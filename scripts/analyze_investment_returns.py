#!/usr/bin/env python3
"""Ciclo 3: mercado de compra e estimativas simples de retorno.

Escopo deliberado:
- reutiliza os preços por segmento aprovados nos ciclos 1 e 2;
- prepara o VivaReal sem alterar o CSV original;
- relaciona as plataformas apenas por bairro + tipo residencial + quartos;
- calcula testes de estresse, não receita realizada ou retorno líquido.
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

VIVAREAL_FILE = DATA_DIR / "VivaReal_Itapema.csv"
AIRBNB_SEGMENTS_FILE = GENERATED_DIR / "airbnb_profile_segments.csv"
AIRBNB_CALENDAR_FILE = GENERATED_DIR / "airbnb_price_calendar.csv"

VIVAREAL_OUTPUT = PROCESSED_DIR / "vivareal_residential_listings.csv"
QUALITY_OUTPUT = GENERATED_DIR / "vivareal_quality.csv"
VIVAREAL_SEGMENTS_OUTPUT = GENERATED_DIR / "vivareal_segments.csv"
LINK_OUTPUT = GENERATED_DIR / "airbnb_vivareal_segments.csv"
SCENARIOS_OUTPUT = GENERATED_DIR / "investment_scenarios.csv"
ROBUSTNESS_OUTPUT = GENERATED_DIR / "investment_robustness.csv"
CHECKS_OUTPUT = GENERATED_DIR / "investment_checks.csv"
SUMMARY_OUTPUT = GENERATED_DIR / "investment_summary.json"
REPORT_OUTPUT = ROOT / "reports" / "investment_return_analysis.md"

RAW_FILES = sorted(DATA_DIR.glob("*_Itapema.csv"))
RESIDENTIAL_TYPES = {"apartamento", "casa"}
AIRBNB_MAIN_MIN = 30
VIVAREAL_MAIN_MIN = 20
EXPLORATORY_MIN = 10
SALE_LOW_THRESHOLD = 100_000.0
AREA_MAX = 1_000.0
OCCUPANCIES = (0.30, 0.45, 0.60)
SEASONAL_FACTORS = (0.60, 0.80, 1.00)
INTERMEDIATE_OCCUPANCY = 0.45
INTERMEDIATE_SEASONALITY = 0.80
TARGET = "centro|apartamento|1 quarto"
COMPARATORS = (
    "meia praia|apartamento|1 quarto",
    "centro|apartamento|2 quartos",
    "centro|apartamento|3 quartos",
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


def json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return "desconhecido"
    text = str(value).strip().casefold()
    if not text or text == "none":
        return "desconhecido"
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents)


def bedroom_label(value: Any) -> str:
    if pd.isna(value):
        return "quartos desconhecidos"
    number = float(value)
    if number.is_integer():
        integer = int(number)
        return "1 quarto" if integer == 1 else f"{integer} quartos"
    return f"{number:g} quartos"


def title_text(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value).split())


def segment_label(suburb: str, property_type: str, bedrooms: Any) -> str:
    return f"{title_text(suburb)} · {property_type} · {bedroom_label(bedrooms)}"


def support_label(n_airbnb: int, n_vivareal: int) -> str:
    if n_airbnb >= AIRBNB_MAIN_MIN and n_vivareal >= VIVAREAL_MAIN_MIN:
        return "principal"
    if n_airbnb >= EXPLORATORY_MIN and n_vivareal >= EXPLORATORY_MIN:
        return "exploratório"
    return "evidência insuficiente"


def canonical_amenities(value: Any) -> tuple[str, ...]:
    if pd.isna(value) or not str(value).strip():
        return ()
    parsed = json.loads(str(value))
    require(isinstance(parsed, list), "amenities não contém uma lista JSON.")
    return tuple(sorted(str(item) for item in parsed))


def quantile(series: pd.Series, value: float) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.quantile(value)) if len(clean) else np.nan


def median(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.median()) if len(clean) else np.nan


def tukey_outer_fences(series: pd.Series) -> tuple[float, float]:
    q25 = quantile(series, 0.25)
    q75 = quantile(series, 0.75)
    iqr = q75 - q25
    return q25 - 3.0 * iqr, q75 + 3.0 * iqr


def read_vivareal() -> pd.DataFrame:
    return pd.read_csv(
        VIVAREAL_FILE,
        dtype={"listing_id": "string", "advertiser_name": "string"},
        low_memory=False,
    )


def validate_and_deduplicate(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    require(len(raw) == 8_329, "VivaReal bruto deixou de ter 8.329 linhas.")
    duplicate_rows = raw.loc[raw.duplicated("listing_id", keep=False)].copy()
    material_ids: list[str] = []
    amenities_order_only = 0
    for listing_id, group in duplicate_rows.groupby("listing_id", sort=True):
        normalized = group.copy()
        normalized["amenities"] = normalized["amenities"].map(canonical_amenities)
        materially_equal = all(
            normalized[column].astype("string").fillna("<NA>").nunique() == 1
            for column in normalized.columns
        )
        if not materially_equal:
            material_ids.append(str(listing_id))
        elif group["amenities"].astype("string").nunique(dropna=False) > 1:
            amenities_order_only += 1
    require(
        not material_ids,
        "Duplicações do VivaReal possuem divergências materiais: "
        + ", ".join(material_ids[:10]),
    )
    deduplicated = (
        raw.assign(_source_row=np.arange(len(raw)))
        .sort_values(["listing_id", "_source_row"], kind="stable")
        .drop_duplicates("listing_id", keep="first")
        .sort_values("_source_row", kind="stable")
        .drop(columns="_source_row")
        .reset_index(drop=True)
    )
    require(deduplicated["listing_id"].nunique() == 8_293, "Deduplicação não produziu 8.293 IDs.")
    return deduplicated, {
        "duplicate_ids": int(duplicate_rows["listing_id"].nunique()),
        "duplicate_rows_removed": int(len(raw) - len(deduplicated)),
        "amenities_order_only_ids": int(amenities_order_only),
        "material_divergence_ids": len(material_ids),
    }


def prepare_vivareal(deduplicated: pd.DataFrame) -> pd.DataFrame:
    frame = deduplicated.copy()
    frame["suburb_original"] = frame["suburb"]
    frame["suburb_norm"] = frame["suburb"].map(normalize_text)
    frame["listing_type_norm"] = frame["listing_type"].map(normalize_text)
    frame["bedrooms_numeric"] = pd.to_numeric(frame["bedrooms"], errors="coerce")
    frame["bedrooms_conversion_failed"] = frame["bedrooms"].notna() & frame["bedrooms_numeric"].isna()
    frame["bedrooms_valid"] = (
        frame["bedrooms_numeric"].notna()
        & np.isfinite(frame["bedrooms_numeric"].astype(float))
        & frame["bedrooms_numeric"].ge(0)
        & np.isclose(frame["bedrooms_numeric"] % 1, 0)
    )
    frame["quartos_label"] = frame["bedrooms_numeric"].map(bedroom_label)
    frame["segment_key"] = (
        frame["suburb_norm"]
        + "|"
        + frame["listing_type_norm"]
        + "|"
        + frame["quartos_label"]
    )
    frame["segmento_imoveis"] = [
        segment_label(suburb, kind, rooms)
        for suburb, kind, rooms in zip(
            frame["suburb_norm"], frame["listing_type_norm"], frame["bedrooms_numeric"]
        )
    ]
    frame["residential_scope"] = frame["listing_type_norm"].isin(RESIDENTIAL_TYPES)
    residential = frame.loc[frame["residential_scope"]].copy()

    for source, target in (
        ("sale_price", "sale_price_numeric"),
        ("usable_area", "usable_area_numeric"),
        ("monthly_condo_fee", "monthly_condo_fee_numeric"),
        ("yearly_iptu", "yearly_iptu_numeric"),
    ):
        residential[target] = pd.to_numeric(residential[source], errors="coerce")
        residential[f"{source}_conversion_failed"] = (
            residential[source].notna() & residential[target].isna()
        )

    sale = residential["sale_price_numeric"]
    residential["sale_price_invalid"] = sale.isna() | ~np.isfinite(sale.astype(float)) | sale.le(0)
    residential["sale_price_below_100k"] = ~residential["sale_price_invalid"] & sale.lt(SALE_LOW_THRESHOLD)
    residential["sale_price_tukey_suspect"] = False
    residential["sale_price_tukey_lower"] = np.nan
    residential["sale_price_tukey_upper"] = np.nan
    for _, index in residential.groupby("segment_key", sort=True).groups.items():
        valid = residential.loc[index, "sale_price_numeric"]
        valid = valid.loc[np.isfinite(valid) & valid.gt(0)]
        if len(valid) >= VIVAREAL_MAIN_MIN:
            lower, upper = tukey_outer_fences(valid)
            residential.loc[index, "sale_price_tukey_lower"] = lower
            residential.loc[index, "sale_price_tukey_upper"] = upper
            residential.loc[index, "sale_price_tukey_suspect"] = (
                residential.loc[index, "sale_price_numeric"].lt(lower)
                | residential.loc[index, "sale_price_numeric"].gt(upper)
            ) & ~residential.loc[index, "sale_price_invalid"]
    residential["sale_price_suspect"] = (
        residential["sale_price_below_100k"] | residential["sale_price_tukey_suspect"]
    )

    area = residential["usable_area_numeric"]
    residential["usable_area_invalid"] = area.isna() | ~np.isfinite(area.astype(float))
    residential["usable_area_suspect"] = (
        ~residential["usable_area_invalid"] & (area.le(0) | area.gt(AREA_MAX))
    )
    residential["usable_area_valid_for_m2"] = ~residential["usable_area_invalid"] & ~residential["usable_area_suspect"]
    residential["sale_price_per_m2"] = np.where(
        residential["usable_area_valid_for_m2"] & ~residential["sale_price_invalid"],
        sale / area,
        np.nan,
    )

    condo = residential["monthly_condo_fee_numeric"]
    residential["condo_unknown"] = condo.isna() | condo.eq(0)
    residential["condo_invalid"] = condo.notna() & (~np.isfinite(condo.astype(float)) | condo.lt(0))
    residential["condo_annual_ge_sale"] = (
        condo.gt(0) & ~residential["condo_invalid"] & ~residential["sale_price_invalid"] & condo.mul(12).ge(sale)
    )
    residential["condo_tukey_suspect"] = False
    residential["condo_tukey_upper"] = np.nan
    for _, index in residential.groupby("segment_key", sort=True).groups.items():
        valid = residential.loc[index, "monthly_condo_fee_numeric"]
        valid = valid.loc[np.isfinite(valid) & valid.gt(0)]
        if len(valid) >= VIVAREAL_MAIN_MIN:
            _, upper = tukey_outer_fences(valid)
            residential.loc[index, "condo_tukey_upper"] = upper
            residential.loc[index, "condo_tukey_suspect"] = residential.loc[index, "monthly_condo_fee_numeric"].gt(upper)
    residential["condo_suspect"] = residential["condo_annual_ge_sale"] | residential["condo_tukey_suspect"]
    residential["condo_valid_observed"] = (
        condo.gt(0)
        & ~residential["condo_invalid"]
        & ~residential["condo_unknown"]
        & ~residential["condo_suspect"]
    )

    iptu = residential["yearly_iptu_numeric"]
    residential["iptu_unknown"] = iptu.isna() | iptu.eq(0)
    residential["iptu_invalid"] = iptu.notna() & (~np.isfinite(iptu.astype(float)) | iptu.lt(0))
    residential["iptu_suspect"] = (
        iptu.gt(0) & ~residential["iptu_invalid"] & ~residential["sale_price_invalid"] & iptu.ge(sale)
    )
    residential["iptu_positive_observed"] = iptu.gt(0) & ~residential["iptu_invalid"] & ~residential["iptu_suspect"]
    residential["advertiser_name_norm"] = residential["advertiser_name"].fillna("desconhecido").str.strip().replace("", "desconhecido")
    return residential.sort_values("listing_id", kind="stable").reset_index(drop=True)


def build_quality(raw: pd.DataFrame, deduplicated: pd.DataFrame, residential: pd.DataFrame, duplicate_info: dict[str, int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(category: str, item: str, count: int, treatment: str, notes: str = "") -> None:
        rows.append({"categoria": category, "item": item, "registros": int(count), "tratamento": treatment, "observacao": notes})

    add("deduplicação", "Linhas brutas", len(raw), "preservadas no CSV original")
    add("deduplicação", "IDs duplicados", duplicate_info["duplicate_ids"], "DEDUPLICAÇÃO")
    add("deduplicação", "Linhas removidas da tabela derivada", duplicate_info["duplicate_rows_removed"], "DEDUPLICAÇÃO")
    add("deduplicação", "IDs com diferença apenas na ordem de amenities", duplicate_info["amenities_order_only_ids"], "DEDUPLICAÇÃO")
    add("deduplicação", "IDs com divergência material", duplicate_info["material_divergence_ids"], "bloqueio se > 0")
    for listing_type, count in deduplicated["listing_type"].value_counts(dropna=False).items():
        normalized = normalize_text(listing_type)
        treatment = "FILTRO DE ESCOPO" if normalized not in RESIDENTIAL_TYPES else "universo residencial principal"
        add("escopo", f"Tipo: {listing_type}", count, treatment)
    for original, group in deduplicated.groupby("suburb", dropna=False, sort=True):
        normalized = normalize_text(original)
        label = "<ausente>" if pd.isna(original) else str(original)
        add("normalização de bairro", f"{label} → {normalized}", len(group), "NORMALIZAÇÃO", "Somente caixa, espaços e acentos; subdivisões não são fundidas.")
    rules = [
        ("preço de compra", "Preço inválido", residential["sale_price_invalid"].sum(), "excluído das métricas de preço"),
        ("preço de compra", "Preço abaixo de R$ 100 mil", residential["sale_price_below_100k"].sum(), "FLAG DE QUALIDADE; preservado no principal"),
        ("preço de compra", "Preço fora da cerca externa do segmento", residential["sale_price_tukey_suspect"].sum(), "FLAG DE QUALIDADE; preservado no principal"),
        ("área", "Área ausente/não finita", residential["usable_area_invalid"].sum(), "fora apenas das métricas por m²"),
        ("área", "Área ≤ 0 ou > 1.000 m²", residential["usable_area_suspect"].sum(), "FLAG DE QUALIDADE; fora apenas das métricas por m²"),
        ("condomínio", "Ausente ou zero", residential["condo_unknown"].sum(), "desconhecido; nunca convertido em gratuito"),
        ("condomínio", "Não finito ou negativo", residential["condo_invalid"].sum(), "inválido"),
        ("condomínio", "Custo anual ≥ preço pedido", residential["condo_annual_ge_sale"].sum(), "FLAG DE QUALIDADE"),
        ("condomínio", "Acima da cerca externa do segmento", residential["condo_tukey_suspect"].sum(), "FLAG DE QUALIDADE"),
        ("IPTU", "Ausente ou zero", residential["iptu_unknown"].sum(), "cobertura desconhecida; não descontado"),
        ("IPTU", "Não finito ou negativo", residential["iptu_invalid"].sum(), "inválido; não descontado"),
        ("IPTU", "Valor anual ≥ preço pedido", residential["iptu_suspect"].sum(), "FLAG DE QUALIDADE; não descontado"),
    ]
    for category, item, count, treatment in rules:
        add(category, item, int(count), treatment)
    return pd.DataFrame(rows)


def build_vivareal_segments(residential: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    valid_price = residential.loc[~residential["sale_price_invalid"]].copy()
    for segment_key, group in valid_price.groupby("segment_key", sort=True):
        sale_all = group["sale_price_numeric"]
        sale_clean = group.loc[~group["sale_price_suspect"], "sale_price_numeric"]
        area_group = group.loc[group["usable_area_valid_for_m2"]]
        condo_group = group.loc[group["condo_valid_observed"]]
        iptu_group = group.loc[group["iptu_positive_observed"]]
        advertiser_counts = group["advertiser_name_norm"].value_counts(dropna=False)
        top_advertiser = str(advertiser_counts.index[0]) if len(advertiser_counts) else "desconhecido"
        n = len(group)
        n_condo = len(condo_group)
        rows.append({
            "segment_key": segment_key,
            "segmento_imoveis": group["segmento_imoveis"].iloc[0],
            "suburb_original_variants": " | ".join(sorted(group["suburb_original"].dropna().astype(str).unique())),
            "suburb_norm": group["suburb_norm"].iloc[0],
            "tipo_imovel": group["listing_type_norm"].iloc[0],
            "quartos": group["bedrooms_numeric"].iloc[0],
            "n_vivareal": n,
            "preco_pedido_mediano": median(sale_all),
            "preco_pedido_p25": quantile(sale_all, 0.25),
            "preco_pedido_p75": quantile(sale_all, 0.75),
            "n_preco_compra_suspeito": int(group["sale_price_suspect"].sum()),
            "n_preco_compra_sem_suspeitos": int(len(sale_clean)),
            "preco_pedido_mediano_sem_suspeitos": median(sale_clean),
            "n_area_valida": len(area_group),
            "cobertura_area_valida": len(area_group) / n,
            "area_util_mediana_m2": median(area_group["usable_area_numeric"]),
            "preco_pedido_mediano_m2": median(area_group["sale_price_per_m2"]),
            "n_condominio_valido": n_condo,
            "cobertura_condominio_valido": n_condo / n,
            "condominio_mensal_mediano_valido": median(condo_group["monthly_condo_fee_numeric"]),
            "suporte_condominio": "principal" if n_condo >= 20 else ("exploratório" if n_condo else "sem dado válido"),
            "n_iptu_positivo_observado": len(iptu_group),
            "cobertura_iptu_positivo_observado": len(iptu_group) / n,
            "n_advertisers": int(group["advertiser_name_norm"].nunique(dropna=False)),
            "maior_advertiser": top_advertiser,
            "listings_maior_advertiser": int(advertiser_counts.iloc[0]) if len(advertiser_counts) else 0,
            "participacao_maior_advertiser": float(advertiser_counts.iloc[0] / n) if len(advertiser_counts) else np.nan,
        })
    return pd.DataFrame(rows).sort_values("segment_key", kind="stable").reset_index(drop=True)


def read_airbnb_segments() -> tuple[pd.DataFrame, pd.DataFrame]:
    segments = pd.read_csv(AIRBNB_SEGMENTS_FILE, low_memory=False)
    required = segments.loc[
        (segments["metrica"] == "preco_total")
        & (segments["tratamento_capacidade"] == "não aplicável")
    ].copy()
    headline = required.loc[
        (required["metodo"] == "snapshot_2025_01_20")
        & (required["tratamento_outlier"] == "original")
    ].copy()
    require(not headline["segment_key"].duplicated().any(), "Headline Airbnb não possui uma linha por segmento.")
    calendar = pd.read_csv(AIRBNB_CALENDAR_FILE, low_memory=False)
    require(not calendar["segment_key"].duplicated().any(), "Calendário do Ciclo 1 não possui uma linha por segmento.")
    return required, headline


def build_link_table(headline: pd.DataFrame, viva_segments: pd.DataFrame) -> pd.DataFrame:
    airbnb = headline[[
        "segment_key", "segmento_imoveis", "bairro", "tipo_imovel", "quartos",
        "n_listings", "preco_mediano", "preco_p25", "preco_p75", "n_hosts",
        "participacao_maior_host",
    ]].rename(columns={
        "n_listings": "n_airbnb",
        "preco_mediano": "preco_airbnb_mediano_20_01",
        "preco_p25": "preco_airbnb_p25_20_01",
        "preco_p75": "preco_airbnb_p75_20_01",
    })
    airbnb["_merge_key"] = np.where(
        airbnb["segment_key"].str.startswith("desconhecido|"),
        "airbnb|" + airbnb["segment_key"],
        airbnb["segment_key"],
    )
    viva_segments = viva_segments.copy()
    viva_segments["_merge_key"] = np.where(
        viva_segments["suburb_norm"].eq("desconhecido"),
        "vivareal|" + viva_segments["segment_key"],
        viva_segments["segment_key"],
    )
    linked = airbnb.merge(viva_segments, on="_merge_key", how="outer", suffixes=("_airbnb", "_vivareal"), indicator=True)
    linked["segment_key"] = linked["segment_key_airbnb"].combine_first(linked["segment_key_vivareal"])
    linked["n_airbnb"] = linked["n_airbnb"].fillna(0).astype(int)
    linked["n_vivareal"] = linked["n_vivareal"].fillna(0).astype(int)
    linked["status_ligacao"] = linked["_merge"].map({"both": "segmento correspondente", "left_only": "exclusivo Airbnb", "right_only": "exclusivo VivaReal"}).astype(str)
    linked["suporte_investimento"] = [support_label(a, v) for a, v in zip(linked["n_airbnb"], linked["n_vivareal"])]
    linked["ligacao_individual"] = False
    linked["chave_ligacao"] = "bairro normalizado + tipo residencial + quartos"
    linked = linked.drop(columns=["_merge", "_merge_key", "segment_key_airbnb", "segment_key_vivareal"]).sort_values(["segment_key", "status_ligacao"], kind="stable").reset_index(drop=True)
    return linked


def build_scenarios(linked: pd.DataFrame) -> pd.DataFrame:
    eligible = linked.loc[
        (linked["status_ligacao"] == "segmento correspondente")
        & linked["preco_airbnb_mediano_20_01"].notna()
        & linked["preco_pedido_mediano"].notna()
        & linked["preco_pedido_mediano"].gt(0)
    ].copy()
    rows: list[dict[str, Any]] = []
    for _, segment in eligible.iterrows():
        for occupancy in OCCUPANCIES:
            for seasonality in SEASONAL_FACTORS:
                annualized = segment["preco_airbnb_mediano_20_01"] * seasonality * 365 * occupancy
                gross_yield = annualized / segment["preco_pedido_mediano"]
                condo = segment["condominio_mensal_mediano_valido"]
                after_condo = (
                    (annualized - 12 * condo) / segment["preco_pedido_mediano"]
                    if pd.notna(condo) and segment["n_condominio_valido"] > 0
                    else np.nan
                )
                rows.append({
                    "segment_key": segment["segment_key"],
                    "segmento_imoveis": segment.get("segmento_imoveis_airbnb", segment.get("segmento_imoveis", "")),
                    "suporte_investimento": segment["suporte_investimento"],
                    "n_airbnb": int(segment["n_airbnb"]),
                    "n_vivareal": int(segment["n_vivareal"]),
                    "preco_airbnb_mediano_20_01": segment["preco_airbnb_mediano_20_01"],
                    "preco_pedido_mediano": segment["preco_pedido_mediano"],
                    "n_preco_compra_suspeito": int(segment["n_preco_compra_suspeito"]),
                    "area_util_mediana_m2": segment["area_util_mediana_m2"],
                    "preco_pedido_mediano_m2": segment["preco_pedido_mediano_m2"],
                    "n_advertisers": int(segment["n_advertisers"]),
                    "participacao_maior_advertiser": segment["participacao_maior_advertiser"],
                    "ocupacao_assumida": occupancy,
                    "fator_sazonalidade_assumido": seasonality,
                    "cenario": f"ocupacao_{int(occupancy*100)}pct__sazonalidade_{int(seasonality*100)}pct",
                    "preco_anualizado_no_cenario": annualized,
                    "gross_yield_proxy": gross_yield,
                    "n_condominio_valido": int(segment["n_condominio_valido"]),
                    "cobertura_condominio_valido": segment["cobertura_condominio_valido"],
                    "suporte_condominio": segment["suporte_condominio"],
                    "condominio_mensal_mediano_valido": condo,
                    "yield_apos_condominio_observado": after_condo,
                })
    scenarios = pd.DataFrame(rows)
    main = scenarios["suporte_investimento"].eq("principal")
    scenarios["rank_gross_yield_principal"] = np.nan
    scenarios.loc[main, "rank_gross_yield_principal"] = scenarios.loc[main].groupby("cenario")["gross_yield_proxy"].rank(method="min", ascending=False)
    scenarios["rank_yield_apos_condominio_principal"] = np.nan
    main_condo = main & scenarios["yield_apos_condominio_observado"].notna() & scenarios["suporte_condominio"].eq("principal")
    scenarios.loc[main_condo, "rank_yield_apos_condominio_principal"] = scenarios.loc[main_condo].groupby("cenario")["yield_apos_condominio_observado"].rank(method="min", ascending=False)
    return scenarios.sort_values(["segment_key", "ocupacao_assumida", "fator_sazonalidade_assumido"], kind="stable").reset_index(drop=True)


def get_airbnb_sensitivity(segments: pd.DataFrame, method: str, outlier: str) -> pd.DataFrame:
    frame = segments.loc[(segments["metodo"] == method) & (segments["tratamento_outlier"] == outlier)].copy()
    require(not frame["segment_key"].duplicated().any(), f"Sensibilidade Airbnb duplicada: {method}/{outlier}")
    return frame[["segment_key", "n_listings", "preco_mediano"]].rename(columns={"n_listings": "n_airbnb_sensibilidade", "preco_mediano": "preco_airbnb_sensibilidade"})


def build_robustness(linked: pd.DataFrame, airbnb_segments: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    base = linked.loc[
        (linked["status_ligacao"] == "segmento correspondente")
        & linked["preco_airbnb_mediano_20_01"].notna()
        & linked["preco_pedido_mediano"].gt(0)
    ].copy()
    sensitivity_specs = [
        ("headline", "Preço Airbnb 20/01 + compra mediana", "snapshot_2025_01_20", "original", "preco_pedido_mediano", False),
        ("airbnb_mediana_capturas", "Mediana Airbnb entre capturas", "median_across_captures", "original", "preco_pedido_mediano", False),
        ("airbnb_sem_precos_10k", "Airbnb sem preços ≥ R$ 10 mil", "snapshot_2025_01_20", "exclude_suspicious_prices", "preco_pedido_mediano", False),
        ("airbnb_sem_listings_afetados", "Airbnb sem os três imóveis afetados", "snapshot_2025_01_20", "exclude_affected_listings", "preco_pedido_mediano", False),
        ("compra_p25", "Preço de compra p25", "snapshot_2025_01_20", "original", "preco_pedido_p25", False),
        ("compra_p75", "Preço de compra p75", "snapshot_2025_01_20", "original", "preco_pedido_p75", False),
        ("compra_sem_suspeitos", "Compra mediana sem preços suspeitos", "snapshot_2025_01_20", "original", "preco_pedido_mediano_sem_suspeitos", False),
        ("apos_condominio", "Após condomínio observado", "snapshot_2025_01_20", "original", "preco_pedido_mediano", True),
    ]
    rows: list[pd.DataFrame] = []
    multiplier = INTERMEDIATE_OCCUPANCY * INTERMEDIATE_SEASONALITY * 365
    for code, label, method, outlier, purchase_col, subtract_condo in sensitivity_specs:
        airbnb = get_airbnb_sensitivity(airbnb_segments, method, outlier)
        frame = base.merge(airbnb, on="segment_key", how="left", validate="one_to_one")
        frame["preco_compra_sensibilidade"] = frame[purchase_col]
        frame["preco_anualizado_no_cenario"] = frame["preco_airbnb_sensibilidade"] * multiplier
        if subtract_condo:
            frame["metrica_retorno"] = "yield após condomínio observado"
            frame["yield_sensibilidade"] = np.where(
                frame["condominio_mensal_mediano_valido"].notna(),
                (frame["preco_anualizado_no_cenario"] - 12 * frame["condominio_mensal_mediano_valido"]) / frame["preco_compra_sensibilidade"],
                np.nan,
            )
        else:
            frame["metrica_retorno"] = "gross yield proxy"
            frame["yield_sensibilidade"] = frame["preco_anualizado_no_cenario"] / frame["preco_compra_sensibilidade"]
        frame["sensibilidade"] = code
        frame["sensibilidade_label"] = label
        rows.append(frame)

    calendar_frame = base.merge(
        calendar[["segment_key", "n_listings", "preco_mediano_ajustado_calendario"]].rename(columns={"n_listings": "n_airbnb_sensibilidade", "preco_mediano_ajustado_calendario": "preco_airbnb_sensibilidade"}),
        on="segment_key", how="left", validate="one_to_one",
    )
    calendar_frame["preco_compra_sensibilidade"] = calendar_frame["preco_pedido_mediano"]
    calendar_frame["preco_anualizado_no_cenario"] = calendar_frame["preco_airbnb_sensibilidade"] * multiplier
    calendar_frame["metrica_retorno"] = "gross yield proxy"
    calendar_frame["yield_sensibilidade"] = calendar_frame["preco_anualizado_no_cenario"] / calendar_frame["preco_compra_sensibilidade"]
    calendar_frame["sensibilidade"] = "airbnb_ajuste_calendario"
    calendar_frame["sensibilidade_label"] = "Airbnb com ajuste de calendário aprovado"
    rows.append(calendar_frame)

    robustness = pd.concat(rows, ignore_index=True)
    robustness["ocupacao_assumida"] = INTERMEDIATE_OCCUPANCY
    robustness["fator_sazonalidade_assumido"] = INTERMEDIATE_SEASONALITY
    robustness["rank_segmentos_principais"] = np.nan
    ranking_scope = (
        robustness["suporte_investimento"].eq("principal")
        & robustness["yield_sensibilidade"].notna()
        & (
            robustness["sensibilidade"].ne("apos_condominio")
            | robustness["suporte_condominio"].eq("principal")
        )
    )
    robustness.loc[ranking_scope, "rank_segmentos_principais"] = robustness.loc[ranking_scope].groupby("sensibilidade")["yield_sensibilidade"].rank(method="min", ascending=False)
    columns = [
        "segment_key", "segmento_imoveis_airbnb", "suporte_investimento", "n_airbnb", "n_vivareal",
        "sensibilidade", "sensibilidade_label", "metrica_retorno", "n_airbnb_sensibilidade",
        "preco_airbnb_sensibilidade", "preco_compra_sensibilidade", "preco_anualizado_no_cenario",
        "yield_sensibilidade", "n_condominio_valido", "cobertura_condominio_valido", "suporte_condominio",
        "ocupacao_assumida", "fator_sazonalidade_assumido", "rank_segmentos_principais",
    ]
    return robustness[columns].rename(columns={"segmento_imoveis_airbnb": "segmento_imoveis"}).sort_values(["sensibilidade", "segment_key"], kind="stable").reset_index(drop=True)


def add_check(rows: list[dict[str, Any]], name: str, actual: Any, expected: Any, passed: bool, notes: str = "") -> None:
    rows.append({"check": name, "actual": actual, "expected": expected, "status": "OK" if passed else "FALHOU", "observacao": notes})


def build_checks(raw: pd.DataFrame, deduplicated: pd.DataFrame, residential: pd.DataFrame, duplicate_info: dict[str, int], linked: pd.DataFrame, scenarios: pd.DataFrame, robustness: pd.DataFrame, raw_hashes_before: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    add_check(rows, "8.293 IDs únicos após deduplicação", deduplicated["listing_id"].nunique(), 8_293, deduplicated["listing_id"].nunique() == 8_293)
    add_check(rows, "Uma linha por listing_id na base residencial processada", int(residential.duplicated("listing_id").sum()), 0, not residential.duplicated("listing_id").any())
    add_check(rows, "Nenhuma divergência material escondida nas duplicações", duplicate_info["material_divergence_ids"], 0, duplicate_info["material_divergence_ids"] == 0)
    add_check(rows, "Somente apartamentos e casas no universo principal", sorted(residential["listing_type_norm"].unique().tolist()), sorted(RESIDENTIAL_TYPES), set(residential["listing_type_norm"].unique()) == RESIDENTIAL_TYPES)
    add_check(rows, "Nenhuma ligação individual Airbnb–VivaReal", bool(linked["ligacao_individual"].any()), False, not linked["ligacao_individual"].any(), "Única chave: bairro normalizado + tipo residencial + quartos.")
    add_check(rows, "Uma linha por segmento e cenário econômico", int(scenarios.duplicated(["segment_key", "cenario"]).sum()), 0, not scenarios.duplicated(["segment_key", "cenario"]).any())
    combinations = scenarios[["ocupacao_assumida", "fator_sazonalidade_assumido"]].drop_duplicates()
    add_check(rows, "Exatamente nove combinações de ocupação e sazonalidade", len(combinations), 9, len(combinations) == 9)
    annual_error = (scenarios["preco_anualizado_no_cenario"] - scenarios["preco_airbnb_mediano_20_01"] * scenarios["fator_sazonalidade_assumido"] * 365 * scenarios["ocupacao_assumida"]).abs().max()
    yield_error = (scenarios["gross_yield_proxy"] - scenarios["preco_anualizado_no_cenario"] / scenarios["preco_pedido_mediano"]).abs().max()
    condo_expected = (scenarios["preco_anualizado_no_cenario"] - 12 * scenarios["condominio_mensal_mediano_valido"]) / scenarios["preco_pedido_mediano"]
    condo_error = (scenarios.loc[scenarios["yield_apos_condominio_observado"].notna(), "yield_apos_condominio_observado"] - condo_expected.loc[scenarios["yield_apos_condominio_observado"].notna()]).abs().max()
    add_check(rows, "Fórmula do preço anualizado reconciliada", float(annual_error), 0.0, annual_error <= 1e-12)
    add_check(rows, "Fórmula do gross yield proxy reconciliada", float(yield_error), 0.0, yield_error <= 1e-12)
    add_check(rows, "Fórmula do yield após condomínio reconciliada", float(condo_error), 0.0, condo_error <= 1e-12)
    expected_support = pd.Series([support_label(a, v) for a, v in zip(linked["n_airbnb"], linked["n_vivareal"])], index=linked.index)
    support_mismatch = int((expected_support != linked["suporte_investimento"]).sum())
    add_check(rows, "Suporte principal e exploratório classificado automaticamente", support_mismatch, 0, support_mismatch == 0)
    add_check(rows, "Bairro original e normalizado preservados", all(column in residential.columns for column in ["suburb_original", "suburb_norm"]), True, all(column in residential.columns for column in ["suburb_original", "suburb_norm"]))
    suspect_count = int(residential["sale_price_suspect"].sum())
    segment_suspect_count = int(linked["n_preco_compra_suspeito"].fillna(0).sum())
    add_check(rows, "Preços suspeitos preservados no principal", segment_suspect_count, suspect_count, segment_suspect_count == suspect_count)
    clean_rows = robustness.loc[robustness["sensibilidade"] == "compra_sem_suspeitos"]
    add_check(rows, "Preços suspeitos retirados somente na sensibilidade", len(clean_rows), int((linked["status_ligacao"] == "segmento correspondente").sum()), len(clean_rows) == int((linked["status_ligacao"] == "segmento correspondente").sum()))
    condo_unknown_valid = int((residential["condo_unknown"] & residential["condo_valid_observed"]).sum())
    add_check(rows, "Condomínio desconhecido não tratado como zero", condo_unknown_valid, 0, condo_unknown_valid == 0)
    after_hashes = {path.name: sha256(path) for path in RAW_FILES}
    add_check(rows, "Hashes dos CSVs originais preservados", after_hashes == raw_hashes_before, True, after_hashes == raw_hashes_before)
    scenario_order = scenarios.sort_values(["segment_key", "ocupacao_assumida", "fator_sazonalidade_assumido"], kind="stable").reset_index(drop=True)
    robustness_order = robustness.sort_values(["sensibilidade", "segment_key"], kind="stable").reset_index(drop=True)
    deterministic_order = scenarios.equals(scenario_order) and robustness.equals(robustness_order)
    add_check(rows, "Ordenação determinística dos artefatos econômicos", deterministic_order, True, deterministic_order, "A repetição integral também é verificada após a execução.")
    git_result = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    add_check(rows, "git diff --check aprovado", git_result.returncode, 0, git_result.returncode == 0, git_result.stdout + git_result.stderr)
    checks = pd.DataFrame(rows)
    require((checks["status"] == "OK").all(), "Checks críticos falharam:\n" + checks.loc[checks["status"] != "OK"].to_string(index=False))
    return checks


def fmt_money(value: Any, decimals: int = 0) -> str:
    if pd.isna(value):
        return "—"
    text = f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def fmt_pct(value: Any, decimals: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value) * 100:.{decimals}f}%".replace(".", ",")


def markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    if frame.empty:
        return "_Sem registros._"
    header = "| " + " | ".join(label for _, label in columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, separator]
    for _, row in frame.iterrows():
        values = []
        for column, _ in columns:
            value = row[column]
            if column == "faixa_gross_yield_proxy":
                values.append(str(value))
            elif "yield" in column or "cobertura" in column or "participacao" in column:
                values.append(fmt_pct(value))
            elif column == "faixa_diferenca_pp":
                values.append(str(value))
            elif "diferenca_pp" in column:
                values.append(f"{float(value):.2f}".replace(".", ",") + " p.p.")
            elif column.startswith("n_"):
                values.append(str(int(value)))
            elif column.startswith("suporte"):
                values.append(str(value))
            elif "preco" in column or "condominio" in column:
                values.append(fmt_money(value))
            elif isinstance(value, (float, np.floating)) and float(value).is_integer():
                values.append(str(int(value)))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def summarize(linked: pd.DataFrame, scenarios: pd.DataFrame, robustness: pd.DataFrame, checks: pd.DataFrame, quality: pd.DataFrame) -> tuple[str, dict[str, Any]]:
    intermediate = scenarios.loc[
        (scenarios["ocupacao_assumida"] == INTERMEDIATE_OCCUPANCY)
        & (scenarios["fator_sazonalidade_assumido"] == INTERMEDIATE_SEASONALITY)
        & (scenarios["suporte_investimento"] == "principal")
    ].sort_values("gross_yield_proxy", ascending=False).copy()
    require(len(intermediate), "Nenhum segmento possui suporte principal para recomendação.")
    leader = intermediate.iloc[0]
    intermediate["diferenca_pp_para_lider"] = (leader["gross_yield_proxy"] - intermediate["gross_yield_proxy"]) * 100
    intermediate["faixa_gross_yield_proxy"] = intermediate["segment_key"].map(
        scenarios.groupby("segment_key")["gross_yield_proxy"].agg(lambda values: f"{fmt_pct(values.min())}–{fmt_pct(values.max())}")
    )

    main_robust = robustness.loc[robustness["suporte_investimento"] == "principal"].copy()
    sensitivity_winners = main_robust.loc[main_robust["rank_segmentos_principais"] == 1].copy()
    winner_by_sensitivity = sensitivity_winners.groupby("sensibilidade")["segment_key"].agg(lambda values: " | ".join(sorted(set(values))))
    leader_wins = int(winner_by_sensitivity.eq(leader["segment_key"]).sum())
    robust_leader = leader_wins == len(winner_by_sensitivity)

    target_robust = robustness.loc[robustness["segment_key"] == TARGET].copy()
    compact_results: list[dict[str, Any]] = []
    for comparator in COMPARATORS:
        target_rows = target_robust[["sensibilidade", "yield_sensibilidade"]].rename(columns={"yield_sensibilidade": "yield_target"})
        comparator_rows = robustness.loc[robustness["segment_key"] == comparator, ["sensibilidade", "yield_sensibilidade", "suporte_investimento"]].rename(columns={"yield_sensibilidade": "yield_comparator", "suporte_investimento": "support_comparator"})
        comparison = target_rows.merge(comparator_rows, on="sensibilidade", how="inner")
        comparison["delta"] = comparison["yield_target"] - comparison["yield_comparator"]
        valid = comparison.dropna(subset=["delta"])
        compact_results.append({
            "comparator": comparator,
            "support": valid["support_comparator"].iloc[0] if len(valid) else "ausente",
            "headline_delta": float(valid.loc[valid["sensibilidade"] == "headline", "delta"].iloc[0]) if (valid["sensibilidade"] == "headline").any() else np.nan,
            "min_delta": float(valid["delta"].min()) if len(valid) else np.nan,
            "max_delta": float(valid["delta"].max()) if len(valid) else np.nan,
            "direction_preserved": bool(len(valid) and ((valid["delta"] > 0).all() or (valid["delta"] < 0).all())),
            "all_positive": bool(len(valid) and (valid["delta"] > 0).all()),
        })
    compact_frame = pd.DataFrame(compact_results)
    larger = compact_frame[compact_frame["comparator"].isin(COMPARATORS[1:])]
    compact_economic_favorable = bool(len(larger) == 2 and larger["all_positive"].all())
    if compact_economic_favorable:
        compact_status = "favorável"
    elif len(larger) == 2 and (larger["max_delta"] < 0).all():
        compact_status = "evidência contrária"
    else:
        compact_status = "inconclusivo"

    if robust_leader:
        recommendation = f"{leader['segmento_imoveis']}"
        recommendation_text = f"Recomendação provisória: **{recommendation}**, líder entre os segmentos principais no cenário intermediário ilustrativo e em todas as sensibilidades avaliadas."
    else:
        alternatives = intermediate.head(3)["segmento_imoveis"].tolist()
        recommendation = alternatives
        recommendation_text = "Não há vencedor único robusto. Alternativas provisórias: **" + "; ".join(alternatives) + "**."

    headline_rows = robustness.loc[robustness["sensibilidade"] == "headline", ["segment_key", "yield_sensibilidade"]].set_index("segment_key")
    direct_rows = []
    for item in compact_results:
        comparator = item["comparator"]
        if TARGET in headline_rows.index and comparator in headline_rows.index:
            target_yield = float(headline_rows.loc[TARGET, "yield_sensibilidade"])
            comparator_yield = float(headline_rows.loc[comparator, "yield_sensibilidade"])
            comparator_name_rows = robustness.loc[robustness["segment_key"] == comparator, "segmento_imoveis"]
            comparator_name = comparator_name_rows.iloc[0] if len(comparator_name_rows) else comparator
            direct_rows.append({
                "comparacao": f"Centro · apartamento · 1 quarto − {comparator_name}",
                "yield_centro_1q": target_yield,
                "yield_comparador": comparator_yield,
                "diferenca_pp": (target_yield - comparator_yield) * 100,
                "faixa_diferenca_pp": f"{item['min_delta']*100:.2f} a {item['max_delta']*100:.2f}".replace(".", ","),
                "suporte": item["support"],
            })
    direct = pd.DataFrame(direct_rows)

    winner_table = sensitivity_winners[["sensibilidade_label", "metrica_retorno", "segmento_imoveis", "yield_sensibilidade"]].sort_values("sensibilidade_label", kind="stable")

    link_counts = linked["status_ligacao"].value_counts().to_dict()
    represented = linked.groupby("status_ligacao")[["n_airbnb", "n_vivareal"]].sum().reset_index()
    excluded_types = quality.loc[(quality["categoria"] == "escopo") & quality["tratamento"].eq("FILTRO DE ESCOPO")]
    lines = [
        "# Ciclo 3 — mercado de compra e estimativa simples de retorno",
        "",
        "## Decisão econômica provisória",
        "",
        recommendation_text,
        "",
        f"No cenário intermediário meramente ilustrativo (45% de ocupação e 80% do preço observado), o líder registra **{fmt_pct(leader['gross_yield_proxy'])} de gross yield proxy**, com preço anunciado típico de **{fmt_money(leader['preco_airbnb_mediano_20_01'])}** e preço pedido mediano de **{fmt_money(leader['preco_pedido_mediano'])}**. A faixa nos nove testes de estresse é **{intermediate.iloc[0]['faixa_gross_yield_proxy']}**; nenhum dos nove cenários é tratado como mais provável.",
        "",
        "## Ranking econômico dos segmentos principais",
        "",
        markdown_table(intermediate, [
            ("segmento_imoveis", "Segmento de imóveis"), ("n_airbnb", "Airbnb"), ("n_vivareal", "VivaReal"),
            ("preco_airbnb_mediano_20_01", "Preço Airbnb"), ("preco_pedido_mediano", "Preço pedido"),
            ("n_preco_compra_suspeito", "Preços compra sinalizados"),
            ("area_util_mediana_m2", "Área mediana válida"), ("preco_pedido_mediano_m2", "Preço pedido/m²"),
            ("n_advertisers", "Anunciantes"), ("participacao_maior_advertiser", "Maior anunciante"),
            ("gross_yield_proxy", "Gross yield proxy"), ("diferenca_pp_para_lider", "Distância do líder"),
            ("faixa_gross_yield_proxy", "Faixa 9 cenários"), ("cobertura_condominio_valido", "Cobertura condomínio"),
            ("n_condominio_valido", "n condomínio"), ("suporte_condominio", "Suporte condomínio"),
            ("yield_apos_condominio_observado", "Yield após condomínio observado"),
        ]),
        "",
        "O ranking de gross yield proxy é idêntico nos nove pares ocupação × sazonalidade porque o multiplicador é comum aos segmentos. Mudanças de ranking, quando existem, vêm das sensibilidades de preço do Airbnb, preço de compra e condomínio, não da escolha entre esses nove multiplicadores.",
        "",
        "### Liderança nas sensibilidades",
        "",
        markdown_table(winner_table, [
            ("sensibilidade_label", "Sensibilidade"), ("metrica_retorno", "Métrica"),
            ("segmento_imoveis", "Líder"), ("yield_sensibilidade", "Yield no cenário intermediário"),
        ]),
        "",
        "## Tese econômica dos compactos",
        "",
        f"O componente econômico é **{compact_status}**. A comparação de Centro/1 quarto com apartamentos maiores no Centro usa gross yield proxy; a localização Centro versus Meia Praia/1 quarto continua exploratória devido ao suporte do Airbnb em Meia Praia.",
        "",
        markdown_table(direct, [
            ("comparacao", "Comparação"), ("yield_centro_1q", "Centro/1 quarto"), ("yield_comparador", "Comparador"),
            ("diferenca_pp", "Diferença"), ("faixa_diferenca_pp", "Faixa nas sensibilidades (p.p.)"), ("suporte", "Suporte"),
        ]),
        "",
        "O Ciclo 2 encontrou vantagem apenas na densidade de preço anunciado por capacidade declarada. Este ciclo pergunta se o menor preço pedido preserva essa direção econômica; não transforma preço por hóspede ou por quarto em demanda, ocupação ou retorno.",
        "",
        "## Cobertura e ligação agregada",
        "",
        f"Após deduplicar 8.329 linhas em 8.293 IDs, o universo residencial contém {len(pd.read_csv(VIVAREAL_OUTPUT)) if VIVAREAL_OUTPUT.exists() else '—'} anúncios derivados. Foram encontrados {link_counts.get('segmento correspondente', 0)} segmentos correspondentes, {link_counts.get('exclusivo Airbnb', 0)} exclusivos do Airbnb e {link_counts.get('exclusivo VivaReal', 0)} exclusivos do VivaReal.",
        "",
        markdown_table(represented, [("status_ligacao", "Situação"), ("n_airbnb", "Anúncios Airbnb"), ("n_vivareal", "Anúncios VivaReal")]),
        "",
        "A ligação é exclusivamente agregada por bairro normalizado + tipo residencial + quartos. Não há correspondência entre anúncios individuais, títulos ou IDs. Bairros ausentes permanecem `desconhecido`; subdivisões não foram fundidas.",
        "",
        "## Preparação e qualidade do VivaReal",
        "",
        markdown_table(excluded_types, [("item", "Categoria fora do escopo"), ("registros", "Anúncios deduplicados"), ("tratamento", "Tratamento")]),
        "",
        "Preços pedidos suspeitos foram preservados no resultado principal e retirados somente na sensibilidade. Áreas suspeitas ficam fora apenas das métricas por m². Condomínio ausente ou zero é desconhecido, nunca gratuito. IPTU não foi descontado.",
        "",
        "## Limitações capazes de mudar a decisão",
        "",
        "- O preço Airbnb é anunciado, cobre datas entre janeiro e abril e não informa ocupação observada, taxas ou valor efetivamente recebido.",
        "- Ocupação e sazonalidade são premissas de teste de estresse; o preço anualizado no cenário não é receita realizada.",
        "- O preço VivaReal é pedido, não transacionado, e os imóveis das duas plataformas não são os mesmos; padrão, área e capacidade podem diferir dentro do segmento.",
        "- Gross yield proxy não inclui vacância observada, gestão, limpeza, manutenção, mobília, impostos, custos de aquisição, capex ou financiamento.",
        "- Yield após condomínio observado usa apenas anúncios com condomínio positivo e não suspeito; cobertura seletiva pode mudar a comparação.",
        "- IPTU foi apenas auditado e não descontado. Área existe somente no VivaReal e preço por m² é contexto, não denominador comum com o Airbnb.",
        "- Segmentos pequenos podem aparecer como exploratórios, mas não fundamentam a recomendação principal.",
        "",
        "## Checks",
        "",
        f"{int((checks['status'] == 'OK').sum())} de {len(checks)} checks críticos foram aprovados. A execução não fez matching individual, não produziu retorno líquido e não alterou os CSVs originais.",
    ]
    summary = {
        "provisional_recommendation": recommendation,
        "robust_single_leader": robust_leader,
        "leader_segment": leader["segment_key"],
        "leader_intermediate_gross_yield_proxy": float(leader["gross_yield_proxy"]),
        "leader_sensitivity_wins": leader_wins,
        "sensitivity_count": int(len(winner_by_sensitivity)),
        "compact_economic_status": compact_status,
        "compact_comparisons": [{key: json_value(value) for key, value in row.items()} for row in compact_results],
        "link_coverage": {key: int(value) for key, value in link_counts.items()},
    }
    return "\n".join(lines) + "\n", summary


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    raw_hashes = {path.name: sha256(path) for path in RAW_FILES}
    raw = read_vivareal()
    deduplicated, duplicate_info = validate_and_deduplicate(raw)
    residential = prepare_vivareal(deduplicated)
    quality = build_quality(raw, deduplicated, residential, duplicate_info)
    viva_segments = build_vivareal_segments(residential)
    airbnb_segments, airbnb_headline = read_airbnb_segments()
    calendar = pd.read_csv(AIRBNB_CALENDAR_FILE, low_memory=False)
    linked = build_link_table(airbnb_headline, viva_segments)
    scenarios = build_scenarios(linked)
    robustness = build_robustness(linked, airbnb_segments, calendar)

    residential.to_csv(VIVAREAL_OUTPUT, index=False)
    quality.to_csv(QUALITY_OUTPUT, index=False)
    viva_segments.to_csv(VIVAREAL_SEGMENTS_OUTPUT, index=False)
    linked.to_csv(LINK_OUTPUT, index=False)
    scenarios.to_csv(SCENARIOS_OUTPUT, index=False)
    robustness.to_csv(ROBUSTNESS_OUTPUT, index=False)

    checks = build_checks(raw, deduplicated, residential, duplicate_info, linked, scenarios, robustness, raw_hashes)
    checks.to_csv(CHECKS_OUTPUT, index=False)
    report, report_summary = summarize(linked, scenarios, robustness, checks, quality)
    REPORT_OUTPUT.write_text(report, encoding="utf-8")
    summary = {
        "scope": {
            "individual_matching": False,
            "join_grain": "bairro normalizado + tipo residencial + quartos",
            "return_metric": "gross yield proxy",
            "occupancy_observed": False,
            "seasonality_observed_for_full_year": False,
        },
        "assumptions": {
            "occupancy": list(OCCUPANCIES),
            "seasonality_factors": list(SEASONAL_FACTORS),
            "intermediate_illustrative": {"occupancy": INTERMEDIATE_OCCUPANCY, "seasonality": INTERMEDIATE_SEASONALITY},
        },
        "source_hashes": raw_hashes,
        "counts": {
            "vivareal_raw_rows": len(raw),
            "vivareal_unique_ids": deduplicated["listing_id"].nunique(),
            "vivareal_residential_rows": len(residential),
            "linked_segment_rows": int((linked["status_ligacao"] == "segmento correspondente").sum()),
            "scenario_rows": len(scenarios),
            "robustness_rows": len(robustness),
        },
        "results": report_summary,
        "checks": {"passed": int((checks["status"] == "OK").sum()), "total": len(checks), "all_passed": bool((checks["status"] == "OK").all())},
    }
    SUMMARY_OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Ciclo 3 concluído: {len(checks)}/{len(checks)} checks OK; {len(scenarios)} linhas de cenários.")


if __name__ == "__main__":
    main()
