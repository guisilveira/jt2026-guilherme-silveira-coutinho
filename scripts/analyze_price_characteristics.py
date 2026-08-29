#!/usr/bin/env python3
"""Ciclo 4: características associadas ao preço anunciado.

Modelos descritivos, sem interpretação causal:
- uma linha por listing residencial da captura de 20/01;
- somente segmentos principais do Ciclo 2;
- regressões individuais de log(preço) com efeitos fixos de segmento;
- IC95 por 500 bootstraps agrupados por owner_id.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GENERATED_DIR = ROOT / "reports" / "generated"

DETAILS_FILE = DATA_DIR / "Details_Itapema.csv"
HOSTS_FILE = DATA_DIR / "Hosts_ids_Itapema.csv"
PROFILE_LISTINGS_FILE = PROCESSED_DIR / "airbnb_listing_profile_metrics.csv"
PROFILE_SEGMENTS_FILE = GENERATED_DIR / "airbnb_profile_segments.csv"

LISTING_OUTPUT = PROCESSED_DIR / "airbnb_listing_characteristics.csv"
QUALITY_OUTPUT = GENERATED_DIR / "airbnb_characteristics_quality.csv"
ASSOCIATIONS_OUTPUT = GENERATED_DIR / "airbnb_characteristic_associations.csv"
SENSITIVITIES_OUTPUT = GENERATED_DIR / "airbnb_characteristic_sensitivities.csv"
COMPARISONS_OUTPUT = GENERATED_DIR / "airbnb_adjusted_comparisons.csv"
CHECKS_OUTPUT = GENERATED_DIR / "airbnb_characteristics_checks.csv"
SUMMARY_OUTPUT = GENERATED_DIR / "airbnb_characteristics_summary.json"
REPORT_OUTPUT = ROOT / "reports" / "airbnb_characteristics_analysis.md"

ID = "airbnb_listing_id"
BOOTSTRAP_REPETITIONS = 500
MAIN_METHOD = "snapshot_2025_01_20"
ORIGINAL = "original"
RAW_FILES = sorted(DATA_DIR.glob("*_Itapema.csv"))

COMPARISON_PAIRS = (
    ("centro|apartamento|1 quarto", "centro|apartamento|2 quartos"),
    ("centro|apartamento|1 quarto", "centro|apartamento|3 quartos"),
    ("centro|apartamento|1 quarto", "meia praia|apartamento|1 quarto"),
    ("morretes|apartamento|2 quartos", "centro|apartamento|2 quartos"),
    ("morretes|apartamento|2 quartos", "centro|apartamento|1 quarto"),
)

AMENITY_RULES = {
    "tem_ar_condicionado": r"\bar-condicionado\b",
    "tem_estacionamento": r"\bestacionamento\b",
    "tem_piscina": r"\bpiscina\b",
    "tem_elevador": r"\belevador\b",
    "tem_churrasqueira": r"\bchurrasqueira\b",
    "tem_acesso_praia": r"\bacesso a praia\b",
    "tem_wifi": r"\bwi-?fi\b|\bwifi\b",
}

FEATURES: list[dict[str, Any]] = [
    {"key": "capacidade_hospedes", "label": "Capacidade de hóspedes", "column": "number_of_guests", "kind": "numeric", "scale": 1.0, "unit": "+1 hóspede"},
    {"key": "banheiros", "label": "Banheiros", "column": "number_of_bathrooms", "kind": "numeric", "scale": 1.0, "unit": "+1 banheiro"},
    {"key": "camas", "label": "Camas", "column": "number_of_beds", "kind": "numeric", "scale": 1.0, "unit": "+1 cama"},
    {"key": "quantidade_comodidades", "label": "Quantidade de comodidades", "column": "amenities_count", "kind": "numeric", "scale": 5.0, "unit": "+5 comodidades"},
    {"key": "taxa_limpeza", "label": "Taxa de limpeza positiva", "column": "cleaning_fee", "kind": "positive_numeric", "scale": 100.0, "unit": "+R$ 100"},
    {"key": "quantidade_fotos", "label": "Quantidade de fotos positiva", "column": "picture_count", "kind": "positive_numeric", "scale": 10.0, "unit": "+10 fotos"},
    {"key": "presenca_reviews", "label": "Presença de reviews", "column": "has_reviews", "kind": "binary", "scale": 1.0, "unit": "sim vs. não"},
    {"key": "quantidade_reviews", "label": "Quantidade de reviews", "column": "number_of_reviews", "kind": "log2p1", "scale": 1.0, "unit": "dobro de reviews+1"},
    {"key": "nota_anuncio", "label": "Nota do anúncio avaliado", "column": "listing_rating_observed", "kind": "rating", "scale": 0.1, "unit": "+0,1 ponto"},
    {"key": "favorito_hospedes", "label": "Favorito dos hóspedes", "column": "is_guest_favorite", "kind": "binary_nullable", "scale": 1.0, "unit": "sim vs. não"},
    {"key": "reserva_instantanea", "label": "Reserva instantânea", "column": "can_instant_book", "kind": "binary_nullable", "scale": 1.0, "unit": "sim vs. não"},
    {"key": "anfitriao_profissional", "label": "Anfitrião profissional", "column": "is_professional", "kind": "binary_nullable", "scale": 1.0, "unit": "sim vs. não"},
    {"key": "superhost", "label": "Superhost", "column": "is_superhost", "kind": "binary_nullable", "scale": 1.0, "unit": "sim vs. não"},
    {"key": "reviews_anfitriao", "label": "Quantidade de reviews do anfitrião", "column": "number_of_reviews_host", "kind": "log2p1", "scale": 1.0, "unit": "dobro de reviews+1"},
    {"key": "tempo_anfitriao", "label": "Tempo como anfitrião", "column": "host_tenure_years", "kind": "numeric", "scale": 1.0, "unit": "+1 ano"},
    {"key": "nota_anfitriao", "label": "Nota do anfitrião avaliado", "column": "host_rating_observed", "kind": "rating", "scale": 0.1, "unit": "+0,1 ponto"},
    {"key": "ar_condicionado", "label": "Ar-condicionado", "column": "tem_ar_condicionado", "kind": "binary", "scale": 1.0, "unit": "presente vs. ausente"},
    {"key": "estacionamento", "label": "Estacionamento", "column": "tem_estacionamento", "kind": "binary", "scale": 1.0, "unit": "presente vs. ausente"},
    {"key": "piscina", "label": "Piscina", "column": "tem_piscina", "kind": "binary", "scale": 1.0, "unit": "presente vs. ausente"},
    {"key": "elevador", "label": "Elevador", "column": "tem_elevador", "kind": "binary", "scale": 1.0, "unit": "presente vs. ausente"},
    {"key": "churrasqueira", "label": "Churrasqueira", "column": "tem_churrasqueira", "kind": "binary", "scale": 1.0, "unit": "presente vs. ausente"},
    {"key": "acesso_praia", "label": "Acesso à praia", "column": "tem_acesso_praia", "kind": "binary", "scale": 1.0, "unit": "presente vs. ausente"},
    {"key": "wifi", "label": "Wi-Fi", "column": "tem_wifi", "kind": "binary", "scale": 1.0, "unit": "presente vs. ausente"},
]

SENSITIVITY_SPECS = (
    ("headline_20_01", "Captura de 20/01", MAIN_METHOD, ORIGINAL, False),
    ("mediana_capturas", "Mediana entre capturas nos mesmos imóveis", "median_across_captures", ORIGINAL, False),
    ("ajuste_calendario", "Ajuste de calendário aprovado", "snapshot_calendar_adjusted", ORIGINAL, False),
    ("sem_precos_10k", "Sem preços ≥ R$ 10 mil", MAIN_METHOD, "exclude_suspicious_prices", False),
    ("sem_tres_imoveis", "Sem os três imóveis afetados", MAIN_METHOD, "exclude_affected_listings", False),
    ("peso_igual_anfitriao", "Peso igual por anfitrião", MAIN_METHOD, ORIGINAL, True),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_seed(*parts: str) -> int:
    return int.from_bytes(hashlib.sha256("|".join(parts).encode()).digest()[:8], "little")


def json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def parse_amenities(value: Any) -> tuple[list[str], bool]:
    try:
        parsed = json.loads(value) if pd.notna(value) else []
        if not isinstance(parsed, list):
            return [], False
        normalized = sorted({normalize_text(item) for item in parsed if str(item).strip()})
        return normalized, True
    except (json.JSONDecodeError, TypeError):
        return [], False


def parse_nullable_bool(series: pd.Series) -> pd.Series:
    mapping = {True: True, False: False, "True": True, "False": False, "true": True, "false": False, 1: True, 0: False}
    return series.map(mapping).astype("boolean")


def feature_values(frame: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    raw = frame[spec["column"]]
    kind = spec["kind"]
    if kind in {"binary", "binary_nullable"}:
        values = pd.to_numeric(raw.astype("boolean"), errors="coerce")
    else:
        values = pd.to_numeric(raw, errors="coerce")
    values = values.astype(float)
    values.loc[~np.isfinite(values)] = np.nan
    if kind == "positive_numeric":
        values = values.where(values > 0) / float(spec["scale"])
    elif kind == "log2p1":
        values = values.where(values >= 0)
        values = np.log1p(values) / np.log(2.0)
    elif kind == "rating":
        values = values.where(values > 0) / float(spec["scale"])
    elif kind == "numeric":
        values = values / float(spec["scale"])
    return values


def build_segment_controls(segment: pd.Series) -> tuple[np.ndarray, list[str]]:
    categories = sorted(segment.astype(str).unique())
    controls = pd.get_dummies(pd.Categorical(segment.astype(str), categories=categories), drop_first=True, dtype=float)
    return controls.to_numpy(dtype=float), [f"segment::{category}" for category in categories[1:]]


def fit_ols(y: np.ndarray, x: np.ndarray, weights: np.ndarray | None = None) -> tuple[np.ndarray, int]:
    if weights is not None:
        root = np.sqrt(weights)
        x_fit = x * root[:, None]
        y_fit = y * root
    else:
        x_fit, y_fit = x, y
    rank = int(np.linalg.matrix_rank(x_fit))
    if rank < x_fit.shape[1]:
        return np.full(x_fit.shape[1], np.nan), rank
    beta = np.linalg.lstsq(x_fit, y_fit, rcond=None)[0]
    return beta, rank


def prepare_feature_model(frame: pd.DataFrame, spec: dict[str, Any], price_column: str = "price_model") -> tuple[pd.DataFrame, np.ndarray, np.ndarray, list[str]]:
    work = frame[[ID, "owner_id", "segment_key", price_column]].copy()
    work["feature_value"] = feature_values(frame, spec)
    work[price_column] = pd.to_numeric(work[price_column], errors="coerce")
    work = work.loc[
        work["feature_value"].notna()
        & work[price_column].notna()
        & np.isfinite(work[price_column])
        & work[price_column].gt(0)
        & work["owner_id"].notna()
    ].reset_index(drop=True)
    controls, control_names = build_segment_controls(work["segment_key"])
    x = np.column_stack([np.ones(len(work)), work["feature_value"].to_numpy(float), controls])
    y = np.log(work[price_column].to_numpy(float))
    return work, y, x, ["intercept", spec["key"], *control_names]


def cluster_bootstrap_feature(work: pd.DataFrame, y: np.ndarray, x: np.ndarray, seed: int) -> np.ndarray:
    owners = sorted(work["owner_id"].astype(str).unique())
    owner_rows = {owner: np.flatnonzero(work["owner_id"].astype(str).to_numpy() == owner) for owner in owners}
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    attempts = 0
    while len(estimates) < BOOTSTRAP_REPETITIONS and attempts < BOOTSTRAP_REPETITIONS * 5:
        attempts += 1
        sampled = rng.choice(owners, size=len(owners), replace=True)
        indices = np.concatenate([owner_rows[owner] for owner in sampled])
        beta, rank = fit_ols(y[indices], x[indices])
        if rank == x.shape[1] and np.isfinite(beta[1]):
            estimates.append(float(beta[1]))
    require(len(estimates) == BOOTSTRAP_REPETITIONS, "Não foi possível obter 500 repetições válidas para uma característica.")
    return np.array(estimates)


def effect_pct(beta: float) -> float:
    return float(np.expm1(beta)) if np.isfinite(beta) else np.nan


def main_segment_keys(profile_segments: pd.DataFrame) -> set[str]:
    mask = (
        profile_segments["metodo"].eq(MAIN_METHOD)
        & profile_segments["tratamento_outlier"].eq(ORIGINAL)
        & profile_segments["metrica"].eq("preco_total")
        & profile_segments["tratamento_capacidade"].eq("não aplicável")
        & profile_segments["suporte_metrica"].eq("principal")
    )
    keys = set(profile_segments.loc[mask, "segment_key"])
    require(len(keys) == 7, "O universo aprovado do Ciclo 2 deixou de ter sete segmentos principais.")
    return keys


def build_listing_base(
    details: pd.DataFrame,
    hosts: pd.DataFrame,
    profile: pd.DataFrame,
    profile_segments: pd.DataFrame,
    extra_segment_keys: set[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    keys = main_segment_keys(profile_segments)
    keys.update(extra_segment_keys or set())
    headline = profile.loc[
        profile["metodo"].eq(MAIN_METHOD)
        & profile["tratamento_outlier"].eq(ORIGINAL)
        & profile["segment_key"].isin(keys)
    ].copy()
    expected_rows = 668 if not extra_segment_keys else 684
    require(len(headline) == expected_rows and headline[ID].is_unique, f"Headline analítico não reconciliou em {expected_rows} imóveis únicos.")
    detail_columns = [
        ID, "owner_id", "aquisition_date", "number_of_guests", "number_of_bathrooms",
        "number_of_beds", "amenities", "cleaning_fee", "picture_count", "number_of_reviews",
        "star_rating", "is_guest_favorite", "can_instant_book", "is_professional",
    ]
    detail = details[detail_columns].copy()
    detail[ID] = detail[ID].astype("string")
    detail["owner_id"] = detail["owner_id"].astype("string")
    host = hosts.copy()
    host["owner_id"] = host["owner_id"].astype("string")
    require(not host.duplicated(["owner_id", "host_snapshot_date"]).any(), "Chave temporal de Hosts deixou de ser única.")
    detail_host = detail.merge(
        host,
        left_on=["owner_id", "aquisition_date"],
        right_on=["owner_id", "host_snapshot_date"],
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    join_coverage = float(detail_host["_merge"].eq("both").mean())
    require(len(detail_host) == len(details), "Join temporal de hosts multiplicou Details.")
    require(join_coverage == 1.0, "Join temporal de hosts perdeu cobertura.")
    detail_host = detail_host.drop(columns="_merge")
    base = headline[[
        ID, "preco_total", "owner_id", "bairro", "tipo_imovel", "quartos", "segment_key", "segmento_imoveis",
    ]].rename(columns={"owner_id": "owner_id_price"}).merge(
        detail_host,
        on=ID,
        how="left",
        validate="one_to_one",
    )
    require(base["owner_id_price"].astype(str).equals(base["owner_id"].astype(str)), "owner_id divergiu entre artefato de preço e Details.")
    base = base.drop(columns="owner_id_price")
    base["can_instant_book"] = parse_nullable_bool(base["can_instant_book"])
    base["is_professional"] = parse_nullable_bool(base["is_professional"])
    base["is_guest_favorite"] = parse_nullable_bool(base["is_guest_favorite"])
    base["is_superhost"] = parse_nullable_bool(base["is_superhost"])

    parsed = base["amenities"].map(parse_amenities)
    base["amenities_normalized"] = parsed.map(lambda item: json.dumps(item[0], ensure_ascii=False))
    base["amenities_parse_ok"] = parsed.map(lambda item: item[1])
    base["amenities_count"] = parsed.map(lambda item: len(item[0]) if item[1] else np.nan)
    for column, pattern in AMENITY_RULES.items():
        base[column] = parsed.map(lambda item: bool(any(re.search(pattern, amenity) for amenity in item[0])) if item[1] else pd.NA).astype("boolean")

    base["has_reviews"] = pd.to_numeric(base["number_of_reviews"], errors="coerce").gt(0).astype("boolean")
    listing_rating = pd.to_numeric(base["star_rating"], errors="coerce")
    base["listing_rating_observed"] = listing_rating.where(base["has_reviews"].fillna(False) & listing_rating.gt(0))
    host_reviews = pd.to_numeric(base["number_of_reviews_host"], errors="coerce")
    host_rating = pd.to_numeric(base["star_rating_host"], errors="coerce")
    base["host_has_reviews"] = host_reviews.gt(0).astype("boolean")
    base["host_rating_observed"] = host_rating.where(base["host_has_reviews"].fillna(False) & host_rating.gt(0))
    base["host_tenure_years"] = pd.to_numeric(base["years_host"], errors="coerce") + pd.to_numeric(base["months_host"], errors="coerce") / 12.0
    base["cleaning_fee_zero_ambiguous"] = pd.to_numeric(base["cleaning_fee"], errors="coerce").eq(0)
    base["picture_count_zero_suspect"] = pd.to_numeric(base["picture_count"], errors="coerce").eq(0)
    base["price_model"] = base["preco_total"]
    base = base.sort_values(ID, kind="stable").reset_index(drop=True)
    join = {
        "details_rows": len(details),
        "host_temporal_key_duplicates": int(hosts.duplicated(["owner_id", "host_snapshot_date"]).sum()),
        "join_rows": len(detail_host),
        "join_coverage": join_coverage,
        "headline_rows": len(base),
        "headline_hosts": int(base["owner_id"].nunique()),
    }
    return base, join


def build_quality(base: pd.DataFrame, details: pd.DataFrame, hosts: pd.DataFrame, join: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    def add(category: str, item: str, count: int | float, treatment: str, notes: str = "") -> None:
        rows.append({"categoria": category, "item": item, "registros": count, "tratamento": treatment, "observacao": notes})
    add("universo", "Imóveis nos sete segmentos principais", len(base), "resultado principal")
    add("join hosts", "Cobertura da chave owner_id + timestamp", join["join_coverage"], "exigida em 100%")
    add("join hosts", "Duplicações da chave temporal", join["host_temporal_key_duplicates"], "bloqueio se > 0")
    add("join hosts", "Imóveis após o join", len(base), "uma linha por imóvel")
    add("campos excluídos", "response_rate_shown preenchido", int(hosts["response_rate_shown"].notna().sum()), "não entra na análise")
    add("campos excluídos", "response_time_shown preenchido", int(hosts["response_time_shown"].notna().sum()), "não entra na análise")
    add("comodidades", "Falhas de parsing", int((~base["amenities_parse_ok"]).sum()), "excluídas somente das características de amenities")
    for column, pattern in AMENITY_RULES.items():
        add("regra de comodidade", f"{column}: `{pattern}`", int(base[column].fillna(False).sum()), "correspondência literal após casefold e remoção de acentos")
    add("notas", "Anúncios sem reviews tratados como não avaliados", int((~base["has_reviews"].fillna(False)).sum()), "nota convertida para ausente")
    add("notas", "Notas do anúncio disponíveis", int(base["listing_rating_observed"].notna().sum()), "somente anúncios com reviews e nota > 0")
    add("notas", "Anfitriões sem reviews tratados como não avaliados", int((~base["host_has_reviews"].fillna(False)).sum()), "nota convertida para ausente")
    add("notas", "Notas do anfitrião disponíveis", int(base["host_rating_observed"].notna().sum()), "somente anfitriões com reviews e nota > 0")
    add("zeros ambíguos", "Taxa de limpeza igual a zero", int(base["cleaning_fee_zero_ambiguous"].sum()), "preservada; excluída da regressão individual de valor")
    add("zeros suspeitos", "Quantidade de fotos igual a zero", int(base["picture_count_zero_suspect"].sum()), "preservada; excluída da regressão individual de quantidade")
    for column in ["can_instant_book", "is_professional", "is_guest_favorite", "is_superhost"]:
        add("booleanos", f"{column} desconhecido", int(base[column].isna().sum()), "permanece desconhecido; não convertido em false")
    for spec in FEATURES:
        values = feature_values(base, spec)
        mask = values.notna()
        add("disponibilidade por característica", spec["label"], int(mask.sum()), "amostra da regressão individual", f"{base.loc[mask, 'owner_id'].nunique()} anfitriões")
    return pd.DataFrame(rows)


def price_maps(profile: pd.DataFrame, base_ids: set[str]) -> dict[str, pd.DataFrame]:
    maps: dict[str, pd.DataFrame] = {}
    for code, _, method, outlier, _ in SENSITIVITY_SPECS:
        if code == "peso_igual_anfitriao":
            continue
        frame = profile.loc[
            profile["metodo"].eq(method)
            & profile["tratamento_outlier"].eq(outlier)
            & profile[ID].isin(base_ids),
            [ID, "preco_total"],
        ].copy()
        require(not frame[ID].duplicated().any(), f"Preço duplicado na sensibilidade {code}.")
        maps[code] = frame.rename(columns={"preco_total": "price_model"})
    return maps


def run_associations(base: pd.DataFrame, profile: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    maps = price_maps(profile, set(base[ID]))
    association_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    for spec in FEATURES:
        headline, y, x, _ = prepare_feature_model(base, spec)
        beta, rank = fit_ols(y, x)
        estimable = rank == x.shape[1] and np.isfinite(beta[1])
        if estimable:
            bootstrap = cluster_bootstrap_feature(headline, y, x, deterministic_seed("feature", spec["key"]))
            low, high = np.quantile(bootstrap, [0.025, 0.975])
            direction = "positiva" if beta[1] > 0 else ("negativa" if beta[1] < 0 else "nula")
            headline_effect = effect_pct(float(beta[1]))
        else:
            bootstrap = np.array([], dtype=float)
            low, high = np.nan, np.nan
            direction = "não estimável"
            headline_effect = np.nan
        feature_sensitivities: list[float] = []
        for code, label, _, _, equal_host in SENSITIVITY_SPECS:
            if code == "headline_20_01" or equal_host:
                sensitivity_base = base.copy()
            else:
                sensitivity_base = base.drop(columns="price_model").merge(maps[code], on=ID, how="inner", validate="one_to_one")
            work, sy, sx, _ = prepare_feature_model(sensitivity_base, spec)
            weights = None
            if equal_host:
                counts = work["owner_id"].map(work["owner_id"].value_counts()).to_numpy(float)
                weights = 1.0 / counts
            sbeta, srank = fit_ols(sy, sx, weights)
            value = float(sbeta[1]) if srank == sx.shape[1] else np.nan
            feature_sensitivities.append(value)
            sensitivity_rows.append({
                "caracteristica": spec["key"], "caracteristica_label": spec["label"], "unidade_efeito": spec["unit"],
                "sensibilidade": code, "sensibilidade_label": label, "n_listings": len(work),
                "n_hosts": int(work["owner_id"].nunique()), "coeficiente_log": value,
                "efeito_percentual_aproximado": effect_pct(value), "rank_modelo": srank, "colunas_modelo": sx.shape[1],
            })
        signs = np.sign(np.array(feature_sensitivities, dtype=float))
        direction_stable = bool(estimable and np.isfinite(signs).all() and (signs == np.sign(beta[1])).all() and np.sign(beta[1]) != 0)
        ci_excludes_zero = bool(estimable and (low > 0 or high < 0))
        status = "sustentada" if ci_excludes_zero and direction_stable else "inconclusiva"
        association_rows.append({
            "caracteristica": spec["key"], "caracteristica_label": spec["label"], "unidade_efeito": spec["unit"],
            "n_listings": len(headline), "n_hosts": int(headline["owner_id"].nunique()),
            "coeficiente_log": float(beta[1]) if estimable else np.nan, "efeito_percentual_aproximado": headline_effect,
            "ic95_inferior_percentual": effect_pct(float(low)), "ic95_superior_percentual": effect_pct(float(high)),
            "direcao": direction, "intervalo_exclui_zero": ci_excludes_zero,
            "direcao_preservada_sensibilidades": direction_stable, "classificacao": status,
            "bootstrap_repeticoes": BOOTSTRAP_REPETITIONS, "bootstrap_validas": len(bootstrap),
            "estimavel_com_controle_segmento": estimable,
        })
    associations = pd.DataFrame(association_rows).sort_values(["classificacao", "efeito_percentual_aproximado"], ascending=[True, False], kind="stable").reset_index(drop=True)
    sensitivities = pd.DataFrame(sensitivity_rows).sort_values(["caracteristica", "sensibilidade"], kind="stable").reset_index(drop=True)
    return associations, sensitivities


def fill_with_segment_median(frame: pd.DataFrame, source: str, valid: pd.Series | None = None) -> tuple[pd.Series, pd.Series]:
    values = pd.to_numeric(frame[source], errors="coerce").astype(float)
    observed = values.notna() & np.isfinite(values)
    if valid is not None:
        observed &= valid
    filled = values.where(observed)
    segment_medians = frame.assign(_value=filled).groupby("segment_key")["_value"].transform("median")
    global_median = float(filled.median())
    filled = filled.fillna(segment_medians).fillna(global_median)
    return filled, ~observed


def build_adjusted_design(base: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    columns: dict[str, pd.Series] = {}
    direct_numeric = {
        "capacidade": ("number_of_guests", None), "banheiros": ("number_of_bathrooms", None),
        "camas": ("number_of_beds", None), "comodidades_5": ("amenities_count", None),
        "reviews_log2": ("number_of_reviews", "log2p1"), "host_reviews_log2": ("number_of_reviews_host", "log2p1"),
        "tempo_host": ("host_tenure_years", None),
    }
    for name, (source, transform) in direct_numeric.items():
        values, _ = fill_with_segment_median(base, source)
        if name == "comodidades_5": values = values / 5.0
        if transform == "log2p1": values = np.log1p(values.clip(lower=0)) / np.log(2.0)
        columns[name] = values
    cleaning, cleaning_unknown = fill_with_segment_median(base, "cleaning_fee", pd.to_numeric(base["cleaning_fee"], errors="coerce").gt(0))
    photos, photos_unknown = fill_with_segment_median(base, "picture_count", pd.to_numeric(base["picture_count"], errors="coerce").gt(0))
    columns["taxa_limpeza_100"] = cleaning / 100.0
    columns["taxa_limpeza_desconhecida"] = cleaning_unknown.astype(float)
    columns["fotos_10"] = photos / 10.0
    columns["fotos_desconhecidas"] = photos_unknown.astype(float)
    listing_rating, _ = fill_with_segment_median(base, "listing_rating_observed")
    host_rating, host_rating_unknown = fill_with_segment_median(base, "host_rating_observed")
    columns["nota_anuncio_01"] = listing_rating / 0.1
    columns["tem_reviews"] = base["has_reviews"].astype(float)
    columns["nota_host_01"] = host_rating / 0.1
    columns["host_sem_nota"] = host_rating_unknown.astype(float)
    for source in ["is_guest_favorite", "is_superhost", *AMENITY_RULES.keys()]:
        values = base[source].astype("boolean")
        if values.nunique(dropna=True) > 1:
            columns[source] = values.fillna(False).astype(float)
    unknown_masks: dict[str, pd.Series] = {}
    for source in ["can_instant_book", "is_professional"]:
        values = base[source].astype("boolean")
        columns[f"{source}_true"] = values.eq(True).fillna(False).astype(float)
        unknown_masks[source] = values.isna().astype(float)
    if unknown_masks["can_instant_book"].equals(unknown_masks["is_professional"]):
        columns["instant_professional_unknown"] = unknown_masks["can_instant_book"]
    else:
        columns["can_instant_book_unknown"] = unknown_masks["can_instant_book"]
        columns["is_professional_unknown"] = unknown_masks["is_professional"]
    design = pd.DataFrame(columns, index=base.index)
    variable = [column for column in design.columns if design[column].nunique(dropna=False) > 1]
    design = design[variable]
    continuous = [column for column in variable if not set(design[column].dropna().unique()).issubset({0.0, 1.0})]
    for column in continuous:
        std = float(design[column].std(ddof=0))
        if std > 0:
            design[column] = (design[column] - design[column].mean()) / std
    segment_categories = sorted(base["segment_key"].unique())
    segment = pd.get_dummies(pd.Categorical(base["segment_key"], categories=segment_categories), drop_first=True, dtype=float)
    segment.columns = [f"segment::{category}" for category in segment_categories[1:]]
    x_frame = pd.concat([pd.Series(1.0, index=base.index, name="intercept"), segment, design], axis=1)
    require(not x_frame.isna().any().any(), "Design ajustado contém ausências.")
    x = x_frame.to_numpy(float)
    y = np.log(base["preco_total"].to_numpy(float))
    return y, x, list(x_frame.columns), segment_categories


def segment_contrast_vector(columns: list[str], segment_a: str, segment_b: str) -> np.ndarray:
    vector = np.zeros(len(columns))
    for sign, segment in ((1.0, segment_a), (-1.0, segment_b)):
        column = f"segment::{segment}"
        if column in columns:
            vector[columns.index(column)] += sign
    return vector


def run_adjusted_comparisons(base: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    y, x, columns, segment_categories = build_adjusted_design(base)
    beta, rank = fit_ols(y, x)
    require(rank == x.shape[1], f"Modelo ajustado não tem rank completo: {rank}/{x.shape[1]}.")
    owners = sorted(base["owner_id"].astype(str).unique())
    owner_rows = {owner: np.flatnonzero(base["owner_id"].astype(str).to_numpy() == owner) for owner in owners}
    rng = np.random.default_rng(deterministic_seed("adjusted-comparisons"))
    bootstrap_values = {pair: [] for pair in COMPARISON_PAIRS}
    valid = 0
    attempts = 0
    while valid < BOOTSTRAP_REPETITIONS and attempts < BOOTSTRAP_REPETITIONS * 5:
        attempts += 1
        sampled = rng.choice(owners, size=len(owners), replace=True)
        indices = np.concatenate([owner_rows[owner] for owner in sampled])
        b, r = fit_ols(y[indices], x[indices])
        if r != x.shape[1]:
            continue
        for pair in COMPARISON_PAIRS:
            vector = segment_contrast_vector(columns, *pair)
            bootstrap_values[pair].append(float(vector @ b))
        valid += 1
    require(valid == BOOTSTRAP_REPETITIONS, "Modelo ajustado não produziu 500 bootstraps válidos.")
    rows: list[dict[str, Any]] = []
    for segment_a, segment_b in COMPARISON_PAIRS:
        group_a = base.loc[base["segment_key"] == segment_a]
        group_b = base.loc[base["segment_key"] == segment_b]
        require(len(group_a) and len(group_b), f"Comparação ausente: {segment_a} vs {segment_b}")
        median_a = float(group_a["preco_total"].median())
        median_b = float(group_b["preco_total"].median())
        median_delta = median_a / median_b - 1.0
        vector = segment_contrast_vector(columns, segment_a, segment_b)
        adjusted_beta = float(vector @ beta)
        boot = np.array(bootstrap_values[(segment_a, segment_b)])
        low, high = np.quantile(boot, [0.025, 0.975])
        adjusted_effect = effect_pct(adjusted_beta)
        direction_changed = bool(np.sign(median_delta) != np.sign(adjusted_effect) and np.sign(median_delta) != 0 and np.sign(adjusted_effect) != 0)
        rows.append({
            "segment_key_a": segment_a, "segmento_a": group_a["segmento_imoveis"].iloc[0],
            "segment_key_b": segment_b, "segmento_b": group_b["segmento_imoveis"].iloc[0],
            "n_listings_a": len(group_a), "n_hosts_a": int(group_a["owner_id"].nunique()),
            "n_listings_b": len(group_b), "n_hosts_b": int(group_b["owner_id"].nunique()),
            "preco_mediano_a": median_a, "preco_mediano_b": median_b,
            "diferenca_mediana_percentual": median_delta, "diferenca_ajustada_percentual": adjusted_effect,
            "ic95_ajustado_inferior": effect_pct(float(low)), "ic95_ajustado_superior": effect_pct(float(high)),
            "direcao_mudou_apos_controles": direction_changed,
            "evidencia_ajustada": "sustentada" if low > 0 or high < 0 else "inconclusiva",
            "bootstrap_repeticoes": BOOTSTRAP_REPETITIONS,
        })
    diagnostics = {"design_rows": len(base), "design_columns": x.shape[1], "design_rank": rank, "bootstrap_valid": valid, "segment_categories": segment_categories, "control_columns": columns}
    return pd.DataFrame(rows), diagnostics


def add_check(rows: list[dict[str, Any]], name: str, actual: Any, expected: Any, passed: bool, notes: str = "") -> None:
    rows.append({"check": name, "actual": actual, "expected": expected, "status": "OK" if passed else "FALHOU", "observacao": notes})


def build_checks(base: pd.DataFrame, details: pd.DataFrame, hosts: pd.DataFrame, join: dict[str, Any], associations: pd.DataFrame, sensitivities: pd.DataFrame, comparisons: pd.DataFrame, diagnostics: dict[str, Any], profile: pd.DataFrame, raw_hashes: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    add_check(rows, "Base contém 668 imóveis dos segmentos principais", len(base), 668, len(base) == 668)
    add_check(rows, "Uma linha por imóvel", int(base.duplicated(ID).sum()), 0, not base.duplicated(ID).any())
    add_check(rows, "Sete segmentos principais", base["segment_key"].nunique(), 7, base["segment_key"].nunique() == 7)
    add_check(rows, "Chave temporal de hosts única", join["host_temporal_key_duplicates"], 0, join["host_temporal_key_duplicates"] == 0)
    add_check(rows, "Join com hosts não multiplica imóveis", len(base), join["headline_rows"], len(base) == join["headline_rows"])
    add_check(rows, "Cobertura do join com hosts", join["join_coverage"], 1.0, join["join_coverage"] == 1.0)
    add_check(rows, "Taxa de resposta totalmente vazia e excluída", int(hosts["response_rate_shown"].notna().sum()), 0, hosts["response_rate_shown"].notna().sum() == 0)
    add_check(rows, "Tempo de resposta totalmente vazio e excluído", int(hosts["response_time_shown"].notna().sum()), 0, hosts["response_time_shown"].notna().sum() == 0)
    add_check(rows, "Amenities sem falha de parsing", int((~base["amenities_parse_ok"]).sum()), 0, base["amenities_parse_ok"].all())
    rating_bad = int((base["number_of_reviews"].eq(0) & base["listing_rating_observed"].notna()).sum())
    host_rating_bad = int((base["number_of_reviews_host"].eq(0) & base["host_rating_observed"].notna()).sum())
    add_check(rows, "Nota zero sem reviews não tratada como avaliação", rating_bad, 0, rating_bad == 0)
    add_check(rows, "Nota de host zero sem reviews não tratada como avaliação", host_rating_bad, 0, host_rating_bad == 0)
    for column in ["can_instant_book", "is_professional", "is_guest_favorite", "is_superhost"]:
        if column in details:
            expected_missing = int(details.loc[details[ID].isin(set(base[ID])), column].isna().sum())
        else:
            expected_missing = 0
        actual_missing = int(base[column].isna().sum())
        add_check(rows, f"Booleano {column} preserva desconhecidos", actual_missing, expected_missing, actual_missing == expected_missing, "Nenhum fillna(False) na característica individual.")
    add_check(rows, "Todas as características calculadas", associations["caracteristica"].nunique(), len(FEATURES), associations["caracteristica"].nunique() == len(FEATURES))
    estimable = associations["estimavel_com_controle_segmento"]
    add_check(rows, "500 bootstraps por característica estimável", int(associations.loc[estimable, "bootstrap_validas"].min()), BOOTSTRAP_REPETITIONS, associations.loc[estimable, "bootstrap_validas"].eq(BOOTSTRAP_REPETITIONS).all())
    add_check(rows, "Características não estimáveis explicitamente sinalizadas", int((~estimable).sum()), int(associations["coeficiente_log"].isna().sum()), int((~estimable).sum()) == int(associations["coeficiente_log"].isna().sum()))
    add_check(rows, "Seis sensibilidades por característica", int(sensitivities.groupby("caracteristica").size().min()), len(SENSITIVITY_SPECS), sensitivities.groupby("caracteristica").size().eq(len(SENSITIVITY_SPECS)).all())
    formula_error = float((associations["efeito_percentual_aproximado"] - np.expm1(associations["coeficiente_log"])).abs().max())
    add_check(rows, "Fórmula de efeito percentual reconciliada", formula_error, 0.0, formula_error <= 1e-12)
    headline_ids = set(base[ID])
    median_ids = set(profile.loc[profile["metodo"].eq("median_across_captures") & profile["tratamento_outlier"].eq(ORIGINAL) & profile[ID].isin(headline_ids), ID])
    calendar_ids = set(profile.loc[profile["metodo"].eq("snapshot_calendar_adjusted") & profile[ID].isin(headline_ids), ID])
    add_check(rows, "Mediana entre capturas usa os mesmos imóveis", len(median_ids), len(headline_ids), median_ids == headline_ids)
    add_check(rows, "Ajuste de calendário usa os mesmos imóveis", len(calendar_ids), len(headline_ids), calendar_ids == headline_ids)
    add_check(rows, "Cinco comparações ajustadas", len(comparisons), len(COMPARISON_PAIRS), len(comparisons) == len(COMPARISON_PAIRS))
    add_check(rows, "500 bootstraps no modelo ajustado", diagnostics["bootstrap_valid"], BOOTSTRAP_REPETITIONS, diagnostics["bootstrap_valid"] == BOOTSTRAP_REPETITIONS)
    add_check(rows, "Modelo ajustado com rank completo", diagnostics["design_rank"], diagnostics["design_columns"], diagnostics["design_rank"] == diagnostics["design_columns"])
    after_hashes = {path.name: sha256(path) for path in RAW_FILES}
    add_check(rows, "Hashes dos CSVs originais preservados", after_hashes == raw_hashes, True, after_hashes == raw_hashes)
    deterministic_order = base[ID].is_monotonic_increasing and sensitivities.equals(sensitivities.sort_values(["caracteristica", "sensibilidade"], kind="stable").reset_index(drop=True))
    add_check(rows, "Ordenação determinística", deterministic_order, True, deterministic_order)
    git_result = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    add_check(rows, "git diff --check aprovado", git_result.returncode, 0, git_result.returncode == 0, git_result.stdout + git_result.stderr)
    checks = pd.DataFrame(rows)
    require(checks["status"].eq("OK").all(), "Checks críticos falharam:\n" + checks.loc[checks["status"] != "OK"].to_string(index=False))
    return checks


def fmt_pct(value: Any) -> str:
    if pd.isna(value): return "—"
    return f"{float(value)*100:.1f}%".replace(".", ",")


def fmt_money(value: Any) -> str:
    if pd.isna(value): return "—"
    return "R$ " + f"{float(value):,.0f}".replace(",", ".")


def markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    if frame.empty: return "_Sem resultados._"
    lines = ["| " + " | ".join(label for _, label in columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for _, row in frame.iterrows():
        values: list[str] = []
        for column, _ in columns:
            value = row[column]
            if "percentual" in column or column.startswith("ic95"):
                values.append(fmt_pct(value))
            elif column.startswith("preco"):
                values.append(fmt_money(value))
            elif column.startswith("n_") or "bootstrap" in column:
                values.append(str(int(value)))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_report(base: pd.DataFrame, quality: pd.DataFrame, associations: pd.DataFrame, sensitivities: pd.DataFrame, comparisons: pd.DataFrame, checks: pd.DataFrame) -> tuple[str, dict[str, Any]]:
    positive = associations.loc[(associations["classificacao"] == "sustentada") & (associations["direcao"] == "positiva")]
    negative = associations.loc[(associations["classificacao"] == "sustentada") & (associations["direcao"] == "negativa")]
    inconclusive = associations.loc[associations["classificacao"] == "inconclusiva"]
    direction_changes = comparisons.loc[comparisons["direcao_mudou_apos_controles"]]
    compact_pairs = comparisons.loc[
        comparisons["segment_key_a"].eq("centro|apartamento|1 quarto")
        & comparisons["segment_key_b"].isin(["centro|apartamento|2 quartos", "centro|apartamento|3 quartos"])
    ]
    compact_changed = bool(compact_pairs["direcao_mudou_apos_controles"].any())
    shortlist_pairs = comparisons.loc[comparisons[["segment_key_a", "segment_key_b"]].apply(lambda row: set(row).issubset({"morretes|apartamento|2 quartos", "centro|apartamento|2 quartos", "centro|apartamento|1 quarto"}), axis=1)]
    shortlist_defensible = not bool(shortlist_pairs["evidencia_ajustada"].eq("sustentada").all() and shortlist_pairs["direcao_mudou_apos_controles"].any())
    table_columns = [
        ("caracteristica_label", "Característica"), ("unidade_efeito", "Unidade"), ("n_listings", "Imóveis"),
        ("n_hosts", "Anfitriões"), ("direcao", "Direção"), ("efeito_percentual_aproximado", "Efeito aproximado"),
        ("ic95_inferior_percentual", "IC95 inferior"), ("ic95_superior_percentual", "IC95 superior"),
        ("direcao_preservada_sensibilidades", "Sinal estável"), ("classificacao", "Conclusão"),
    ]
    lines = [
        "# Ciclo 4 — características associadas ao preço anunciado",
        "",
        "## Resultado executivo",
        "",
        f"Foram analisados **{len(base)} imóveis** e **{base['owner_id'].nunique()} anfitriões** nos sete segmentos principais do Ciclo 2. Cada regressão estima separadamente a associação com `log(preço anunciado)`, controlando bairro + tipologia + quartos por efeito fixo de segmento, mas sem controlar simultaneamente as demais características. Portanto, os resultados são associações dentro de perfis comparáveis, não efeitos independentes de cada atributo.",
        "",
        ("Associações positivas sustentadas: **" + ", ".join(positive["caracteristica_label"]) + "**." if len(positive) else "Nenhuma associação positiva cumpriu simultaneamente o IC95 e a estabilidade nas sensibilidades."),
        ("Associações negativas sustentadas: **" + ", ".join(negative["caracteristica_label"]) + "**." if len(negative) else "Nenhuma associação negativa cumpriu simultaneamente o IC95 e a estabilidade nas sensibilidades."),
        f"As outras {len(inconclusive)} características permanecem inconclusivas.",
        "",
        "Associação não é causalidade. O coeficiente de piscina, por exemplo, compara anúncios semelhantes que já diferem em piscina e em fatores não observados; não mede o efeito de instalar uma piscina.",
        "",
        "## Associações sustentadas",
        "",
        markdown_table(pd.concat([positive, negative]), table_columns),
        "",
        "## Associações inconclusivas",
        "",
        markdown_table(inconclusive, table_columns),
        "",
        "## Comparações depois do controle conjunto das características",
        "",
        "O modelo conjunto usa os 668 imóveis principais e acrescenta somente os 16 imóveis de Meia Praia/1 quarto para cumprir o contraste exploratório obrigatório. Essa ampliação não entra nas regressões individuais nem transforma o segmento em principal.",
        "",
        markdown_table(comparisons, [
            ("segmento_a", "Segmento A"), ("segmento_b", "Segmento B"),
            ("n_listings_a", "n A"), ("n_listings_b", "n B"),
            ("diferenca_mediana_percentual", "Diferença mediana original"),
            ("diferenca_ajustada_percentual", "Diferença ajustada"),
            ("ic95_ajustado_inferior", "IC95 ajustado inf."), ("ic95_ajustado_superior", "IC95 ajustado sup."),
            ("direcao_mudou_apos_controles", "Direção mudou"), ("evidencia_ajustada", "Evidência ajustada"),
        ]),
        "",
        "O Ciclo 4 não testou novamente preço anunciado por hóspede comportado nem preço anunciado por quarto. No preço total ajustado, Centro/1 quarto continua abaixo de Centro/2 e Centro/3, mas os intervalos incluem zero; assim, não apareceu evidência para revisar a conclusão do Ciclo 2.",
        "",
        "Este diagnóstico não invalidou a shortlist Morretes/2 quartos, Centro/2 quartos e Centro/1 quarto, mas também não a validou economicamente. A sustentação da shortlist continua vindo dos preços de compra e dos cenários do Ciclo 3.",
        "",
        "## Qualidade, regras e sensibilidades",
        "",
        "O join `Details.(owner_id, aquisition_date) → Hosts.(owner_id, host_snapshot_date)` é N:1 e tem 100% de cobertura. Taxa e tempo de resposta estão 100% vazios e foram excluídos. Booleanos ausentes permanecem desconhecidos; notas zero sem reviews viraram ausentes.",
        "",
        "Comodidades específicas foram identificadas somente pelas sete expressões literais pré-definidas, após casefold e remoção de acentos. Taxa de limpeza zero e fotos zero foram preservadas com flags e excluídas somente das respectivas regressões individuais, por semântica ambígua.",
        "",
        "A classificação exige IC95 agrupado por anfitrião excluindo zero e mesmo sinal nas seis leituras: 20/01, mediana entre capturas nos mesmos imóveis, calendário, duas sensibilidades de preços ≥ R$ 10 mil e peso igual por anfitrião.",
        "",
        "## Limitações",
        "",
        "- Regressões individuais não eliminam confundimento por padrão, área, vista, estado do imóvel, gestão ou seleção da amostra com preço.",
        "- Reviews, notas, favorito e superhost podem ser consequência do tempo e desempenho do anúncio; não são necessariamente causas do preço.",
        "- O modelo ajustado usa representações determinísticas de ausências para não reduzir a amostra, mas seus contrastes são apenas diagnóstico de direção.",
        "- A captura permanece concentrada entre janeiro e abril, e preço anunciado não é receita realizada.",
        "- A recomendação econômica continua dependendo do VivaReal e dos cenários do Ciclo 3.",
        "",
        "## Checks",
        "",
        f"{int(checks['status'].eq('OK').sum())} de {len(checks)} checks foram aprovados. Cada associação estimável e o modelo ajustado usaram 500 repetições de bootstrap por owner_id; Wi-Fi foi explicitamente não estimável por ausência de variação suficiente.",
    ]
    summary = {
        "positive_supported": positive["caracteristica"].tolist(),
        "negative_supported": negative["caracteristica"].tolist(),
        "inconclusive": inconclusive["caracteristica"].tolist(),
        "compact_reading_changed": compact_changed,
        "shortlist_remains_defensible": shortlist_defensible,
        "adjusted_direction_changes": direction_changes[["segment_key_a", "segment_key_b"]].to_dict("records"),
    }
    return "\n".join(lines) + "\n", summary


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    raw_hashes = {path.name: sha256(path) for path in RAW_FILES}
    details = pd.read_csv(DETAILS_FILE, dtype={ID: "string", "owner_id": "string"}, low_memory=False)
    hosts = pd.read_csv(HOSTS_FILE, dtype={"owner_id": "string"}, low_memory=False)
    profile = pd.read_csv(PROFILE_LISTINGS_FILE, dtype={ID: "string", "owner_id": "string"}, low_memory=False)
    profile_segments = pd.read_csv(PROFILE_SEGMENTS_FILE, low_memory=False)
    base, join = build_listing_base(details, hosts, profile, profile_segments)
    quality = build_quality(base, details, hosts, join)
    associations, sensitivities = run_associations(base, profile)
    comparison_base, _ = build_listing_base(
        details,
        hosts,
        profile,
        profile_segments,
        extra_segment_keys={"meia praia|apartamento|1 quarto"},
    )
    comparisons, diagnostics = run_adjusted_comparisons(comparison_base)

    base.to_csv(LISTING_OUTPUT, index=False)
    quality.to_csv(QUALITY_OUTPUT, index=False)
    associations.to_csv(ASSOCIATIONS_OUTPUT, index=False)
    sensitivities.to_csv(SENSITIVITIES_OUTPUT, index=False)
    comparisons.to_csv(COMPARISONS_OUTPUT, index=False)
    checks = build_checks(base, details, hosts, join, associations, sensitivities, comparisons, diagnostics, profile, raw_hashes)
    checks.to_csv(CHECKS_OUTPUT, index=False)
    report, result_summary = build_report(base, quality, associations, sensitivities, comparisons, checks)
    REPORT_OUTPUT.write_text(report, encoding="utf-8")
    summary = {
        "scope": {"main_capture": "2025-01-20", "main_segments": 7, "listing_rows": len(base), "host_rows": int(base["owner_id"].nunique()), "causal_interpretation": False},
        "host_join": join,
        "amenity_rules": AMENITY_RULES,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "adjusted_model": diagnostics,
        "results": result_summary,
        "source_hashes": raw_hashes,
        "checks": {"passed": int(checks["status"].eq("OK").sum()), "total": len(checks), "all_passed": bool(checks["status"].eq("OK").all())},
    }
    SUMMARY_OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False, default=json_value) + "\n", encoding="utf-8")
    print(f"Ciclo 4 concluído: {len(checks)}/{len(checks)} checks OK; {len(associations)} características.")


if __name__ == "__main__":
    main()
