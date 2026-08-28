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
DECOMPOSITION_OUTPUT = GENERATED_DIR / "airbnb_price_decomposition.csv"
HOST_CONCENTRATION_OUTPUT = GENERATED_DIR / "airbnb_price_host_concentration.csv"
PAIRWISE_OUTPUT = GENERATED_DIR / "airbnb_price_pairwise_differences.csv"
CAPTURE_CHANGES_OUTPUT = GENERATED_DIR / "airbnb_price_capture_changes.csv"
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


def require(condition: bool, message: str) -> None:
    """Validação executável que permanece ativa mesmo com Python otimizado."""
    if not condition:
        raise ValueError(message)


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
    price = pd.read_csv(
        PRICE_FILE,
        dtype={
            ID: "string",
            "date": "string",
            "price": "string",
            "aquisition_date": "string",
        },
        low_memory=False,
    )

    price["price_raw_missing"] = price["price"].isna() | price["price"].str.strip().eq("")
    price["stay_date_raw_missing"] = price["date"].isna() | price["date"].str.strip().eq("")
    price["capture_date_raw_missing"] = (
        price["aquisition_date"].isna()
        | price["aquisition_date"].str.strip().eq("")
    )
    price["stay_date"] = pd.to_datetime(price["date"], errors="coerce").dt.normalize()
    price["capture_timestamp"] = pd.to_datetime(
        price["aquisition_date"], errors="coerce"
    )
    price["capture_day"] = price["capture_timestamp"].dt.normalize()
    price["price_numeric"] = pd.to_numeric(price["price"], errors="coerce")
    price["price_conversion_failed"] = (
        ~price["price_raw_missing"] & price["price_numeric"].isna()
    )
    price["stay_date_conversion_failed"] = (
        ~price["stay_date_raw_missing"] & price["stay_date"].isna()
    )
    price["capture_date_conversion_failed"] = (
        ~price["capture_date_raw_missing"] & price["capture_timestamp"].isna()
    )
    price["price_non_finite"] = (
        price["price_numeric"].notna()
        & ~np.isfinite(price["price_numeric"].astype(float))
    )
    price["price_non_positive"] = price["price_numeric"].notna() & (
        price["price_numeric"] <= 0
    )
    price["valid_row_for_price_analysis"] = (
        price[ID].notna()
        & price["stay_date"].notna()
        & price["capture_timestamp"].notna()
        & price["price_numeric"].notna()
        & ~price["price_non_finite"]
        & ~price["price_non_positive"]
    )
    price["is_suspicious_price"] = (
        price["price_numeric"] >= SUSPICIOUS_PRICE_THRESHOLD
    )
    return details, mesh, price


def build_listing_base(
    details: pd.DataFrame, mesh: pd.DataFrame, price: pd.DataFrame
) -> pd.DataFrame:
    require(
        bool(details[ID].notna().all() and details[ID].is_unique),
        "Details precisa ter IDs não nulos e únicos.",
    )
    require(
        bool(mesh[ID].notna().all() and mesh[ID].is_unique),
        "Mesh precisa ter IDs não nulos e únicos.",
    )
    require(set(details[ID]) == set(mesh[ID]), "Details e Mesh precisam ter os mesmos IDs.")

    mesh_columns = [ID, "suburb", "latitude", "longitude"]
    base = details.merge(
        mesh[mesh_columns],
        on=ID,
        how="left",
        validate="one_to_one",
        suffixes=("_details", "_mesh"),
    )
    require(len(base) == len(details), "O join Details–Mesh multiplicou ou perdeu listings.")

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
    price = price.loc[price["valid_row_for_price_analysis"]].copy()
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

    require(
        not bool(pair.duplicated([ID, "stay_date"]).any()),
        f"O método {method} produziu pares listing–estadia duplicados.",
    )
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
    require(bool(listing[ID].is_unique), "A agregação não produziu uma linha por listing.")
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


def cluster_bootstrap_median_interval(
    group: pd.DataFrame,
    seed: int,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> tuple[float, float]:
    """IC da mediana reamostrando anfitriões e mantendo seus listings juntos."""
    usable = group[["owner_id", "preco_anunciado_tipico"]].dropna()
    owners = usable["owner_id"].drop_duplicates().to_numpy()
    if len(owners) < 5:
        return np.nan, np.nan
    values_by_owner = {
        owner: owner_group["preco_anunciado_tipico"].to_numpy(dtype=float)
        for owner, owner_group in usable.groupby("owner_id")
    }
    rng = np.random.default_rng(seed)
    medians = np.empty(iterations, dtype=float)
    for iteration in range(iterations):
        sampled = rng.choice(owners, size=len(owners), replace=True)
        values = np.concatenate([values_by_owner[owner] for owner in sampled])
        medians[iteration] = np.median(values)
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
    require(
        not bool(duplicate_keys.any()),
        "Há duplicações no grain listing–método–tratamento.",
    )
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
        cluster_low, cluster_high = cluster_bootstrap_median_interval(
            group,
            deterministic_seed(
                "host_cluster",
                str(row["metodo"]),
                str(row["tratamento_outlier"]),
                str(row["segment_key"]),
            ),
        )
        row.update(
            {
                "n_listings": int(group[ID].nunique()),
                "preco_mediano_listings": float(values.median()),
                "preco_p25_listings": float(values.quantile(0.25)),
                "preco_p75_listings": float(values.quantile(0.75)),
                "bootstrap_mediana_ic95_inferior": ci_low,
                "bootstrap_mediana_ic95_superior": ci_high,
                "bootstrap_host_mediana_ic95_inferior": cluster_low,
                "bootstrap_host_mediana_ic95_superior": cluster_high,
                "n_hosts": int(group["owner_id"].nunique()),
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


def summarize_stage_pairs(
    pair: pd.DataFrame,
    listing_base: pd.DataFrame,
    method: str,
    stage: str,
    primary_segments: set[str],
) -> pd.DataFrame:
    """Resume uma etapa com uma observação por listing antes da mediana do segmento."""
    listing = aggregate_listing(pair).merge(
        listing_base[
            [
                ID,
                "segment_key",
                "segmento_imoveis",
                "bairro",
                "tipo_imovel",
                "quartos",
                "residential_scope",
            ]
        ],
        on=ID,
        how="left",
        validate="one_to_one",
    )
    listing = listing.loc[
        listing["residential_scope"] & listing["segment_key"].isin(primary_segments)
    ].copy()
    rows = (
        listing.groupby(
            ["segment_key", "segmento_imoveis", "bairro", "tipo_imovel", "quartos"],
            as_index=False,
            dropna=False,
        )
        .agg(
            n_listings=(ID, "nunique"),
            preco_mediano=("preco_anunciado_tipico", "median"),
            mediana_datas_por_listing=("n_datas_estadia", "median"),
        )
    )
    pair_counts = (
        pair.merge(
            listing_base[[ID, "segment_key", "residential_scope"]],
            on=ID,
            how="left",
            validate="many_to_one",
        )
        .loc[lambda frame: frame["residential_scope"] & frame["segment_key"].isin(primary_segments)]
        .groupby("segment_key", as_index=False)
        .size()
        .rename(columns={"size": "n_pares_listing_data"})
    )
    rows = rows.merge(pair_counts, on="segment_key", how="left", validate="one_to_one")
    rows["metodo"] = method
    rows["metodo_label"] = METHODS[method]
    rows["etapa"] = stage
    return rows


def build_incremental_decomposition(
    pair_tables: dict[tuple[str, str], pd.DataFrame],
    listing_base: pd.DataFrame,
    primary_support: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ponte preço → calendário → amostra; componentes dependem dessa ordem."""
    primary_segments = set(
        primary_support.loc[
            primary_support["n_listings_metodo_principal"] >= PRIMARY_AIRBNB_MIN,
            "segment_key",
        ]
    )
    reference_pair = pair_tables[("snapshot_2025_01_20", "original")]
    reference_keys = reference_pair[[ID, "stay_date"]].drop_duplicates()
    reference_ids = set(reference_keys[ID])
    stage_frames: list[pd.DataFrame] = []
    for method in METHODS:
        full_pair = pair_tables[(method, "original")]
        fixed_pairs = full_pair.merge(
            reference_keys,
            on=[ID, "stay_date"],
            how="inner",
            validate="one_to_one",
        )
        same_listings = full_pair.loc[full_pair[ID].isin(reference_ids)].copy()
        stages = {
            "1_pares_20_01": fixed_pairs,
            "2_mesmos_listings_todas_datas": same_listings,
            "3_todos_listings_todas_datas": full_pair,
        }
        for stage, stage_pair in stages.items():
            stage_frames.append(
                summarize_stage_pairs(
                    stage_pair, listing_base, method, stage, primary_segments
                )
            )

    stages = pd.concat(stage_frames, ignore_index=True)
    stages["rank_na_etapa"] = stages.groupby(["metodo", "etapa"])[
        "preco_mediano"
    ].rank(method="min", ascending=False)

    index_columns = [
        "segment_key",
        "segmento_imoveis",
        "bairro",
        "tipo_imovel",
        "quartos",
        "metodo",
        "metodo_label",
    ]
    value_columns = [
        "preco_mediano",
        "n_listings",
        "n_pares_listing_data",
        "mediana_datas_por_listing",
        "rank_na_etapa",
    ]
    wide = stages.pivot(index=index_columns, columns="etapa", values=value_columns)
    wide.columns = [f"{value}_{stage}" for value, stage in wide.columns]
    wide = wide.reset_index()

    baseline = stages.loc[
        (stages["metodo"] == "snapshot_2025_01_20")
        & (stages["etapa"] == "1_pares_20_01"),
        ["segment_key", "preco_mediano"],
    ].rename(columns={"preco_mediano": "preco_base_20_01"})
    wide = wide.merge(baseline, on="segment_key", how="left", validate="many_to_one")

    price_1 = wide["preco_mediano_1_pares_20_01"]
    price_2 = wide["preco_mediano_2_mesmos_listings_todas_datas"]
    price_3 = wide["preco_mediano_3_todos_listings_todas_datas"]
    base = wide["preco_base_20_01"]
    wide["mudanca_incremental_metodo_preco_rs"] = price_1 - base
    wide["mudanca_incremental_datas_rs"] = price_2 - price_1
    wide["mudanca_incremental_amostra_rs"] = price_3 - price_2
    wide["mudanca_total_rs"] = price_3 - base
    wide["erro_reconciliacao_rs"] = wide["mudanca_total_rs"] - (
        wide["mudanca_incremental_metodo_preco_rs"]
        + wide["mudanca_incremental_datas_rs"]
        + wide["mudanca_incremental_amostra_rs"]
    )
    for column in [
        "mudanca_incremental_metodo_preco_rs",
        "mudanca_incremental_datas_rs",
        "mudanca_incremental_amostra_rs",
        "mudanca_total_rs",
    ]:
        wide[column.replace("_rs", "_pct_base")] = wide[column] / base
    wide["ordem_decomposicao"] = "método de preço → datas → amostra"
    wide["interpretacao"] = (
        "mudanças incrementais condicionais à ordem; não são causas independentes"
    )
    return wide.sort_values(["metodo", "preco_base_20_01"], ascending=[True, False]), stages


def build_capture_change_diagnostic(
    matched_price: pd.DataFrame,
    listing_base: pd.DataFrame,
    primary_support: pd.DataFrame,
) -> pd.DataFrame:
    """Mudanças observadas entre capturas para os mesmos pares listing–data."""
    primary_segments = set(
        primary_support.loc[
            primary_support["n_listings_metodo_principal"] >= PRIMARY_AIRBNB_MIN,
            "segment_key",
        ]
    )
    valid = matched_price.loc[matched_price["valid_row_for_price_analysis"]].copy()
    main = valid.loc[
        valid["capture_day"] == MAIN_CAPTURE,
        [ID, "stay_date", "price_numeric"],
    ].rename(columns={"price_numeric": "preco_20_01"})
    main = main.merge(
        listing_base[[ID, "segment_key", "segmento_imoveis", "residential_scope"]],
        on=ID,
        how="left",
        validate="many_to_one",
    )
    main = main.loc[
        main["residential_scope"] & main["segment_key"].isin(primary_segments)
    ].copy()
    reference_counts = (
        main.groupby(["segment_key", "segmento_imoveis"], as_index=False)
        .agg(
            pares_referencia_20_01=("stay_date", "size"),
            listings_referencia_20_01=(ID, "nunique"),
        )
    )
    frames: list[pd.DataFrame] = []
    earlier_days = sorted(
        day for day in valid["capture_day"].dropna().unique() if day < MAIN_CAPTURE
    )
    for earlier_day in earlier_days:
        earlier = valid.loc[
            valid["capture_day"] == earlier_day,
            [ID, "stay_date", "price_numeric"],
        ].rename(columns={"price_numeric": "preco_anterior"})
        common = main.merge(
            earlier,
            on=[ID, "stay_date"],
            how="inner",
            validate="one_to_one",
        )
        common["mudanca_rs"] = common["preco_20_01"] - common["preco_anterior"]
        common["mudanca_pct"] = common["preco_20_01"] / common["preco_anterior"] - 1
        common["mudou"] = common["mudanca_rs"] != 0
        common["aumentou"] = common["mudanca_rs"] > 0
        common["diminuiu"] = common["mudanca_rs"] < 0
        by_listing = (
            common.groupby(["segment_key", "segmento_imoveis", ID], as_index=False)
            .agg(
                pares_comuns=("stay_date", "size"),
                listing_teve_alguma_mudanca=("mudou", "any"),
                mudanca_mediana_rs_listing=("mudanca_rs", "median"),
                mudanca_mediana_pct_listing=("mudanca_pct", "median"),
                mediana_abs_mudanca_pct_condicional_listing=(
                    "mudanca_pct",
                    lambda s: s.loc[s != 0].abs().median(),
                ),
            )
        )
        pair_diagnostic = (
            common.groupby(["segment_key", "segmento_imoveis"], as_index=False)
            .agg(
                pares_comuns=("stay_date", "size"),
                pares_alterados=("mudou", "sum"),
                pares_aumentaram=("aumentou", "sum"),
                pares_diminuiram=("diminuiu", "sum"),
            )
        )
        segment = (
            by_listing.groupby(["segment_key", "segmento_imoveis"], as_index=False)
            .agg(
                listings_comparaveis=(ID, "nunique"),
                listings_com_alguma_mudanca=("listing_teve_alguma_mudanca", "sum"),
                mudanca_mediana_rs=("mudanca_mediana_rs_listing", "median"),
                mudanca_mediana_pct=("mudanca_mediana_pct_listing", "median"),
                p25_mudanca_pct=("mudanca_mediana_pct_listing", lambda s: s.quantile(0.25)),
                p75_mudanca_pct=("mudanca_mediana_pct_listing", lambda s: s.quantile(0.75)),
                mediana_abs_mudanca_pct_condicional=(
                    "mediana_abs_mudanca_pct_condicional_listing",
                    "median",
                ),
            )
            .merge(
                pair_diagnostic,
                on=["segment_key", "segmento_imoveis"],
                how="left",
                validate="one_to_one",
            )
            .merge(
                reference_counts,
                on=["segment_key", "segmento_imoveis"],
                how="right",
                validate="one_to_one",
            )
        )
        segment["captura_anterior"] = pd.Timestamp(earlier_day)
        segment["captura_referencia"] = MAIN_CAPTURE
        segment["cobertura_pares_comuns"] = (
            segment["pares_comuns"] / segment["pares_referencia_20_01"]
        )
        segment["proporcao_listings_com_alguma_mudanca"] = (
            segment["listings_com_alguma_mudanca"] / segment["listings_comparaveis"]
        )
        segment["proporcao_pares_alterados"] = (
            segment["pares_alterados"] / segment["pares_comuns"]
        )
        segment["proporcao_pares_aumentaram"] = (
            segment["pares_aumentaram"] / segment["pares_comuns"]
        )
        segment["proporcao_pares_diminuiram"] = (
            segment["pares_diminuiram"] / segment["pares_comuns"]
        )
        segment["peso"] = "igual por listing"
        frames.append(segment)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["captura_anterior", "segmento_imoveis"]
    )


def build_host_concentration(
    listing_methods: pd.DataFrame,
    primary_support: pd.DataFrame,
) -> pd.DataFrame:
    primary_segments = set(
        primary_support.loc[
            primary_support["n_listings_metodo_principal"] >= PRIMARY_AIRBNB_MIN,
            "segment_key",
        ]
    )
    main = listing_methods.loc[
        (listing_methods["metodo"] == "snapshot_2025_01_20")
        & (listing_methods["tratamento_outlier"] == "original")
        & listing_methods["residential_scope"]
        & listing_methods["segment_key"].isin(primary_segments)
    ].copy()
    rows: list[dict[str, Any]] = []
    for segment_key, group in main.groupby("segment_key"):
        first = group.iloc[0]
        owner_counts = group.groupby("owner_id")[ID].nunique().sort_values(ascending=False)
        max_count = int(owner_counts.max())
        top_owners = owner_counts.loc[owner_counts == max_count].index.astype(str).tolist()
        current = float(group["preco_anunciado_tipico"].median())
        owner_typical = group.groupby("owner_id")["preco_anunciado_tipico"].median()
        equal_owner = float(owner_typical.median())
        without_values = [
            float(group.loc[group["owner_id"] != owner, "preco_anunciado_tipico"].median())
            for owner in top_owners
        ]
        without_single = without_values[0] if len(without_values) == 1 else np.nan
        rows.append(
            {
                "segment_key": segment_key,
                "segmento_imoveis": first["segmento_imoveis"],
                "bairro": first["bairro"],
                "tipo_imovel": first["tipo_imovel"],
                "quartos": first["quartos"],
                "n_listings": int(group[ID].nunique()),
                "n_hosts": int(group["owner_id"].nunique()),
                "n_hosts_empatados_no_topo": len(top_owners),
                "owner_ids_maior_concentracao": ";".join(top_owners),
                "listings_maior_host": max_count,
                "participacao_maior_host": max_count / group[ID].nunique(),
                "mediana_peso_igual_listing": current,
                "mediana_peso_igual_host": equal_owner,
                "mudanca_peso_host_rs": equal_owner - current,
                "mudanca_peso_host_pct": equal_owner / current - 1,
                "mediana_sem_maior_host": without_single,
                "mediana_sem_maior_host_min": min(without_values),
                "mediana_sem_maior_host_max": max(without_values),
                "mudanca_sem_maior_host_min_rs": min(without_values) - current,
                "mudanca_sem_maior_host_max_rs": max(without_values) - current,
                "mudanca_sem_maior_host_min_pct": min(without_values) / current - 1,
                "mudanca_sem_maior_host_max_pct": max(without_values) / current - 1,
            }
        )
    return pd.DataFrame(rows).sort_values("mediana_peso_igual_listing", ascending=False)


def bootstrap_pairwise_difference(
    left: pd.DataFrame,
    right: pd.DataFrame,
    seed: int,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> tuple[float, float, float, float]:
    rng = np.random.default_rng(seed)
    left_values = left["preco_anunciado_tipico"].to_numpy(dtype=float)
    right_values = right["preco_anunciado_tipico"].to_numpy(dtype=float)
    listing_differences = np.median(
        rng.choice(left_values, size=(iterations, len(left_values)), replace=True), axis=1
    ) - np.median(
        rng.choice(right_values, size=(iterations, len(right_values)), replace=True), axis=1
    )

    all_owners = np.array(
        sorted(set(left["owner_id"].astype(str)) | set(right["owner_id"].astype(str)))
    )
    left_by_owner = {
        str(owner): group["preco_anunciado_tipico"].to_numpy(dtype=float)
        for owner, group in left.groupby("owner_id")
    }
    right_by_owner = {
        str(owner): group["preco_anunciado_tipico"].to_numpy(dtype=float)
        for owner, group in right.groupby("owner_id")
    }
    cluster_differences: list[float] = []
    for _ in range(iterations):
        counts = rng.multinomial(len(all_owners), np.repeat(1 / len(all_owners), len(all_owners)))
        left_parts: list[np.ndarray] = []
        right_parts: list[np.ndarray] = []
        for owner, count in zip(all_owners, counts, strict=True):
            if count and owner in left_by_owner:
                left_parts.extend([left_by_owner[owner]] * int(count))
            if count and owner in right_by_owner:
                right_parts.extend([right_by_owner[owner]] * int(count))
        if left_parts and right_parts:
            cluster_differences.append(
                float(np.median(np.concatenate(left_parts)) - np.median(np.concatenate(right_parts)))
            )
    require(
        len(cluster_differences) >= int(iterations * 0.95),
        "O bootstrap agrupado não gerou replicações válidas suficientes.",
    )
    listing_low, listing_high = np.quantile(listing_differences, [0.025, 0.975])
    cluster_low, cluster_high = np.quantile(cluster_differences, [0.025, 0.975])
    return (
        float(listing_low),
        float(listing_high),
        float(cluster_low),
        float(cluster_high),
    )


def build_pairwise_differences(
    listing_methods: pd.DataFrame,
    primary_support: pd.DataFrame,
) -> pd.DataFrame:
    primary_segments = set(
        primary_support.loc[
            primary_support["n_listings_metodo_principal"] >= PRIMARY_AIRBNB_MIN,
            "segment_key",
        ]
    )
    main = listing_methods.loc[
        (listing_methods["metodo"] == "snapshot_2025_01_20")
        & (listing_methods["tratamento_outlier"] == "original")
        & listing_methods["residential_scope"]
        & listing_methods["segment_key"].isin(primary_segments)
    ].copy()
    medians = main.groupby("segment_key")["preco_anunciado_tipico"].median()
    ordered_segments = medians.sort_values(ascending=False).index.tolist()
    rows: list[dict[str, Any]] = []
    for left_key, right_key in combinations(ordered_segments, 2):
        left = main.loc[main["segment_key"] == left_key]
        right = main.loc[main["segment_key"] == right_key]
        left_price = float(left["preco_anunciado_tipico"].median())
        right_price = float(right["preco_anunciado_tipico"].median())
        difference = left_price - right_price
        listing_low, listing_high, cluster_low, cluster_high = bootstrap_pairwise_difference(
            left,
            right,
            deterministic_seed("pairwise", left_key, right_key),
        )
        inconclusive = cluster_low <= 0 <= cluster_high
        rows.append(
            {
                "segmento_a": left.iloc[0]["segmento_imoveis"],
                "segmento_b": right.iloc[0]["segmento_imoveis"],
                "n_listings_a": int(left[ID].nunique()),
                "n_listings_b": int(right[ID].nunique()),
                "n_hosts_a": int(left["owner_id"].nunique()),
                "n_hosts_b": int(right["owner_id"].nunique()),
                "hosts_presentes_nos_dois_segmentos": int(
                    len(set(left["owner_id"]) & set(right["owner_id"]))
                ),
                "preco_mediano_a": left_price,
                "preco_mediano_b": right_price,
                "diferenca_rs": difference,
                "diferenca_pct_sobre_b": difference / right_price,
                "bootstrap_listing_ic95_inferior_rs": listing_low,
                "bootstrap_listing_ic95_superior_rs": listing_high,
                "bootstrap_host_ic95_inferior_rs": cluster_low,
                "bootstrap_host_ic95_superior_rs": cluster_high,
                "evidencia_estatistica": (
                    "inconclusiva" if inconclusive else "diferença sustentada"
                ),
                "relevancia_economica": "não avaliada nesta etapa",
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["preco_mediano_a", "preco_mediano_b"], ascending=[False, False]
    )


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
            "etapa": "Validação de preço e datas",
            "linhas_entrada": len(price),
            "linhas_saida": int(price["valid_row_for_price_analysis"].sum()),
            "registros_afetados": int((~price["valid_row_for_price_analysis"]).sum()),
            "funcao": "read_inputs + build_pair_table",
            "observacao": (
                "Linhas com ID/data/preço ausente ou inválido são quantificadas "
                "nos checks e não entram nas agregações; nesta execução, nenhuma."
            ),
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
    critical: bool = True,
) -> None:
    numeric_types = (int, float, np.integer, np.floating)
    if (
        isinstance(actual, numeric_types)
        and not isinstance(actual, (bool, np.bool_))
        and isinstance(expected, numeric_types)
        and not isinstance(expected, (bool, np.bool_))
    ):
        difference: Any = float(actual) - float(expected)
    else:
        difference = 0 if actual == expected else None
    checks.append(
        {
            "check": name,
            "actual": actual,
            "expected": expected,
            "difference": difference,
            "status": "OK" if passed else "FALHA",
            "critical": critical,
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
    primary_support: pd.DataFrame,
    decomposition: pd.DataFrame,
    decomposition_stages: pd.DataFrame,
    host_concentration: pd.DataFrame,
    pairwise: pd.DataFrame,
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []
    quality_checks = [
        ("IDs ausentes em Price", int(price[ID].isna().sum())),
        ("Preços raw ausentes", int(price["price_raw_missing"].sum())),
        ("Falhas de conversão de preço", int(price["price_conversion_failed"].sum())),
        ("Datas de estadia raw ausentes", int(price["stay_date_raw_missing"].sum())),
        ("Falhas de conversão de data de estadia", int(price["stay_date_conversion_failed"].sum())),
        ("Datas de captura raw ausentes", int(price["capture_date_raw_missing"].sum())),
        ("Falhas de conversão de data de captura", int(price["capture_date_conversion_failed"].sum())),
        ("Preços não finitos", int(price["price_non_finite"].sum())),
        ("Preços não positivos", int(price["price_non_positive"].sum())),
    ]
    for name, actual in quality_checks:
        add_check(
            checks,
            name,
            actual,
            0,
            actual == 0,
            "Validação explícita da ingestão; valores inválidos não entram nas agregações.",
        )
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
    maximum_reconciliation_error = float(decomposition["erro_reconciliacao_rs"].abs().max())
    add_check(
        checks,
        "Decomposição incremental reconcilia antes do arredondamento",
        maximum_reconciliation_error,
        0.0,
        maximum_reconciliation_error <= 1e-12,
        "Preço → datas → amostra é uma sequência dependente da ordem, não causal.",
    )
    decomposition_duplicates = int(
        decomposition.duplicated(["segment_key", "metodo"]).sum()
    )
    add_check(
        checks,
        "Uma linha por segmento–método na decomposição",
        decomposition_duplicates,
        0,
        decomposition_duplicates == 0,
        "",
    )
    expected_stage_rows = (
        decomposition["segment_key"].nunique() * len(METHODS) * 3
    )
    add_check(
        checks,
        "Etapas completas da decomposição",
        len(decomposition_stages),
        expected_stage_rows,
        len(decomposition_stages) == expected_stage_rows,
        "Três etapas para cada método e segmento principal.",
    )
    same_listing_mismatches = int(
        (
            decomposition["n_listings_1_pares_20_01"]
            != decomposition["n_listings_2_mesmos_listings_todas_datas"]
        ).sum()
    )
    add_check(
        checks,
        "Listings fixos entre as etapas de preço e datas",
        same_listing_mismatches,
        0,
        same_listing_mismatches == 0,
        "A etapa de datas não pode introduzir nem retirar listings.",
    )
    reference_pairs = decomposition.loc[
        decomposition["metodo"] == "snapshot_2025_01_20",
        ["segment_key", "n_pares_listing_data_1_pares_20_01"],
    ].rename(columns={"n_pares_listing_data_1_pares_20_01": "pares_referencia"})
    fixed_pair_check = decomposition.merge(
        reference_pairs, on="segment_key", how="left", validate="many_to_one"
    )
    fixed_pair_mismatches = int(
        (
            fixed_pair_check["n_pares_listing_data_1_pares_20_01"]
            != fixed_pair_check["pares_referencia"]
        ).sum()
    )
    add_check(
        checks,
        "Pares listing–data idênticos na primeira etapa",
        fixed_pair_mismatches,
        0,
        fixed_pair_mismatches == 0,
        "Todos os métodos usam exatamente os pares observados em 20/01.",
    )
    sample_decrease_count = int(
        (
            decomposition["n_listings_3_todos_listings_todas_datas"]
            < decomposition["n_listings_2_mesmos_listings_todas_datas"]
        ).sum()
    )
    add_check(
        checks,
        "A liberação da amostra não reduz listings",
        sample_decrease_count,
        0,
        sample_decrease_count == 0,
        "A terceira etapa pode apenas manter ou ampliar a amostra do método.",
    )
    latest_fixed = decomposition.loc[decomposition["metodo"] == "latest_available"]
    latest_fixed_max_difference = float(
        (latest_fixed["preco_mediano_1_pares_20_01"] - latest_fixed["preco_base_20_01"])
        .abs()
        .max()
    )
    add_check(
        checks,
        "Mais recente nos pares de 20/01 coincide com 20/01",
        latest_fixed_max_difference,
        0.0,
        latest_fixed_max_difference == 0,
        "Identidade por construção; não é evidência de estabilidade de preços.",
    )
    primary_segment_count = int(
        primary_support["n_listings_metodo_principal"].ge(PRIMARY_AIRBNB_MIN).sum()
    )
    add_check(
        checks,
        "Concentração cobre todos os segmentos principais",
        host_concentration["segment_key"].nunique(),
        primary_segment_count,
        host_concentration["segment_key"].nunique() == primary_segment_count,
        "owner_id vem de Details e não exige join com snapshots de Hosts.",
    )
    main_owner_missing = int(
        listing_methods.loc[
            (listing_methods["metodo"] == "snapshot_2025_01_20")
            & (listing_methods["tratamento_outlier"] == "original")
            & listing_methods["segment_key"].isin(set(host_concentration["segment_key"])),
            "owner_id",
        ].isna().sum()
    )
    add_check(
        checks,
        "owner_id ausente nos segmentos principais",
        main_owner_missing,
        0,
        main_owner_missing == 0,
        "Necessário para ponderação e bootstrap agrupados.",
    )
    expected_pairwise = primary_segment_count * (primary_segment_count - 1) // 2
    add_check(
        checks,
        "Todas as comparações pareadas principais foram produzidas",
        len(pairwise),
        expected_pairwise,
        len(pairwise) == expected_pairwise,
        "Cada par aparece uma vez; a ordem segue a mediana pontual.",
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
        "bootstrap_host_mediana_ic95_inferior",
        "bootstrap_host_mediana_ic95_superior",
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
    decomposition, decomposition_stages = build_incremental_decomposition(
        pair_tables, listing_base, primary_support
    )
    capture_changes = build_capture_change_diagnostic(
        matched_price, listing_base, primary_support
    )
    host_concentration = build_host_concentration(listing_methods, primary_support)
    pairwise = build_pairwise_differences(listing_methods, primary_support)
    checks = build_checks(
        details,
        mesh,
        price,
        listing_base,
        matched_price,
        orphan_price,
        listing_methods,
        pair_tables,
        primary_support,
        decomposition,
        decomposition_stages,
        host_concentration,
        pairwise,
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
    transformations = pd.concat(
        [
            transformations,
            pd.DataFrame(
                [
                    {
                        "etapa": "Decomposição incremental preço–datas–amostra",
                        "linhas_entrada": len(decomposition_stages),
                        "linhas_saida": len(decomposition),
                        "registros_afetados": len(decomposition_stages),
                        "funcao": "build_incremental_decomposition",
                        "observacao": (
                            "Mudanças condicionais à sequência escolhida; a soma "
                            "reconcilia com o total antes do arredondamento."
                        ),
                    },
                    {
                        "etapa": "Concentração por anfitrião",
                        "linhas_entrada": int(
                            listing_methods.loc[
                                (listing_methods["metodo"] == "snapshot_2025_01_20")
                                & (listing_methods["tratamento_outlier"] == "original")
                            ].shape[0]
                        ),
                        "linhas_saida": len(host_concentration),
                        "registros_afetados": len(host_concentration),
                        "funcao": "build_host_concentration",
                        "observacao": "Resultado principal mantém peso igual por listing.",
                    },
                    {
                        "etapa": "Contrastes pareados com bootstrap por host",
                        "linhas_entrada": int(
                            host_concentration["n_listings"].sum()
                        ),
                        "linhas_saida": len(pairwise),
                        "registros_afetados": len(pairwise),
                        "funcao": "build_pairwise_differences",
                        "observacao": (
                            "Reamostragem agrupada por owner_id preserva juntos os "
                            "listings do mesmo anfitrião."
                        ),
                    },
                    {
                        "etapa": "Diagnóstico de variação entre capturas",
                        "linhas_entrada": len(matched_price),
                        "linhas_saida": len(capture_changes),
                        "registros_afetados": int(capture_changes["pares_comuns"].sum()),
                        "funcao": "build_capture_change_diagnostic",
                        "observacao": (
                            "Compara somente pares listing–data comuns e dá peso "
                            "igual por listing; não mede ocupação."
                        ),
                    },
                ]
            ),
        ],
        ignore_index=True,
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
        "incremental_decomposition": [
            {key: json_value(value) for key, value in row.items()}
            for row in decomposition.to_dict("records")
        ],
        "capture_changes": [
            {key: json_value(value) for key, value in row.items()}
            for row in capture_changes.to_dict("records")
        ],
        "host_concentration": [
            {key: json_value(value) for key, value in row.items()}
            for row in host_concentration.to_dict("records")
        ],
        "pairwise_differences": [
            {key: json_value(value) for key, value in row.items()}
            for row in pairwise.to_dict("records")
        ],
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
            "critical_failed_count": int(
                ((checks["status"] != "OK") & checks["critical"]).sum()
            ),
        },
    }

    listing_methods.to_csv(LISTING_OUTPUT, index=False)
    segment_summary.to_csv(SEGMENT_OUTPUT, index=False)
    coverage.to_csv(COVERAGE_OUTPUT, index=False)
    calendar.to_csv(CALENDAR_OUTPUT, index=False)
    checks.to_csv(CHECKS_OUTPUT, index=False)
    transformations.to_csv(TRANSFORMATIONS_OUTPUT, index=False)
    decomposition.to_csv(DECOMPOSITION_OUTPUT, index=False)
    host_concentration.to_csv(HOST_CONCENTRATION_OUTPUT, index=False)
    pairwise.to_csv(PAIRWISE_OUTPUT, index=False)
    capture_changes.to_csv(CAPTURE_CHANGES_OUTPUT, index=False)
    SUMMARY_OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    if summary["checks"]["critical_failed_count"]:
        raise RuntimeError(
            f"{summary['checks']['critical_failed_count']} validações críticas falharam; "
            f"consulte {CHECKS_OUTPUT.relative_to(ROOT)}."
        )

    print(
        "Análise Airbnb concluída: "
        f"{len(price):,} linhas de preço; "
        f"{len(listing_methods):,} linhas listing–método–tratamento; "
        f"checks={'OK' if summary['checks']['all_passed'] else 'FALHA'}"
    )
if __name__ == "__main__":
    main()
