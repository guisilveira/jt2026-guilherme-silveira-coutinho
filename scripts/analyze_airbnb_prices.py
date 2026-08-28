#!/usr/bin/env python3
"""Prepara e compara preços anunciados do Airbnb em Itapema.

Escopo deliberado deste ciclo:
- usa somente Details, Mesh e Price_AV;
- não estima ocupação, receita ou retorno;
- não interpreta ausência de linha como reserva ou disponibilidade;
- preserva os CSVs originais e grava apenas tabelas derivadas.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GENERATED_DIR = ROOT / "reports" / "generated"

DETAILS_FILE = DATA_DIR / "Details_Itapema.csv"
MESH_FILE = DATA_DIR / "Mesh_Ids_Data_Itapema.csv"
PRICE_FILE = DATA_DIR / "Price_AV_Itapema.csv"

LISTING_OUTPUT = PROCESSED_DIR / "airbnb_listing_prices.csv"
SEGMENT_OUTPUT = GENERATED_DIR / "airbnb_price_cohorts.csv"
COVERAGE_OUTPUT = GENERATED_DIR / "airbnb_price_coverage.csv"
CALENDAR_OUTPUT = GENERATED_DIR / "airbnb_price_calendar.csv"
CHECKS_OUTPUT = GENERATED_DIR / "airbnb_price_checks.csv"
TRANSFORMATIONS_OUTPUT = GENERATED_DIR / "airbnb_price_transformations.csv"
SUMMARY_OUTPUT = GENERATED_DIR / "airbnb_price_summary.json"

ID = "airbnb_listing_id"
MAIN_CAPTURE = pd.Timestamp("2025-01-20")
SUSPICIOUS_PRICE_THRESHOLD = 10_000.0
PRIMARY_AIRBNB_MIN = 30
EXPLORATORY_AIRBNB_MIN = 10
BOOTSTRAP_ITERATIONS = 1_000

METHODS = {
    "snapshot_2025_01_20": "Captura de 20/01",
    "latest_available": "Preço mais recente",
    "median_across_captures": "Mediana entre capturas",
}

VARIANTS = {
    "original": "Valores originais",
    "exclude_suspicious_prices": "Sem preços ≥ 10 mil",
    "exclude_affected_listings": "Sem os três imóveis afetados",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
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


def support_label(n_listings: int) -> str:
    if n_listings >= PRIMARY_AIRBNB_MIN:
        return "principal no Airbnb"
    if n_listings >= EXPLORATORY_AIRBNB_MIN:
        return "exploratório no Airbnb"
    return "evidência insuficiente no Airbnb"


def spearman_correlation(left: pd.Series, right: pd.Series) -> float:
    """Calcula Spearman como Pearson dos ranks, sem depender de scipy."""
    aligned = pd.concat([left, right], axis=1).dropna()
    if len(aligned) < 2:
        return np.nan
    ranked = aligned.rank(method="average")
    return float(ranked.iloc[:, 0].corr(ranked.iloc[:, 1], method="pearson"))


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    details = pd.read_csv(
        DETAILS_FILE,
        dtype={ID: "string", "owner_id": "string"},
        low_memory=False,
    )
    mesh = pd.read_csv(MESH_FILE, dtype={ID: "string"}, low_memory=False)
    price = pd.read_csv(PRICE_FILE, dtype={ID: "string"}, low_memory=False)

    price["stay_date"] = pd.to_datetime(price["date"], errors="coerce").dt.normalize()
    price["capture_timestamp"] = pd.to_datetime(
        price["aquisition_date"], errors="coerce"
    )
    price["capture_day"] = price["capture_timestamp"].dt.normalize()
    price["price_numeric"] = pd.to_numeric(price["price"], errors="coerce")
    price["is_suspicious_price"] = (
        price["price_numeric"] >= SUSPICIOUS_PRICE_THRESHOLD
    )
    return details, mesh, price


def build_listing_base(
    details: pd.DataFrame, mesh: pd.DataFrame, price: pd.DataFrame
) -> pd.DataFrame:
    assert details[ID].notna().all() and details[ID].is_unique
    assert mesh[ID].notna().all() and mesh[ID].is_unique
    assert set(details[ID]) == set(mesh[ID])

    mesh_columns = [ID, "suburb", "latitude", "longitude"]
    base = details.merge(
        mesh[mesh_columns],
        on=ID,
        how="left",
        validate="one_to_one",
        suffixes=("_details", "_mesh"),
    )
    assert len(base) == len(details)

    base["suburb_norm"] = base["suburb"].map(normalize_text)
    display_by_norm = (
        base.loc[base["suburb_norm"] != "desconhecido"]
        .groupby("suburb_norm")["suburb"]
        .agg(lambda series: series.dropna().astype(str).str.strip().mode().iloc[0])
        .to_dict()
    )
    base["bairro"] = base["suburb_norm"].map(display_by_norm).fillna("Desconhecido")
    base["tipo_imovel"] = base["listing_type"].map(normalize_text)
    base["quartos"] = pd.to_numeric(base["number_of_bedrooms"], errors="coerce")
    base["quartos_label"] = base["quartos"].map(bedroom_label)
    base["segmento_imoveis"] = (
        base["bairro"].astype(str)
        + " · "
        + base["tipo_imovel"].astype(str)
        + " · "
        + base["quartos_label"].astype(str)
    )
    base["segment_key"] = (
        base["suburb_norm"].astype(str)
        + "|"
        + base["tipo_imovel"].astype(str)
        + "|"
        + base["quartos_label"].astype(str)
    )
    base["residential_scope"] = base["tipo_imovel"].isin(["apartamento", "casa"])

    price_ids = set(price[ID].dropna())
    capture_20_ids = set(price.loc[price["capture_day"] == MAIN_CAPTURE, ID].dropna())
    base["has_any_price"] = base[ID].isin(price_ids)
    base["has_snapshot_20_price"] = base[ID].isin(capture_20_ids)
    return base


def filter_variant(
    price: pd.DataFrame, variant: str, affected_listing_ids: set[str]
) -> pd.DataFrame:
    if variant == "original":
        return price.copy()
    if variant == "exclude_suspicious_prices":
        return price.loc[~price["is_suspicious_price"]].copy()
    if variant == "exclude_affected_listings":
        return price.loc[~price[ID].isin(affected_listing_ids)].copy()
    raise ValueError(f"Tratamento desconhecido: {variant}")


def build_pair_table(price: pd.DataFrame, method: str) -> pd.DataFrame:
    columns = [ID, "stay_date", "price_numeric"]
    if method == "snapshot_2025_01_20":
        pair = price.loc[price["capture_day"] == MAIN_CAPTURE, columns].copy()
    elif method == "latest_available":
        pair = (
            price.sort_values([ID, "stay_date", "capture_day", "capture_timestamp"])
            .drop_duplicates([ID, "stay_date"], keep="last")
            [columns]
            .copy()
        )
    elif method == "median_across_captures":
        pair = (
            price.groupby([ID, "stay_date"], as_index=False)["price_numeric"]
            .median()
            .copy()
        )
    else:
        raise ValueError(f"Método desconhecido: {method}")

    assert not pair.duplicated([ID, "stay_date"]).any()
    pair = pair.dropna(subset=[ID, "stay_date", "price_numeric"])
    pair["is_weekend"] = pair["stay_date"].dt.dayofweek >= 5
    pair["stay_month"] = pair["stay_date"].dt.month
    return pair


def aggregate_listing(pair: pd.DataFrame) -> pd.DataFrame:
    def month_share(series: pd.Series, month: int) -> float:
        return float((series == month).mean()) if len(series) else np.nan

    grouped = pair.groupby(ID, as_index=False).agg(
        preco_anunciado_tipico=("price_numeric", "median"),
        n_datas_estadia=("stay_date", "nunique"),
        primeira_data_estadia=("stay_date", "min"),
        ultima_data_estadia=("stay_date", "max"),
        proporcao_fim_semana=("is_weekend", "mean"),
    )
    month_table = (
        pair.groupby(ID)["stay_month"]
        .agg(
            proporcao_janeiro=lambda series: month_share(series, 1),
            proporcao_fevereiro=lambda series: month_share(series, 2),
            proporcao_marco=lambda series: month_share(series, 3),
            proporcao_abril=lambda series: month_share(series, 4),
        )
        .reset_index()
    )
    listing = grouped.merge(month_table, on=ID, validate="one_to_one")
    assert listing[ID].is_unique
    return listing


def deterministic_seed(*parts: str) -> int:
    payload = "|".join(parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:8], 16)


def bootstrap_median_interval(
    values: pd.Series, seed: int, iterations: int = BOOTSTRAP_ITERATIONS
) -> tuple[float, float]:
    array = values.dropna().to_numpy(dtype=float)
    if len(array) < 5:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(iterations, len(array)), replace=True)
    medians = np.median(samples, axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def build_listing_methods(
    listing_base: pd.DataFrame,
    matched_price: pd.DataFrame,
    affected_listing_ids: set[str],
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    base_columns = [
        ID,
        "owner_id",
        "bairro",
        "suburb_norm",
        "tipo_imovel",
        "quartos",
        "quartos_label",
        "segmento_imoveis",
        "segment_key",
        "number_of_guests",
        "residential_scope",
    ]
    base = listing_base[base_columns]
    long_frames: list[pd.DataFrame] = []
    pair_tables: dict[tuple[str, str], pd.DataFrame] = {}

    suspicious_counts = (
        matched_price.groupby(ID)["is_suspicious_price"]
        .agg(n_precos_suspeitos="sum", possui_preco_suspeito="any")
        .reset_index()
    )

    for method in METHODS:
        for variant in VARIANTS:
            filtered = filter_variant(matched_price, variant, affected_listing_ids)
            pair = build_pair_table(filtered, method)
            pair_tables[(method, variant)] = pair
            listing = aggregate_listing(pair)
            listing = listing.merge(base, on=ID, how="left", validate="one_to_one")
            listing = listing.merge(
                suspicious_counts, on=ID, how="left", validate="one_to_one"
            )
            listing["n_precos_suspeitos"] = (
                listing["n_precos_suspeitos"].fillna(0).astype(int)
            )
            listing["possui_preco_suspeito"] = listing[
                "possui_preco_suspeito"
            ].fillna(False)
            listing["metodo"] = method
            listing["metodo_label"] = METHODS[method]
            listing["tratamento_outlier"] = variant
            listing["tratamento_outlier_label"] = VARIANTS[variant]
            long_frames.append(listing)

    result = pd.concat(long_frames, ignore_index=True)
    duplicate_keys = result.duplicated([ID, "metodo", "tratamento_outlier"])
    assert not duplicate_keys.any()
    return result, pair_tables


def build_primary_support(listing_methods: pd.DataFrame) -> pd.DataFrame:
    main = listing_methods.loc[
        (listing_methods["metodo"] == "snapshot_2025_01_20")
        & (listing_methods["tratamento_outlier"] == "original")
        & listing_methods["residential_scope"]
    ]
    support = (
        main.groupby("segment_key", as_index=False)[ID]
        .nunique()
        .rename(columns={ID: "n_listings_metodo_principal"})
    )
    support["suporte_principal_airbnb"] = support[
        "n_listings_metodo_principal"
    ].map(support_label)
    return support


def build_segment_summary(
    listing_methods: pd.DataFrame, primary_support: pd.DataFrame
) -> pd.DataFrame:
    residential = listing_methods.loc[listing_methods["residential_scope"]].copy()
    group_columns = [
        "metodo",
        "metodo_label",
        "tratamento_outlier",
        "tratamento_outlier_label",
        "segment_key",
        "segmento_imoveis",
        "bairro",
        "tipo_imovel",
        "quartos",
        "quartos_label",
    ]
    rows: list[dict[str, Any]] = []
    for keys, group in residential.groupby(group_columns, dropna=False):
        row = dict(zip(group_columns, keys, strict=True))
        values = group["preco_anunciado_tipico"].dropna()
        seed = deterministic_seed(
            str(row["metodo"]),
            str(row["tratamento_outlier"]),
            str(row["segment_key"]),
        )
        ci_low, ci_high = bootstrap_median_interval(values, seed)
        row.update(
            {
                "n_listings": int(group[ID].nunique()),
                "preco_mediano_listings": float(values.median()),
                "preco_p25_listings": float(values.quantile(0.25)),
                "preco_p75_listings": float(values.quantile(0.75)),
                "bootstrap_mediana_ic95_inferior": ci_low,
                "bootstrap_mediana_ic95_superior": ci_high,
                "mediana_datas_por_listing": float(group["n_datas_estadia"].median()),
                "p25_datas_por_listing": float(group["n_datas_estadia"].quantile(0.25)),
                "p75_datas_por_listing": float(group["n_datas_estadia"].quantile(0.75)),
                "n_listings_com_preco_suspeito": int(
                    group.loc[group["possui_preco_suspeito"], ID].nunique()
                ),
                "suporte_amostra_atual": support_label(int(group[ID].nunique())),
            }
        )
        rows.append(row)

    summary = pd.DataFrame(rows)
    summary = summary.merge(primary_support, on="segment_key", how="left")
    summary["n_listings_metodo_principal"] = (
        summary["n_listings_metodo_principal"].fillna(0).astype(int)
    )
    summary["suporte_principal_airbnb"] = summary[
        "suporte_principal_airbnb"
    ].fillna("evidência insuficiente no Airbnb")
    summary["elegivel_comparacao_principal"] = (
        summary["n_listings_metodo_principal"] >= PRIMARY_AIRBNB_MIN
    )

    summary["rank_preco_dentro_metodo"] = summary.groupby(
        ["metodo", "tratamento_outlier"]
    )["preco_mediano_listings"].rank(method="min", ascending=False)
    comparison_mask = summary["elegivel_comparacao_principal"]
    summary["rank_entre_segmentos_principais"] = np.nan
    summary.loc[comparison_mask, "rank_entre_segmentos_principais"] = (
        summary.loc[comparison_mask]
        .groupby(["metodo", "tratamento_outlier"])["preco_mediano_listings"]
        .rank(method="min", ascending=False)
    )
    return summary.sort_values(
        ["metodo", "tratamento_outlier", "rank_preco_dentro_metodo"]
    )


def build_coverage_table(listing_base: pd.DataFrame) -> pd.DataFrame:
    dimension_specs = {
        "bairro": "bairro",
        "tipo de imóvel": "tipo_imovel",
        "número de quartos": "quartos_label",
        "segmento de imóveis": "segmento_imoveis",
    }
    frames: list[pd.DataFrame] = []
    for dimension_label, column in dimension_specs.items():
        grouped = (
            listing_base.groupby(column, dropna=False)
            .agg(
                total_listings=(ID, "nunique"),
                listings_com_algum_preco=("has_any_price", "sum"),
                listings_com_preco_20_01=("has_snapshot_20_price", "sum"),
            )
            .reset_index()
            .rename(columns={column: "categoria"})
        )
        grouped["listings_sem_preco"] = (
            grouped["total_listings"] - grouped["listings_com_algum_preco"]
        )
        grouped["perda_ao_usar_20_01"] = (
            grouped["listings_com_algum_preco"]
            - grouped["listings_com_preco_20_01"]
        )
        grouped["cobertura_algum_preco"] = (
            grouped["listings_com_algum_preco"] / grouped["total_listings"]
        )
        grouped["cobertura_20_01"] = (
            grouped["listings_com_preco_20_01"] / grouped["total_listings"]
        )
        grouped["retencao_20_01_entre_precificados"] = (
            grouped["listings_com_preco_20_01"]
            / grouped["listings_com_algum_preco"].replace(0, np.nan)
        )
        grouped["participacao_entre_precificados"] = (
            grouped["listings_com_algum_preco"]
            / grouped["listings_com_algum_preco"].sum()
        )
        grouped["participacao_entre_nao_precificados"] = (
            grouped["listings_sem_preco"] / grouped["listings_sem_preco"].sum()
        )
        grouped["diferenca_representacao_pp"] = 100 * (
            grouped["participacao_entre_precificados"]
            - grouped["participacao_entre_nao_precificados"]
        )
        grouped["dimensao"] = dimension_label
        frames.append(grouped)
    return pd.concat(frames, ignore_index=True)


def median_pairwise_jaccard(date_sets: list[set[pd.Timestamp]]) -> float:
    if len(date_sets) < 2:
        return np.nan
    values = []
    for left, right in combinations(date_sets, 2):
        union = left | right
        values.append(len(left & right) / len(union) if union else np.nan)
    return float(np.nanmedian(values))


def equal_listing_date_distribution(pair: pd.DataFrame) -> pd.Series:
    listing_counts = pair.groupby(ID)["stay_date"].transform("nunique")
    weighted = pair.assign(weight=1.0 / listing_counts)
    distribution = weighted.groupby("stay_date")["weight"].sum()
    total = distribution.sum()
    return distribution / total if total else distribution


def total_variation_distance(left: pd.Series, right: pd.Series) -> float:
    index = left.index.union(right.index)
    left_aligned = left.reindex(index, fill_value=0.0)
    right_aligned = right.reindex(index, fill_value=0.0)
    return float(0.5 * np.abs(left_aligned - right_aligned).sum())


def build_calendar_diagnostics(
    snapshot_pair: pd.DataFrame,
    listing_base: pd.DataFrame,
    primary_support: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    columns = [ID, "segment_key", "segmento_imoveis", "bairro", "tipo_imovel", "quartos"]
    pair = snapshot_pair.merge(
        listing_base[columns + ["residential_scope"]],
        on=ID,
        how="left",
        validate="many_to_one",
    )
    pair = pair.loc[pair["residential_scope"]].copy()

    daily_market_median = pair.groupby("stay_date")["price_numeric"].median()
    pair["daily_market_median"] = pair["stay_date"].map(daily_market_median)
    pair["relative_date_price"] = (
        pair["price_numeric"] / pair["daily_market_median"]
    )
    market_listing_scale = pair.groupby(ID).agg(
        listing_price=("price_numeric", "median"),
        listing_relative_index=("relative_date_price", "median"),
    )
    reference_price = float(
        market_listing_scale["listing_price"].median()
        / market_listing_scale["listing_relative_index"].median()
    )
    pair["price_calendar_adjusted"] = (
        pair["relative_date_price"] * reference_price
    )
    listing_adjusted = (
        pair.groupby([ID, "segment_key"], as_index=False)["price_calendar_adjusted"]
        .median()
    )
    segment_adjusted = (
        listing_adjusted.groupby("segment_key")["price_calendar_adjusted"]
        .median()
        .rename("preco_mediano_ajustado_calendario")
    )

    listing_original = pair.groupby([ID, "segment_key"], as_index=False).agg(
        preco_listing=("price_numeric", "median"),
        n_datas=("stay_date", "nunique"),
        proporcao_fim_semana=("is_weekend", "mean"),
        proporcao_janeiro=("stay_month", lambda s: float((s == 1).mean())),
        proporcao_fevereiro=("stay_month", lambda s: float((s == 2).mean())),
        proporcao_marco=("stay_month", lambda s: float((s == 3).mean())),
        proporcao_abril=("stay_month", lambda s: float((s == 4).mean())),
    )
    segment_original = (
        listing_original.groupby("segment_key")["preco_listing"]
        .median()
        .rename("preco_mediano_original")
    )
    market_distribution = equal_listing_date_distribution(pair)

    rows: list[dict[str, Any]] = []
    for segment_key, segment_pair in pair.groupby("segment_key"):
        listing_groups = list(segment_pair.groupby(ID))
        date_sets = [set(group["stay_date"]) for _, group in listing_groups]
        union_dates = set().union(*date_sets) if date_sets else set()
        intersection_dates = set.intersection(*date_sets) if date_sets else set()
        segment_distribution = equal_listing_date_distribution(segment_pair)
        segment_listing = listing_original.loc[
            listing_original["segment_key"] == segment_key
        ]
        first = segment_pair.iloc[0]
        rows.append(
            {
                "segment_key": segment_key,
                "segmento_imoveis": first["segmento_imoveis"],
                "bairro": first["bairro"],
                "tipo_imovel": first["tipo_imovel"],
                "quartos": first["quartos"],
                "n_listings": int(segment_pair[ID].nunique()),
                "mediana_datas_por_listing": float(segment_listing["n_datas"].median()),
                "p25_datas_por_listing": float(segment_listing["n_datas"].quantile(0.25)),
                "p75_datas_por_listing": float(segment_listing["n_datas"].quantile(0.75)),
                "datas_uniao": len(union_dates),
                "datas_comuns_a_todos": len(intersection_dates),
                "jaccard_mediano_entre_listings": median_pairwise_jaccard(date_sets),
                "distancia_calendario_do_mercado": total_variation_distance(
                    segment_distribution, market_distribution
                ),
                "mediana_proporcao_fim_semana": float(
                    segment_listing["proporcao_fim_semana"].median()
                ),
                "mediana_proporcao_janeiro": float(
                    segment_listing["proporcao_janeiro"].median()
                ),
                "mediana_proporcao_fevereiro": float(
                    segment_listing["proporcao_fevereiro"].median()
                ),
                "mediana_proporcao_marco": float(
                    segment_listing["proporcao_marco"].median()
                ),
                "mediana_proporcao_abril": float(
                    segment_listing["proporcao_abril"].median()
                ),
            }
        )

    calendar = pd.DataFrame(rows)
    calendar = calendar.merge(segment_original, on="segment_key", how="left")
    calendar = calendar.merge(segment_adjusted, on="segment_key", how="left")
    calendar = calendar.merge(primary_support, on="segment_key", how="left")
    calendar["n_listings_metodo_principal"] = (
        calendar["n_listings_metodo_principal"].fillna(0).astype(int)
    )
    calendar["suporte_principal_airbnb"] = calendar[
        "suporte_principal_airbnb"
    ].fillna("evidência insuficiente no Airbnb")
    calendar["ajuste_calendario_pct"] = (
        calendar["preco_mediano_ajustado_calendario"]
        / calendar["preco_mediano_original"]
        - 1
    )
    eligible = calendar["n_listings_metodo_principal"] >= PRIMARY_AIRBNB_MIN
    calendar["rank_original_segmentos_principais"] = np.nan
    calendar["rank_ajustado_segmentos_principais"] = np.nan
    calendar.loc[eligible, "rank_original_segmentos_principais"] = calendar.loc[
        eligible, "preco_mediano_original"
    ].rank(method="min", ascending=False)
    calendar.loc[eligible, "rank_ajustado_segmentos_principais"] = calendar.loc[
        eligible, "preco_mediano_ajustado_calendario"
    ].rank(method="min", ascending=False)
    return (
        calendar.sort_values("preco_mediano_original", ascending=False),
        pair,
        reference_price,
    )


def method_comparison(segment_summary: pd.DataFrame) -> list[dict[str, Any]]:
    original = segment_summary.loc[
        (segment_summary["tratamento_outlier"] == "original")
        & segment_summary["elegivel_comparacao_principal"]
    ]
    pivot = original.pivot(
        index="segmento_imoveis", columns="metodo", values="preco_mediano_listings"
    )
    snapshot = pivot["snapshot_2025_01_20"]
    rows = []
    for method in METHODS:
        comparable = pd.concat([snapshot, pivot[method]], axis=1).dropna()
        comparable.columns = ["snapshot", "comparison"]
        pct_diff = comparable["comparison"] / comparable["snapshot"] - 1
        rows.append(
            {
                "metodo": method,
                "metodo_label": METHODS[method],
                "segmentos_comparaveis": len(comparable),
                "correlacao_spearman_com_20_01": spearman_correlation(
                    comparable["snapshot"], comparable["comparison"]
                )
                if len(comparable) >= 2
                else None,
                "mediana_diferenca_absoluta_pct": float(pct_diff.abs().median())
                if len(comparable)
                else None,
                "maior_diferenca_absoluta_pct": float(pct_diff.abs().max())
                if len(comparable)
                else None,
                "segmento_mais_caro": comparable["comparison"].idxmax()
                if len(comparable)
                else None,
                "preco_segmento_mais_caro": float(comparable["comparison"].max())
                if len(comparable)
                else None,
            }
        )
    return rows


def method_support(segment_summary: pd.DataFrame) -> list[dict[str, Any]]:
    original = segment_summary.loc[segment_summary["tratamento_outlier"] == "original"]
    rows = []
    for method, group in original.groupby("metodo"):
        listing_count = int(group["n_listings"].sum())
        rows.append(
            {
                "metodo": method,
                "metodo_label": METHODS[method],
                "listings_residenciais": listing_count,
                "segmentos_com_algum_preco": int(group["segment_key"].nunique()),
                "segmentos_principais_n30": int((group["n_listings"] >= 30).sum()),
                "segmentos_exploratorios_n10_29": int(
                    group["n_listings"].between(10, 29).sum()
                ),
                "segmentos_n_menor_10": int((group["n_listings"] < 10).sum()),
            }
        )
    return sorted(rows, key=lambda row: list(METHODS).index(row["metodo"]))


def outlier_impact(
    segment_summary: pd.DataFrame, minimum_primary_n: int
) -> list[dict[str, Any]]:
    rows = []
    for method in METHODS:
        method_data = segment_summary.loc[
            (segment_summary["metodo"] == method)
            & (segment_summary["n_listings_metodo_principal"] >= minimum_primary_n)
        ]
        pivot = method_data.pivot(
            index="segmento_imoveis",
            columns="tratamento_outlier",
            values="preco_mediano_listings",
        )
        original = pivot["original"]
        row_only = pivot["exclude_suspicious_prices"]
        listing_only = pivot["exclude_affected_listings"]
        row_change = (row_only / original - 1).dropna()
        listing_change = (listing_only / original - 1).dropna()
        rows.append(
            {
                "metodo": method,
                "metodo_label": METHODS[method],
                "universo": f"segmentos com n principal ≥ {minimum_primary_n}",
                "segmentos_avaliados": int(len(pivot)),
                "maior_impacto_sem_precos_suspeitos_pct": float(
                    row_change.abs().max()
                )
                if len(row_change)
                else None,
                "segmento_maior_impacto_sem_precos_suspeitos": row_change.abs().idxmax()
                if len(row_change)
                else None,
                "maior_impacto_sem_listings_afetados_pct": float(
                    listing_change.abs().max()
                )
                if len(listing_change)
                else None,
                "segmento_maior_impacto_sem_listings_afetados": listing_change.abs().idxmax()
                if len(listing_change)
                else None,
                "mais_caro_original": original.idxmax() if len(original) else None,
                "mais_caro_sem_precos_suspeitos": row_only.idxmax()
                if row_only.notna().any()
                else None,
                "mais_caro_sem_listings_afetados": listing_only.idxmax()
                if listing_only.notna().any()
                else None,
            }
        )
    return rows


def build_transformation_log(
    details: pd.DataFrame,
    mesh: pd.DataFrame,
    price: pd.DataFrame,
    listing_base: pd.DataFrame,
    matched_price: pd.DataFrame,
    orphan_price: pd.DataFrame,
    listing_methods: pd.DataFrame,
    pair_tables: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows = [
        {
            "etapa": "Leitura de Details",
            "linhas_entrada": len(details),
            "linhas_saida": len(details),
            "registros_afetados": 0,
            "funcao": "read_inputs",
            "observacao": "Somente leitura; ID preservado como texto.",
        },
        {
            "etapa": "Leitura de Mesh",
            "linhas_entrada": len(mesh),
            "linhas_saida": len(mesh),
            "registros_afetados": 0,
            "funcao": "read_inputs",
            "observacao": "Somente leitura; ID preservado como texto.",
        },
        {
            "etapa": "Join Details–Mesh",
            "linhas_entrada": len(details),
            "linhas_saida": len(listing_base),
            "registros_afetados": len(listing_base) - len(details),
            "funcao": "build_listing_base",
            "observacao": "Join 1:1; nenhuma multiplicação de listings.",
        },
        {
            "etapa": "Leitura de Price_AV",
            "linhas_entrada": len(price),
            "linhas_saida": len(price),
            "registros_afetados": 0,
            "funcao": "read_inputs",
            "observacao": "Preço raw preservado; datas e flag ≥ 10.000 derivadas.",
        },
        {
            "etapa": "Separação de preços ligados a Details",
            "linhas_entrada": len(price),
            "linhas_saida": len(matched_price),
            "registros_afetados": len(orphan_price),
            "funcao": "main",
            "observacao": (
                f"{orphan_price[ID].nunique()} IDs e {len(orphan_price)} linhas "
                "órfãs ficam fora da comparação, mas são reconciliadas."
            ),
        },
    ]
    for (method, variant), pair in pair_tables.items():
        n_listings = int(
            listing_methods.loc[
                (listing_methods["metodo"] == method)
                & (listing_methods["tratamento_outlier"] == variant),
                ID,
            ].nunique()
        )
        rows.append(
            {
                "etapa": f"Agregação {method}/{variant}",
                "linhas_entrada": len(matched_price),
                "linhas_saida": len(pair),
                "registros_afetados": len(matched_price) - len(pair),
                "funcao": "filter_variant + build_pair_table + aggregate_listing",
                "observacao": (
                    f"{len(pair)} pares listing–estadia resultaram em "
                    f"{n_listings} preços típicos por listing. A diferença inclui "
                    "filtro temporal, sensibilidade e agregação; não é perda silenciosa."
                ),
            }
        )
    return pd.DataFrame(rows)


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    actual: Any,
    expected: Any,
    passed: bool,
    notes: str,
) -> None:
    checks.append(
        {
            "check": name,
            "actual": actual,
            "expected": expected,
            "status": "OK" if passed else "FALHA",
            "notes": notes,
        }
    )


def build_checks(
    details: pd.DataFrame,
    mesh: pd.DataFrame,
    price: pd.DataFrame,
    listing_base: pd.DataFrame,
    matched_price: pd.DataFrame,
    orphan_price: pd.DataFrame,
    listing_methods: pd.DataFrame,
    pair_tables: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []
    add_check(checks, "Details ID único", details[ID].is_unique, True, details[ID].is_unique, "")
    add_check(checks, "Mesh ID único", mesh[ID].is_unique, True, mesh[ID].is_unique, "")
    add_check(
        checks,
        "Join Details–Mesh sem multiplicação",
        len(listing_base),
        len(details),
        len(listing_base) == len(details),
        "Join validado como 1:1.",
    )
    safe_grain_duplicates = int(
        price.duplicated([ID, "stay_date", "capture_day"]).sum()
    )
    add_check(
        checks,
        "Grain Price listing–estadia–capture_day único",
        safe_grain_duplicates,
        0,
        safe_grain_duplicates == 0,
        "O timestamp completo não é usado como snapshot independente.",
    )
    add_check(
        checks,
        "Reconciliação de linhas Price",
        len(matched_price) + len(orphan_price),
        len(price),
        len(matched_price) + len(orphan_price) == len(price),
        f"{len(orphan_price)} linhas órfãs preservadas no diagnóstico.",
    )
    add_check(
        checks,
        "Reconciliação de IDs Price",
        matched_price[ID].nunique() + orphan_price[ID].nunique(),
        price[ID].nunique(),
        matched_price[ID].nunique() + orphan_price[ID].nunique()
        == price[ID].nunique(),
        "Namespaces de IDs não foram convertidos.",
    )
    listing_method_duplicates = int(
        listing_methods.duplicated([ID, "metodo", "tratamento_outlier"]).sum()
    )
    add_check(
        checks,
        "Uma linha por listing–método–tratamento",
        listing_method_duplicates,
        0,
        listing_method_duplicates == 0,
        "Garante peso igual por listing na agregação posterior.",
    )
    for (method, variant), pair in pair_tables.items():
        duplicates = int(pair.duplicated([ID, "stay_date"]).sum())
        add_check(
            checks,
            f"Par listing–estadia único: {method}/{variant}",
            duplicates,
            0,
            duplicates == 0,
            "",
        )
    return pd.DataFrame(checks)


def top_segment_rows(
    segment_summary: pd.DataFrame, method: str, variant: str, limit: int = 10
) -> list[dict[str, Any]]:
    selected = segment_summary.loc[
        (segment_summary["metodo"] == method)
        & (segment_summary["tratamento_outlier"] == variant)
        & segment_summary["elegivel_comparacao_principal"]
    ].sort_values("preco_mediano_listings", ascending=False)
    columns = [
        "segmento_imoveis",
        "n_listings",
        "preco_mediano_listings",
        "preco_p25_listings",
        "preco_p75_listings",
        "bootstrap_mediana_ic95_inferior",
        "bootstrap_mediana_ic95_superior",
        "mediana_datas_por_listing",
    ]
    return [
        {key: json_value(value) for key, value in row.items()}
        for row in selected[columns].head(limit).to_dict("records")
    ]


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    source_hashes = {
        DETAILS_FILE.name: sha256(DETAILS_FILE),
        MESH_FILE.name: sha256(MESH_FILE),
        PRICE_FILE.name: sha256(PRICE_FILE),
    }
    details, mesh, price = read_inputs()
    listing_base = build_listing_base(details, mesh, price)

    detail_ids = set(details[ID])
    matched_price = price.loc[price[ID].isin(detail_ids)].copy()
    orphan_price = price.loc[~price[ID].isin(detail_ids)].copy()
    affected_listing_ids = set(
        matched_price.loc[matched_price["is_suspicious_price"], ID].astype(str)
    )

    listing_methods, pair_tables = build_listing_methods(
        listing_base, matched_price, affected_listing_ids
    )
    primary_support = build_primary_support(listing_methods)
    segment_summary = build_segment_summary(listing_methods, primary_support)
    coverage = build_coverage_table(listing_base)
    calendar, _, calendar_reference_price = build_calendar_diagnostics(
        pair_tables[("snapshot_2025_01_20", "original")],
        listing_base,
        primary_support,
    )
    checks = build_checks(
        details,
        mesh,
        price,
        listing_base,
        matched_price,
        orphan_price,
        listing_methods,
        pair_tables,
    )

    affected_details = (
        matched_price.loc[matched_price[ID].isin(affected_listing_ids)]
        .groupby(ID)
        .agg(
            n_linhas_preco=("price_numeric", "size"),
            n_precos_suspeitos=("is_suspicious_price", "sum"),
            preco_minimo=("price_numeric", "min"),
            preco_mediano=("price_numeric", "median"),
            preco_maximo=("price_numeric", "max"),
        )
        .reset_index()
        .merge(
            listing_base[[ID, "segmento_imoveis"]],
            on=ID,
            how="left",
            validate="one_to_one",
        )
    )

    method_rows = method_comparison(segment_summary)
    support_rows = method_support(segment_summary)
    outlier_rows_primary = outlier_impact(segment_summary, PRIMARY_AIRBNB_MIN)
    outlier_rows_supported = outlier_impact(
        segment_summary, EXPLORATORY_AIRBNB_MIN
    )
    transformations = build_transformation_log(
        details,
        mesh,
        price,
        listing_base,
        matched_price,
        orphan_price,
        listing_methods,
        pair_tables,
    )

    coverage_segment = coverage.loc[
        (coverage["dimensao"] == "segmento de imóveis")
        & (coverage["listings_com_algum_preco"] >= 10)
    ].copy()
    largest_absolute_losses = coverage_segment.sort_values(
        ["perda_ao_usar_20_01", "listings_com_algum_preco"], ascending=False
    ).head(10)
    largest_relative_losses = coverage_segment.sort_values(
        ["retencao_20_01_entre_precificados", "listings_com_algum_preco"],
        ascending=[True, False],
    ).head(10)

    representation = coverage.loc[
        coverage["dimensao"].isin(["bairro", "tipo de imóvel", "número de quartos"])
    ].copy()
    representation = representation.sort_values(
        "diferenca_representacao_pp", key=lambda series: series.abs(), ascending=False
    )

    calendar_eligible = calendar.loc[
        calendar["n_listings_metodo_principal"] >= PRIMARY_AIRBNB_MIN
    ]
    calendar_rank_changed = bool(
        (
            calendar_eligible["rank_original_segmentos_principais"]
            != calendar_eligible["rank_ajustado_segmentos_principais"]
        ).any()
    )

    main_segments = segment_summary.loc[
        (segment_summary["metodo"] == "snapshot_2025_01_20")
        & (segment_summary["tratamento_outlier"] == "original")
        & (segment_summary["n_listings"] >= EXPLORATORY_AIRBNB_MIN)
    ].copy()
    segment_coverage = coverage.loc[
        coverage["dimensao"] == "segmento de imóveis",
        ["categoria", "cobertura_20_01"],
    ].rename(columns={"categoria": "segmento_imoveis"})
    main_segments = main_segments.merge(
        segment_coverage, on="segmento_imoveis", how="left", validate="one_to_one"
    )
    price_vs_n_corr = spearman_correlation(
        main_segments["preco_mediano_listings"], main_segments["n_listings"]
    )
    price_vs_coverage_corr = spearman_correlation(
        main_segments["preco_mediano_listings"],
        main_segments["cobertura_20_01"],
    )

    summary = {
        "scope": {
            "uses_vivareal": False,
            "estimates_occupancy": False,
            "estimates_revenue": False,
            "main_capture": MAIN_CAPTURE.date().isoformat(),
            "price_semantics": (
                "Preço anunciado presumido em reais por data de estadia; moeda, "
                "taxas e valor efetivamente recebido não são documentados."
            ),
        },
        "source_hashes": source_hashes,
        "source_counts": {
            "details_rows": len(details),
            "mesh_rows": len(mesh),
            "price_rows": len(price),
            "price_ids": int(price[ID].nunique()),
            "matched_price_rows": len(matched_price),
            "matched_price_ids": int(matched_price[ID].nunique()),
            "orphan_price_rows": len(orphan_price),
            "orphan_price_ids": int(orphan_price[ID].nunique()),
        },
        "method_support": support_rows,
        "method_comparison": method_rows,
        "top_segments_main_original": top_segment_rows(
            segment_summary, "snapshot_2025_01_20", "original"
        ),
        "top_segments_latest_original": top_segment_rows(
            segment_summary, "latest_available", "original"
        ),
        "top_segments_median_original": top_segment_rows(
            segment_summary, "median_across_captures", "original"
        ),
        "outliers": {
            "threshold_inclusive": SUSPICIOUS_PRICE_THRESHOLD,
            "affected_listing_count": len(affected_listing_ids),
            "affected_listings": [
                {key: json_value(value) for key, value in row.items()}
                for row in affected_details.to_dict("records")
            ],
            "impact_segmentos_principais": outlier_rows_primary,
            "impact_segmentos_principais_ou_exploratorios": outlier_rows_supported,
        },
        "coverage": {
            "overall_any_price": float(listing_base["has_any_price"].mean()),
            "overall_snapshot_20": float(
                listing_base["has_snapshot_20_price"].mean()
            ),
            "largest_absolute_losses": [
                {key: json_value(value) for key, value in row.items()}
                for row in largest_absolute_losses.to_dict("records")
            ],
            "largest_relative_losses": [
                {key: json_value(value) for key, value in row.items()}
                for row in largest_relative_losses.to_dict("records")
            ],
            "largest_representation_gaps": [
                {key: json_value(value) for key, value in row.items()}
                for row in representation.head(15).to_dict("records")
            ],
            "spearman_price_vs_n_listings_snapshot_20": json_value(price_vs_n_corr),
            "spearman_price_vs_coverage_snapshot_20": json_value(
                price_vs_coverage_corr
            ),
        },
        "calendar": {
            "reference_price_for_adjustment": calendar_reference_price,
            "rank_changed_after_calendar_adjustment": calendar_rank_changed,
            "eligible_segments": [
                {key: json_value(value) for key, value in row.items()}
                for row in calendar_eligible[
                    [
                        "segmento_imoveis",
                        "n_listings",
                        "mediana_datas_por_listing",
                        "jaccard_mediano_entre_listings",
                        "distancia_calendario_do_mercado",
                        "preco_mediano_original",
                        "preco_mediano_ajustado_calendario",
                        "ajuste_calendario_pct",
                        "rank_original_segmentos_principais",
                        "rank_ajustado_segmentos_principais",
                    ]
                ].sort_values("rank_original_segmentos_principais").to_dict("records")
            ],
        },
        "checks": {
            "all_passed": bool((checks["status"] == "OK").all()),
            "failed_count": int((checks["status"] != "OK").sum()),
        },
    }

    listing_methods.to_csv(LISTING_OUTPUT, index=False)
    segment_summary.to_csv(SEGMENT_OUTPUT, index=False)
    coverage.to_csv(COVERAGE_OUTPUT, index=False)
    calendar.to_csv(CALENDAR_OUTPUT, index=False)
    checks.to_csv(CHECKS_OUTPUT, index=False)
    transformations.to_csv(TRANSFORMATIONS_OUTPUT, index=False)
    SUMMARY_OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(
        "Análise Airbnb concluída: "
        f"{len(price):,} linhas de preço; "
        f"{len(listing_methods):,} linhas listing–método–tratamento; "
        f"checks={'OK' if summary['checks']['all_passed'] else 'FALHA'}"
    )
if __name__ == "__main__":
    main()
