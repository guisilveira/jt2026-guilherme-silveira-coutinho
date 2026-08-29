#!/usr/bin/env python3
"""Ciclo 2: perfis, localizações e tese operacional dos compactos.

Escopo deliberado:
- usa Details, Mesh, Price_AV e o dado derivado reproduzível do ciclo 1;
- compara preços anunciados, nunca ocupação, receita ou retorno;
- não usa VivaReal nem altera CSVs originais;
- calcula uma observação por listing antes de agregar segmentos.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_airbnb_prices import (
    BOOTSTRAP_ITERATIONS,
    DETAILS_FILE,
    ID,
    MAIN_CAPTURE,
    MESH_FILE,
    PRICE_FILE,
    PRIMARY_AIRBNB_MIN,
    EXPLORATORY_AIRBNB_MIN,
    build_calendar_diagnostics,
    build_listing_base,
    build_pair_table,
    build_primary_support,
    deterministic_seed,
    json_value,
    read_inputs,
    require,
    sha256,
)


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
GENERATED_DIR = ROOT / "reports" / "generated"
FIGURES_DIR = ROOT / "reports" / "figures"

CYCLE1_LISTINGS = PROCESSED_DIR / "airbnb_listing_prices.csv"
CYCLE1_CALENDAR = GENERATED_DIR / "airbnb_price_calendar.csv"
LISTING_OUTPUT = PROCESSED_DIR / "airbnb_listing_profile_metrics.csv"
SEGMENT_OUTPUT = GENERATED_DIR / "airbnb_profile_segments.csv"
CONTRAST_OUTPUT = GENERATED_DIR / "airbnb_profile_contrasts.csv"
ROBUSTNESS_OUTPUT = GENERATED_DIR / "airbnb_profile_robustness.csv"
LOCATION_OUTPUT = GENERATED_DIR / "airbnb_location_profile_matrix.csv"
CAPACITY_OUTPUT = GENERATED_DIR / "airbnb_capacity_quality.csv"
CHECKS_OUTPUT = GENERATED_DIR / "airbnb_profile_checks.csv"
TRANSFORMATIONS_OUTPUT = GENERATED_DIR / "airbnb_profile_transformations.csv"
SUMMARY_OUTPUT = GENERATED_DIR / "airbnb_profile_summary.json"
REPORT_OUTPUT = ROOT / "reports" / "airbnb_profile_location_analysis.md"

TARGET_KEY = "centro|apartamento|1 quarto"
MAIN_METHOD = "snapshot_2025_01_20"
MEDIAN_METHOD = "median_across_captures"
LATEST_METHOD = "latest_available"
ORIGINAL = "original"

METRICS = {
    "preco_total": "Preço anunciado total",
    "preco_por_hospede": "Preço anunciado por hóspede comportado",
    "preco_por_quarto": "Preço anunciado por quarto",
}


def support_label(n: int) -> str:
    if n >= PRIMARY_AIRBNB_MIN:
        return "principal"
    if n >= EXPLORATORY_AIRBNB_MIN:
        return "exploratório"
    return "evidência insuficiente"


def combined_support(n_a: int, n_b: int) -> str:
    return support_label(min(n_a, n_b))


def audit_capacity(
    details: pd.DataFrame, listing_base: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Cria flags sem consultar preços, conforme regra pré-registrada."""
    capacity = details[[ID, "number_of_guests", "number_of_bedrooms"]].copy()
    capacity["capacidade_raw_missing"] = capacity["number_of_guests"].isna()
    capacity["capacidade"] = pd.to_numeric(
        capacity["number_of_guests"], errors="coerce"
    )
    capacity["capacidade_conversao_falhou"] = (
        ~capacity["capacidade_raw_missing"] & capacity["capacidade"].isna()
    )
    capacity["capacidade_nao_finita"] = capacity["capacidade"].notna() & ~np.isfinite(
        capacity["capacidade"].astype(float)
    )
    capacity["capacidade_zero"] = capacity["capacidade"].eq(0)
    capacity["capacidade_negativa"] = capacity["capacidade"].lt(0)
    capacity["capacidade_positiva_valida"] = (
        capacity["capacidade"].notna()
        & ~capacity["capacidade_nao_finita"]
        & capacity["capacidade"].gt(0)
    )
    capacity["capacidade_positiva_nao_inteira"] = (
        capacity["capacidade_positiva_valida"]
        & ~np.isclose(capacity["capacidade"] % 1, 0)
    )
    capacity["quartos"] = pd.to_numeric(
        capacity["number_of_bedrooms"], errors="coerce"
    )
    capacity["quartos_validos_para_razao"] = (
        capacity["quartos"].notna()
        & np.isfinite(capacity["quartos"].astype(float))
        & capacity["quartos"].gt(0)
    )
    capacity = capacity.merge(
        listing_base[[ID, "tipo_imovel", "segment_key", "residential_scope"]],
        on=ID,
        how="left",
        validate="one_to_one",
    )

    positive = capacity.loc[capacity["capacidade_positiva_valida"], "capacidade"]
    global_q25 = float(positive.quantile(0.25))
    global_q75 = float(positive.quantile(0.75))
    global_fence = global_q75 + 3.0 * (global_q75 - global_q25)

    profile_stats = (
        capacity.loc[capacity["capacidade_positiva_valida"]]
        .groupby(["tipo_imovel", "quartos"], dropna=False)["capacidade"]
        .agg(
            n_perfil="size",
            capacidade_p25=lambda s: s.quantile(0.25),
            capacidade_p75=lambda s: s.quantile(0.75),
        )
        .reset_index()
    )
    profile_stats["cerca_externa_perfil"] = profile_stats["capacidade_p75"] + 3.0 * (
        profile_stats["capacidade_p75"] - profile_stats["capacidade_p25"]
    )
    profile_stats["usa_cerca_perfil"] = profile_stats["n_perfil"] >= 30
    profile_stats["limite_capacidade_suspeita"] = np.where(
        profile_stats["usa_cerca_perfil"],
        profile_stats["cerca_externa_perfil"],
        global_fence,
    )
    capacity = capacity.merge(
        profile_stats[
            [
                "tipo_imovel",
                "quartos",
                "n_perfil",
                "usa_cerca_perfil",
                "limite_capacidade_suspeita",
            ]
        ],
        on=["tipo_imovel", "quartos"],
        how="left",
        validate="many_to_one",
    )
    capacity["capacidade_acima_cerca_externa"] = (
        capacity["capacidade_positiva_valida"]
        & capacity["capacidade"].gt(capacity["limite_capacidade_suspeita"])
    )
    capacity["capacidade_menor_que_quartos"] = (
        capacity["capacidade_positiva_valida"]
        & capacity["quartos_validos_para_razao"]
        & capacity["capacidade"].lt(capacity["quartos"])
    )
    capacity["capacidade_positiva_suspeita"] = (
        capacity["capacidade_positiva_nao_inteira"]
        | capacity["capacidade_acima_cerca_externa"]
        | capacity["capacidade_menor_que_quartos"]
    )

    rows = [
        ("Listings em Details", len(capacity), "universo"),
        ("Capacidade ausente", int(capacity["capacidade_raw_missing"].sum()), "inválido"),
        (
            "Falha de conversão da capacidade",
            int(capacity["capacidade_conversao_falhou"].sum()),
            "inválido",
        ),
        ("Capacidade não finita", int(capacity["capacidade_nao_finita"].sum()), "inválido"),
        ("Capacidade zero", int(capacity["capacidade_zero"].sum()), "inválido"),
        ("Capacidade negativa", int(capacity["capacidade_negativa"].sum()), "inválido"),
        (
            "Capacidade positiva válida",
            int(capacity["capacidade_positiva_valida"].sum()),
            "resultado principal",
        ),
        (
            "Capacidade positiva não inteira",
            int(capacity["capacidade_positiva_nao_inteira"].sum()),
            "flag suspeita",
        ),
        (
            "Capacidade acima da cerca externa",
            int(capacity["capacidade_acima_cerca_externa"].sum()),
            "flag suspeita",
        ),
        (
            "Capacidade menor que quartos",
            int(capacity["capacidade_menor_que_quartos"].sum()),
            "flag suspeita",
        ),
        (
            "Capacidade positiva suspeita (união)",
            int(capacity["capacidade_positiva_suspeita"].sum()),
            "preservada; retirada apenas em sensibilidade",
        ),
        (
            "Quartos zero",
            int(capacity["quartos"].eq(0).sum()),
            "fora somente de preço por quarto",
        ),
        (
            "Quartos positivos válidos",
            int(capacity["quartos_validos_para_razao"].sum()),
            "elegível para preço por quarto",
        ),
    ]
    audit = pd.DataFrame(rows, columns=["regra", "n_listings", "tratamento"])
    audit["proporcao_details"] = audit["n_listings"] / len(capacity)
    thresholds = {
        "capacidade_p25_global": global_q25,
        "capacidade_p75_global": global_q75,
        "cerca_externa_global": float(global_fence),
    }
    return capacity, audit, thresholds


def build_calendar_adjusted_listings(
    listing_base: pd.DataFrame,
    price: pd.DataFrame,
    cycle1_listings: pd.DataFrame,
) -> tuple[pd.DataFrame, float]:
    """Reutiliza integralmente universo, escala e ajuste do ciclo 1."""
    matched = price.loc[price[ID].isin(set(listing_base[ID]))].copy()
    snapshot_pair = build_pair_table(matched, MAIN_METHOD)
    primary_support = build_primary_support(cycle1_listings)
    _, adjusted_pair, reference = build_calendar_diagnostics(
        snapshot_pair,
        listing_base,
        primary_support,
    )
    listing = (
        adjusted_pair.groupby(ID, as_index=False)["price_calendar_adjusted"]
        .median()
        .rename(columns={"price_calendar_adjusted": "preco_anunciado_tipico"})
    )
    return listing, reference


def build_listing_metrics(
    cycle1: pd.DataFrame,
    capacity: pd.DataFrame,
    calendar_listing: pd.DataFrame,
    listing_base: pd.DataFrame,
) -> pd.DataFrame:
    cycle1[ID] = cycle1[ID].astype("string")
    require(
        not bool(cycle1.duplicated([ID, "metodo", "tratamento_outlier"]).any()),
        "O dado do ciclo 1 perdeu o grain listing–método–tratamento.",
    )
    cap_columns = [
        ID,
        "capacidade",
        "capacidade_positiva_valida",
        "capacidade_positiva_suspeita",
        "capacidade_positiva_nao_inteira",
        "capacidade_acima_cerca_externa",
        "capacidade_menor_que_quartos",
        "limite_capacidade_suspeita",
        "quartos_validos_para_razao",
    ]
    listing = cycle1.drop(columns=["number_of_guests"], errors="ignore").merge(
        capacity[cap_columns], on=ID, how="left", validate="many_to_one"
    )
    require(
        bool(listing["capacidade_positiva_valida"].notna().all()),
        "Há listings de preço sem diagnóstico de capacidade.",
    )

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
        "residential_scope",
    ]
    calendar = calendar_listing.merge(
        listing_base[base_columns], on=ID, how="left", validate="one_to_one"
    ).merge(capacity[cap_columns], on=ID, how="left", validate="one_to_one")
    calendar["metodo"] = "snapshot_calendar_adjusted"
    calendar["metodo_label"] = "Captura de 20/01 ajustada por calendário"
    calendar["tratamento_outlier"] = ORIGINAL
    calendar["tratamento_outlier_label"] = "Valores originais"
    calendar["n_datas_estadia"] = np.nan
    calendar["possui_preco_suspeito"] = False
    calendar["n_precos_suspeitos"] = 0
    listing = pd.concat([listing, calendar], ignore_index=True, sort=False)

    listing["preco_total"] = listing["preco_anunciado_tipico"]
    listing["preco_por_hospede"] = np.where(
        listing["capacidade_positiva_valida"],
        listing["preco_total"] / listing["capacidade"],
        np.nan,
    )
    listing["preco_por_hospede_sem_capacidade_suspeita"] = np.where(
        listing["capacidade_positiva_valida"]
        & ~listing["capacidade_positiva_suspeita"],
        listing["preco_total"] / listing["capacidade"],
        np.nan,
    )
    listing["preco_por_quarto"] = np.where(
        listing["quartos_validos_para_razao"],
        listing["preco_total"] / listing["quartos"],
        np.nan,
    )
    require(
        bool(
            (
                listing.loc[
                    listing["preco_por_hospede"].notna(), "capacidade"
                ]
                > 0
            ).all()
        ),
        "Preço por hóspede usou divisor não positivo.",
    )
    require(
        bool(
            (
                listing.loc[listing["preco_por_quarto"].notna(), "quartos"] > 0
            ).all()
        ),
        "Preço por quarto usou divisor não positivo.",
    )
    return listing


def to_metric_long(listing: pd.DataFrame) -> pd.DataFrame:
    columns = [
        ID,
        "owner_id",
        "bairro",
        "tipo_imovel",
        "quartos",
        "segmento_imoveis",
        "segment_key",
        "residential_scope",
        "metodo",
        "metodo_label",
        "tratamento_outlier",
        "tratamento_outlier_label",
    ]
    frames: list[pd.DataFrame] = []
    specifications = [
        ("preco_total", "preco_total", "não aplicável"),
        ("preco_por_hospede", "preco_por_hospede", "todas as capacidades positivas"),
        (
            "preco_por_hospede",
            "preco_por_hospede_sem_capacidade_suspeita",
            "sem capacidades positivas suspeitas",
        ),
        ("preco_por_quarto", "preco_por_quarto", "não aplicável"),
    ]
    for metric, value_column, capacity_treatment in specifications:
        frame = listing[columns + [value_column]].rename(columns={value_column: "valor"})
        frame["metrica"] = metric
        frame["metrica_label"] = METRICS[metric]
        frame["tratamento_capacidade"] = capacity_treatment
        frame = frame.loc[frame["valor"].notna()].copy()
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    require(
        bool(np.isfinite(result["valor"]).all() and (result["valor"] > 0).all()),
        "Métricas derivadas precisam ser positivas e finitas.",
    )
    return result


def cluster_interval(
    group: pd.DataFrame, value_column: str, seed: int
) -> tuple[float, float]:
    usable = group[["owner_id", value_column]].dropna()
    owners = usable["owner_id"].drop_duplicates().to_numpy()
    if len(owners) < 5:
        return np.nan, np.nan
    by_owner = {
        owner: owner_group[value_column].to_numpy(float)
        for owner, owner_group in usable.groupby("owner_id")
    }
    rng = np.random.default_rng(seed)
    medians = np.empty(BOOTSTRAP_ITERATIONS)
    for i in range(BOOTSTRAP_ITERATIONS):
        sampled = rng.choice(owners, size=len(owners), replace=True)
        medians[i] = np.median(np.concatenate([by_owner[o] for o in sampled]))
    return tuple(float(x) for x in np.quantile(medians, [0.025, 0.975]))


def host_sensitivity(group: pd.DataFrame) -> dict[str, Any]:
    counts = group.groupby("owner_id")[ID].nunique().sort_values(ascending=False)
    top_count = int(counts.iloc[0])
    top_owners = counts.loc[counts == top_count].index.tolist()
    host_medians = group.groupby("owner_id")["valor"].median()
    equal_host = float(host_medians.median())
    without = []
    for owner in top_owners:
        values = group.loc[group["owner_id"] != owner, "valor"]
        if len(values):
            without.append(float(values.median()))
    return {
        "n_hosts": int(counts.size),
        "listings_maior_host": top_count,
        "participacao_maior_host": top_count / group[ID].nunique(),
        "n_hosts_empatados_topo": len(top_owners),
        "mediana_peso_igual_host": equal_host,
        "mediana_sem_maior_host_min": min(without) if without else np.nan,
        "mediana_sem_maior_host_max": max(without) if without else np.nan,
    }


def build_segment_summary(metric_long: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "metodo",
        "metodo_label",
        "tratamento_outlier",
        "tratamento_outlier_label",
        "metrica",
        "metrica_label",
        "tratamento_capacidade",
        "segment_key",
        "segmento_imoveis",
        "bairro",
        "tipo_imovel",
        "quartos",
    ]
    rows: list[dict[str, Any]] = []
    residential = metric_long.loc[metric_long["residential_scope"]].copy()
    for values, group in residential.groupby(keys, dropna=False, sort=False):
        row = dict(zip(keys, values))
        n = int(group[ID].nunique())
        low, high = cluster_interval(
            group, "valor", deterministic_seed(*(str(v) for v in values))
        )
        row.update(
            {
                "n_listings": n,
                "preco_mediano": float(group["valor"].median()),
                "preco_p25": float(group["valor"].quantile(0.25)),
                "preco_p75": float(group["valor"].quantile(0.75)),
                "bootstrap_host_ic95_inferior": low,
                "bootstrap_host_ic95_superior": high,
                "suporte_metrica": support_label(n),
                **host_sensitivity(group),
            }
        )
        rows.append(row)
    summary = pd.DataFrame(rows)
    summary["rank_dentro_metodo_metrica"] = summary.groupby(
        ["metodo", "tratamento_outlier", "metrica", "tratamento_capacidade"]
    )["preco_mediano"].rank(method="min", ascending=False)
    return summary.sort_values(
        ["metodo", "tratamento_outlier", "metrica", "preco_mediano"],
        ascending=[True, True, True, False],
    )


def build_contrast_definitions(main_total: pd.DataFrame) -> pd.DataFrame:
    supported = main_total.loc[main_total["n_listings"] >= EXPLORATORY_AIRBNB_MIN].copy()
    require(TARGET_KEY in set(supported["segment_key"]), "Segmento-alvo não encontrado.")
    definitions: dict[tuple[str, str], dict[str, Any]] = {}

    def add(a: pd.Series, b: pd.Series, family: str, scope: str) -> None:
        key = (str(a["segment_key"]), str(b["segment_key"]))
        current = definitions.get(key)
        priority = 0 if scope == "principal pré-definida" else 1
        if current is None or priority < current["_priority"]:
            definitions[key] = {
                "segment_key_a": key[0],
                "segmento_a": a["segmento_imoveis"],
                "segment_key_b": key[1],
                "segmento_b": b["segmento_imoveis"],
                "familia_comparacao": family,
                "escopo_comparacao": scope,
                "_priority": priority,
            }

    target = supported.loc[supported["segment_key"] == TARGET_KEY].iloc[0]
    location = supported.loc[
        (supported["tipo_imovel"] == "apartamento")
        & supported["quartos"].eq(1)
        & supported["segment_key"].ne(TARGET_KEY)
    ]
    for _, other in location.iterrows():
        add(target, other, "tese: vantagem de localização", "principal pré-definida")

    larger = supported.loc[
        (supported["bairro"] == "Centro")
        & (supported["tipo_imovel"] == "apartamento")
        & supported["quartos"].gt(1)
    ].sort_values("quartos")
    for _, other in larger.iterrows():
        add(target, other, "tese: vantagem do compacto", "principal pré-definida")

    for (_, _), group in supported.groupby(["tipo_imovel", "quartos"], dropna=False):
        rows = list(group.sort_values("bairro").iterrows())
        for (_, left), (_, right) in combinations(rows, 2):
            add(left, right, "localização dentro do mesmo perfil", "exploratória")

    for (_, _), group in supported.groupby(["bairro", "tipo_imovel"], dropna=False):
        rows = list(group.sort_values("quartos").iterrows())
        for (_, left), (_, right) in combinations(rows, 2):
            add(left, right, "quartos dentro do mesmo bairro e tipo", "exploratória")

    result = pd.DataFrame(definitions.values()).drop(columns="_priority")
    return result.sort_values(["escopo_comparacao", "familia_comparacao", "segmento_a", "segmento_b"])


def cluster_difference(
    group_a: pd.DataFrame, group_b: pd.DataFrame, seed: int
) -> tuple[float, float]:
    owners = np.array(
        sorted(set(group_a["owner_id"].dropna()) | set(group_b["owner_id"].dropna()))
    )
    if len(owners) < 5:
        return np.nan, np.nan
    a_by_owner = {
        owner: g["valor"].to_numpy(float) for owner, g in group_a.groupby("owner_id")
    }
    b_by_owner = {
        owner: g["valor"].to_numpy(float) for owner, g in group_b.groupby("owner_id")
    }
    rng = np.random.default_rng(seed)
    differences: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sampled = rng.choice(owners, size=len(owners), replace=True)
        a_values = [a_by_owner[o] for o in sampled if o in a_by_owner]
        b_values = [b_by_owner[o] for o in sampled if o in b_by_owner]
        if a_values and b_values:
            differences.append(
                float(np.median(np.concatenate(a_values)) - np.median(np.concatenate(b_values)))
            )
    if len(differences) < BOOTSTRAP_ITERATIONS * 0.9:
        return np.nan, np.nan
    return tuple(float(x) for x in np.quantile(differences, [0.025, 0.975]))


def build_main_contrasts(
    metric_long: pd.DataFrame, definitions: pd.DataFrame
) -> pd.DataFrame:
    main = metric_long.loc[
        (metric_long["metodo"] == MAIN_METHOD)
        & (metric_long["tratamento_outlier"] == ORIGINAL)
        & (
            (metric_long["metrica"] != "preco_por_hospede")
            | (metric_long["tratamento_capacidade"] == "todas as capacidades positivas")
        )
    ].copy()
    rows: list[dict[str, Any]] = []
    for definition in definitions.to_dict("records"):
        for metric, metric_label in METRICS.items():
            a = main.loc[
                (main["segment_key"] == definition["segment_key_a"])
                & (main["metrica"] == metric)
            ]
            b = main.loc[
                (main["segment_key"] == definition["segment_key_b"])
                & (main["metrica"] == metric)
            ]
            if a.empty or b.empty:
                continue
            n_a, n_b = int(a[ID].nunique()), int(b[ID].nunique())
            med_a, med_b = float(a["valor"].median()), float(b["valor"].median())
            delta = med_a - med_b
            low, high = cluster_difference(
                a,
                b,
                deterministic_seed(
                    definition["segment_key_a"], definition["segment_key_b"], metric
                ),
            )
            evidence = (
                "diferença estatisticamente sustentada"
                if pd.notna(low) and pd.notna(high) and (low > 0 or high < 0)
                else "evidência inconclusiva"
            )
            rows.append(
                {
                    **definition,
                    "metrica": metric,
                    "metrica_label": metric_label,
                    "n_listings_a": n_a,
                    "n_listings_b": n_b,
                    "n_hosts_a": int(a["owner_id"].nunique()),
                    "n_hosts_b": int(b["owner_id"].nunique()),
                    "hosts_nos_dois_segmentos": int(
                        len(set(a["owner_id"]) & set(b["owner_id"]))
                    ),
                    "mediana_a": med_a,
                    "p25_a": float(a["valor"].quantile(0.25)),
                    "p75_a": float(a["valor"].quantile(0.75)),
                    "mediana_b": med_b,
                    "p25_b": float(b["valor"].quantile(0.25)),
                    "p75_b": float(b["valor"].quantile(0.75)),
                    "diferenca_rs": delta,
                    "diferenca_pct_sobre_b": delta / med_b if med_b else np.nan,
                    "bootstrap_host_ic95_inferior_rs": low,
                    "bootstrap_host_ic95_superior_rs": high,
                    "evidencia_estatistica": evidence,
                    "suporte_comparacao": combined_support(n_a, n_b),
                    "relevancia_economica": "não avaliada neste ciclo",
                }
            )
    return pd.DataFrame(rows)


def point_difference(
    metric_long: pd.DataFrame,
    segment_a: str,
    segment_b: str,
    metric: str,
    method: str,
    outlier: str,
    capacity_treatment: str,
) -> dict[str, Any] | None:
    subset = metric_long.loc[
        (metric_long["metodo"] == method)
        & (metric_long["tratamento_outlier"] == outlier)
        & (metric_long["metrica"] == metric)
        & (metric_long["tratamento_capacidade"] == capacity_treatment)
    ]
    a = subset.loc[subset["segment_key"] == segment_a]
    b = subset.loc[subset["segment_key"] == segment_b]
    if a.empty or b.empty:
        return None
    med_a, med_b = float(a["valor"].median()), float(b["valor"].median())
    return {
        "n_listings_a": int(a[ID].nunique()),
        "n_listings_b": int(b[ID].nunique()),
        "mediana_a": med_a,
        "mediana_b": med_b,
        "diferenca_rs": med_a - med_b,
        "diferenca_pct_sobre_b": (med_a - med_b) / med_b if med_b else np.nan,
    }


def build_robustness(
    metric_long: pd.DataFrame,
    segment_summary: pd.DataFrame,
    definitions: pd.DataFrame,
) -> pd.DataFrame:
    primary = definitions.loc[definitions["escopo_comparacao"] == "principal pré-definida"]
    scenarios = [
        ("headline", MAIN_METHOD, ORIGINAL, "todas as capacidades positivas"),
        ("mediana entre capturas", MEDIAN_METHOD, ORIGINAL, "todas as capacidades positivas"),
        ("mais recente (diagnóstico)", LATEST_METHOD, ORIGINAL, "todas as capacidades positivas"),
        ("sem preços ≥ R$ 10 mil", MAIN_METHOD, "exclude_suspicious_prices", "todas as capacidades positivas"),
        ("sem os três listings afetados", MAIN_METHOD, "exclude_affected_listings", "todas as capacidades positivas"),
        ("calendário ajustado", "snapshot_calendar_adjusted", ORIGINAL, "todas as capacidades positivas"),
        ("sem capacidades positivas suspeitas", MAIN_METHOD, ORIGINAL, "sem capacidades positivas suspeitas"),
    ]
    rows: list[dict[str, Any]] = []
    for definition in primary.to_dict("records"):
        for metric, metric_label in METRICS.items():
            for scenario, method, outlier, capacity in scenarios:
                cap = capacity if metric == "preco_por_hospede" else "não aplicável"
                if scenario == "sem capacidades positivas suspeitas" and metric != "preco_por_hospede":
                    continue
                result = point_difference(
                    metric_long,
                    definition["segment_key_a"],
                    definition["segment_key_b"],
                    metric,
                    method,
                    outlier,
                    cap,
                )
                if result:
                    rows.append(
                        {
                            **definition,
                            "metrica": metric,
                            "metrica_label": metric_label,
                            "cenario_sensibilidade": scenario,
                            "metodo": method,
                            "tratamento_outlier": outlier,
                            "tratamento_capacidade": cap,
                            **result,
                        }
                    )

            main_summary = segment_summary.loc[
                (segment_summary["metodo"] == MAIN_METHOD)
                & (segment_summary["tratamento_outlier"] == ORIGINAL)
                & (segment_summary["metrica"] == metric)
                & (
                    segment_summary["tratamento_capacidade"]
                    == ("todas as capacidades positivas" if metric == "preco_por_hospede" else "não aplicável")
                )
                & segment_summary["segment_key"].isin(
                    [definition["segment_key_a"], definition["segment_key_b"]]
                )
            ]
            if len(main_summary) == 2:
                a = main_summary.loc[
                    main_summary["segment_key"] == definition["segment_key_a"]
                ].iloc[0]
                b = main_summary.loc[
                    main_summary["segment_key"] == definition["segment_key_b"]
                ].iloc[0]
                delta_host = float(a["mediana_peso_igual_host"] - b["mediana_peso_igual_host"])
                rows.append(
                    {
                        **definition,
                        "metrica": metric,
                        "metrica_label": metric_label,
                        "cenario_sensibilidade": "peso igual por anfitrião",
                        "metodo": MAIN_METHOD,
                        "tratamento_outlier": ORIGINAL,
                        "tratamento_capacidade": "sensibilidade de anfitrião",
                        "n_listings_a": int(a["n_listings"]),
                        "n_listings_b": int(b["n_listings"]),
                        "mediana_a": float(a["mediana_peso_igual_host"]),
                        "mediana_b": float(b["mediana_peso_igual_host"]),
                        "diferenca_rs": delta_host,
                        "diferenca_pct_sobre_b": delta_host / b["mediana_peso_igual_host"] if b["mediana_peso_igual_host"] else np.nan,
                    }
                )
                rows.append(
                    {
                        **definition,
                        "metrica": metric,
                        "metrica_label": metric_label,
                        "cenario_sensibilidade": "sem maior anfitrião (faixa)",
                        "metodo": MAIN_METHOD,
                        "tratamento_outlier": ORIGINAL,
                        "tratamento_capacidade": "sensibilidade de anfitrião",
                        "n_listings_a": int(a["n_listings"]),
                        "n_listings_b": int(b["n_listings"]),
                        "mediana_a": np.nan,
                        "mediana_b": np.nan,
                        "diferenca_rs": np.nan,
                        "diferenca_pct_sobre_b": np.nan,
                        "diferenca_min_rs": float(a["mediana_sem_maior_host_min"] - b["mediana_sem_maior_host_max"]),
                        "diferenca_max_rs": float(a["mediana_sem_maior_host_max"] - b["mediana_sem_maior_host_min"]),
                    }
                )
    return pd.DataFrame(rows)


def build_location_matrix(main_total: pd.DataFrame, contrasts: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    profile_groups = main_total.groupby(["tipo_imovel", "quartos"], dropna=False)
    for (property_type, bedrooms), group in profile_groups:
        eligible = group.loc[group["n_listings"] >= PRIMARY_AIRBNB_MIN]
        for (_, a), (_, b) in combinations(list(eligible.sort_values("bairro").iterrows()), 2):
            match = contrasts.loc[
                (contrasts["metrica"] == "preco_total")
                & (
                    (
                        (contrasts["segment_key_a"] == a["segment_key"])
                        & (contrasts["segment_key_b"] == b["segment_key"])
                    )
                    | (
                        (contrasts["segment_key_a"] == b["segment_key"])
                        & (contrasts["segment_key_b"] == a["segment_key"])
                    )
                )
            ]
            if match.empty:
                continue
            result = match.iloc[0]
            orientation = 1 if result["segment_key_a"] == a["segment_key"] else -1
            rows.append(
                {
                    "bairro_a": a["bairro"],
                    "bairro_b": b["bairro"],
                    "tipo_imovel": property_type,
                    "quartos": bedrooms,
                    "perfil": f"{property_type} · {int(bedrooms) if float(bedrooms).is_integer() else bedrooms} quartos",
                    "n_listings_a": int(a["n_listings"]),
                    "n_listings_b": int(b["n_listings"]),
                    "mediana_a": float(a["preco_mediano"]),
                    "mediana_b": float(b["preco_mediano"]),
                    "diferenca_a_menos_b_rs": orientation * float(result["diferenca_rs"]),
                    "diferenca_a_menos_b_pct_sobre_b": (
                        (float(a["preco_mediano"]) - float(b["preco_mediano"]))
                        / float(b["preco_mediano"])
                    ),
                    "ic95_inferior_rs": orientation
                    * (
                        float(result["bootstrap_host_ic95_inferior_rs"])
                        if orientation == 1
                        else float(result["bootstrap_host_ic95_superior_rs"])
                    ),
                    "ic95_superior_rs": orientation
                    * (
                        float(result["bootstrap_host_ic95_superior_rs"])
                        if orientation == 1
                        else float(result["bootstrap_host_ic95_inferior_rs"])
                    ),
                    "evidencia_estatistica": result["evidencia_estatistica"],
                }
            )
    matrix = pd.DataFrame(rows)
    if not matrix.empty:
        matrix["par_bairros"] = matrix.apply(
            lambda r: " × ".join(sorted([r["bairro_a"], r["bairro_b"]])), axis=1
        )
        matrix["n_perfis_equivalentes_no_par"] = matrix.groupby("par_bairros")["perfil"].transform("nunique")
    return matrix


def add_check(
    rows: list[dict[str, Any]],
    name: str,
    actual: Any,
    expected: Any,
    passed: bool,
    critical: bool,
    notes: str,
) -> None:
    difference = np.nan
    if isinstance(actual, (int, float, np.number)) and isinstance(expected, (int, float, np.number)):
        difference = float(actual) - float(expected)
    rows.append(
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
    listing: pd.DataFrame,
    metric_long: pd.DataFrame,
    segments: pd.DataFrame,
    contrasts: pd.DataFrame,
    capacity: pd.DataFrame,
    cycle1_calendar: pd.DataFrame,
    raw_hashes_before: dict[str, str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cycle1 = listing.loc[listing["metodo"] != "snapshot_calendar_adjusted"]
    add_check(rows, "IDs únicos em Details", details[ID].nunique(), len(details), details[ID].nunique() == len(details), True, "Chave da base principal.")
    duplicate_count = int(cycle1.duplicated([ID, "metodo", "tratamento_outlier"]).sum())
    add_check(rows, "Grain listing–método–tratamento", duplicate_count, 0, duplicate_count == 0, True, "Nenhum listing recebe peso extra por duplicação.")
    add_check(rows, "Diagnóstico de capacidade completo", capacity[ID].nunique(), len(details), capacity[ID].nunique() == len(details), True, "Uma linha de capacidade por listing.")
    invalid_guest_metric = int(metric_long.loc[(metric_long["metrica"] == "preco_por_hospede") & ~np.isfinite(metric_long["valor"]), ID].nunique())
    add_check(rows, "Métricas por hóspede finitas", invalid_guest_metric, 0, invalid_guest_metric == 0, True, "Ausentes e divisores inválidos não entram na razão.")
    nonpositive_values = int((metric_long["valor"] <= 0).sum())
    add_check(rows, "Métricas positivas", nonpositive_values, 0, nonpositive_values == 0, True, "Preços e divisores precisam ser positivos.")
    main_listing_count = int(cycle1.loc[(cycle1["metodo"] == MAIN_METHOD) & (cycle1["tratamento_outlier"] == ORIGINAL), ID].nunique())
    expected_main = pd.read_csv(CYCLE1_LISTINGS, dtype={ID: "string"}).loc[lambda x: (x["metodo"] == MAIN_METHOD) & (x["tratamento_outlier"] == ORIGINAL), ID].nunique()
    add_check(rows, "Reconcilia listings do headline com ciclo 1", main_listing_count, int(expected_main), main_listing_count == expected_main, True, "Nenhum listing foi perdido na preparação do ciclo 2.")
    duplicate_segments = int(segments.duplicated(["metodo", "tratamento_outlier", "metrica", "tratamento_capacidade", "segment_key"]).sum())
    add_check(rows, "Resumo tem uma linha por segmento e cenário", duplicate_segments, 0, duplicate_segments == 0, True, "Evita agregação duplicada.")
    main_contrast_dup = int(contrasts.duplicated(["segment_key_a", "segment_key_b", "metrica"]).sum())
    add_check(rows, "Contrastes do headline sem duplicação", main_contrast_dup, 0, main_contrast_dup == 0, True, "Uma estimativa por par e métrica.")
    percent_error = np.nanmax(np.abs(contrasts["diferenca_pct_sobre_b"] - contrasts["diferenca_rs"] / contrasts["mediana_b"])) if len(contrasts) else 0.0
    add_check(rows, "Percentuais reconciliam com diferença em R$", float(percent_error), 0.0, bool(percent_error < 1e-12), True, "Percentual usa o segmento B como referência.")
    wrong_room = int(metric_long.loc[(metric_long["metrica"] == "preco_por_quarto") & metric_long["quartos"].le(0), ID].nunique())
    add_check(rows, "Zero quarto fora da razão por quarto", wrong_room, 0, wrong_room == 0, True, "Zero quarto permanece nas demais leituras.")
    general_uncontrolled = int(contrasts["familia_comparacao"].eq("bairro sem controle de perfil").sum())
    add_check(rows, "Nenhum contraste bruto de bairro", general_uncontrolled, 0, general_uncontrolled == 0, True, "Localização é comparada dentro do perfil.")
    missing_main_owner = int(
        cycle1.loc[
            (cycle1["metodo"] == MAIN_METHOD)
            & (cycle1["tratamento_outlier"] == ORIGINAL)
            & cycle1["residential_scope"],
            "owner_id",
        ].isna().sum()
    )
    add_check(rows, "Owner presente no headline residencial", missing_main_owner, 0, missing_main_owner == 0, True, "Necessário para bootstrap agrupado.")
    suspicious_union = (
        capacity["capacidade_positiva_nao_inteira"]
        | capacity["capacidade_acima_cerca_externa"]
        | capacity["capacidade_menor_que_quartos"]
    )
    suspicious_mismatch = int((suspicious_union != capacity["capacidade_positiva_suspeita"]).sum())
    add_check(rows, "Flag de capacidade suspeita reconcilia", suspicious_mismatch, 0, suspicious_mismatch == 0, True, "União exata das três regras pré-definidas.")
    invalid_capacity_in_sensitivity = int(
        metric_long.loc[
            (metric_long["metrica"] == "preco_por_hospede")
            & (
                metric_long["tratamento_capacidade"]
                == "sem capacidades positivas suspeitas"
            ),
            ID,
        ].isin(set(capacity.loc[capacity["capacidade_positiva_suspeita"], ID])).sum()
    )
    add_check(rows, "Sensibilidade remove flags de capacidade", invalid_capacity_in_sensitivity, 0, invalid_capacity_in_sensitivity == 0, True, "Nenhuma flag positiva permanece na sensibilidade.")
    bad_interval = int(
        (
            contrasts["bootstrap_host_ic95_inferior_rs"]
            > contrasts["bootstrap_host_ic95_superior_rs"]
        ).sum()
    )
    add_check(rows, "Intervalos agrupados ordenados", bad_interval, 0, bad_interval == 0, True, "Limite inferior não pode superar o superior.")
    cycle2_calendar = segments.loc[
        (segments["metodo"] == "snapshot_calendar_adjusted")
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["metrica"] == "preco_total")
        & (segments["tratamento_capacidade"] == "não aplicável"),
        ["segment_key", "preco_mediano"],
    ]
    calendar_reconciliation = cycle1_calendar[
        ["segment_key", "preco_mediano_ajustado_calendario"]
    ].merge(
        cycle2_calendar,
        on="segment_key",
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    calendar_orphans = int(calendar_reconciliation["_merge"].ne("both").sum())
    add_check(
        rows,
        "Universo do calendário reconcilia com ciclo 1",
        calendar_orphans,
        0,
        calendar_orphans == 0,
        True,
        "Mesmos segmentos residenciais no artefato dos dois ciclos.",
    )
    calendar_max_difference = float(
        (
            calendar_reconciliation["preco_mediano"]
            - calendar_reconciliation["preco_mediano_ajustado_calendario"]
        ).abs().max()
    )
    add_check(
        rows,
        "Medianas ajustadas reconciliam com ciclo 1",
        calendar_max_difference,
        0.0,
        bool(calendar_max_difference <= 1e-10),
        True,
        "Tolerância numérica absoluta de 1e-10 por segmento.",
    )
    predefined_pairs = contrasts.loc[
        contrasts["escopo_comparacao"] == "principal pré-definida",
        ["segment_key_a", "segment_key_b"],
    ].drop_duplicates()
    add_check(rows, "Pares pré-definidos da tese presentes", len(predefined_pairs), 3, len(predefined_pairs) == 3, True, "Um contraste de localização e dois de compacto com suporte mínimo.")
    uses_vivareal = any("VivaReal" in str(path) for path in [DETAILS_FILE, MESH_FILE, PRICE_FILE, CYCLE1_LISTINGS])
    add_check(rows, "VivaReal ausente do ciclo 2", uses_vivareal, False, not uses_vivareal, True, "Escopo operacional do Airbnb.")
    raw_hashes_after = {name: sha256(ROOT / "data" / name) for name in raw_hashes_before}
    add_check(rows, "Hashes dos CSVs brutos preservados", raw_hashes_after == raw_hashes_before, True, raw_hashes_after == raw_hashes_before, True, "Nenhum CSV original foi alterado.")
    checks = pd.DataFrame(rows)
    if bool(((checks["status"] != "OK") & checks["critical"]).any()):
        failures = checks.loc[(checks["status"] != "OK") & checks["critical"], "check"].tolist()
        raise RuntimeError(f"Checks críticos falharam: {failures}")
    return checks


def escape_svg(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_dot_chart(path: Path, title: str, rows: pd.DataFrame, value: str, low: str, high: str, label: str) -> None:
    rows = rows.head(12).copy()
    width, left, right, top, row_h = 1100, 410, 70, 85, 42
    height = top + row_h * len(rows) + 60
    xmin = float(min(0, rows[low].min()))
    xmax = float(rows[high].max())
    span = xmax - xmin or 1.0
    x = lambda v: left + (float(v) - xmin) / span * (width - left - right)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', f'<text x="30" y="38" font-family="Arial" font-size="22" font-weight="bold">{escape_svg(title)}</text>']
    if xmin <= 0 <= xmax:
        parts.append(
            f'<line x1="{x(0):.1f}" y1="{top-22}" x2="{x(0):.1f}" y2="{height-40}" '
            'stroke="#9aa0a6" stroke-width="1.5" stroke-dasharray="5,5"/>'
        )
    for i, row in rows.reset_index(drop=True).iterrows():
        y = top + i * row_h
        parts.append(f'<text x="30" y="{y+5}" font-family="Arial" font-size="14">{escape_svg(row[label])}</text>')
        parts.append(f'<line x1="{x(row[low]):.1f}" y1="{y}" x2="{x(row[high]):.1f}" y2="{y}" stroke="#7a8a99" stroke-width="5"/>')
        parts.append(f'<circle cx="{x(row[value]):.1f}" cy="{y}" r="6" fill="#006d77"/>')
        parts.append(f'<text x="{x(row[value])+10:.1f}" y="{y+5}" font-family="Arial" font-size="13">R$ {row[value]:.0f}</text>')
    parts.append(f'<line x1="{left}" y1="{height-40}" x2="{width-right}" y2="{height-40}" stroke="#333"/>')
    parts.append(f'<text x="{left}" y="{height-15}" font-family="Arial" font-size="12">R$ {xmin:.0f}</text>')
    parts.append(f'<text x="{width-right-60}" y="{height-15}" font-family="Arial" font-size="12">R$ {xmax:.0f}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_forest_chart(path: Path, thesis: pd.DataFrame) -> None:
    rows = thesis.copy()
    rows["rotulo"] = rows["segmento_b"] + " · " + rows["metrica_label"]
    write_dot_chart(
        path,
        "Centro · apartamento · 1 quarto: diferença versus comparadores",
        rows,
        "diferenca_rs",
        "bootstrap_host_ic95_inferior_rs",
        "bootstrap_host_ic95_superior_rs",
        "rotulo",
    )


def fmt_money(value: Any, decimals: int = 0) -> str:
    if pd.isna(value):
        return "n/d"
    return f"R$ {float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value: Any) -> str:
    if pd.isna(value):
        return "n/d"
    return f"{100 * float(value):.1f}%".replace(".", ",")


def markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]], limit: int | None = None) -> str:
    data = frame.head(limit) if limit else frame
    headers = [label for _, label in columns]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in data.iterrows():
        values = []
        for column, _ in columns:
            value = row[column]
            if column.endswith("_pct") or "pct_" in column or column.endswith("_pct_sobre_b"):
                values.append(fmt_pct(value))
            elif column.startswith("preco") or column.startswith("mediana") or column.startswith("p25") or column.startswith("p75") or column.startswith("diferenca") or "ic95" in column:
                values.append(fmt_money(value, 1))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def robust_direction(robustness: pd.DataFrame, segment_b: str, metric: str) -> tuple[bool, list[float]]:
    rows = robustness.loc[
        (robustness["segment_key_b"] == segment_b)
        & (robustness["metrica"] == metric)
        & robustness["diferenca_rs"].notna()
    ]
    values = rows["diferenca_rs"].astype(float).tolist()
    host_range = robustness.loc[
        (robustness["segment_key_b"] == segment_b)
        & (robustness["metrica"] == metric)
        & (robustness["cenario_sensibilidade"] == "sem maior anfitrião (faixa)")
    ]
    if not host_range.empty:
        values += [float(host_range.iloc[0]["diferenca_min_rs"]), float(host_range.iloc[0]["diferenca_max_rs"])]
    nonzero = [v for v in values if not np.isclose(v, 0)]
    stable = bool(nonzero) and (all(v > 0 for v in nonzero) or all(v < 0 for v in nonzero))
    return stable, values


def build_report(
    segments: pd.DataFrame,
    contrasts: pd.DataFrame,
    robustness: pd.DataFrame,
    location: pd.DataFrame,
    capacity_audit: pd.DataFrame,
    thresholds: dict[str, float],
    checks: pd.DataFrame,
) -> tuple[str, dict[str, Any]]:
    main_segments = segments.loc[
        (segments["metodo"] == MAIN_METHOD)
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["tratamento_capacidade"] == "não aplicável")
        & (segments["metrica"] == "preco_total")
        & (segments["n_listings"] >= PRIMARY_AIRBNB_MIN)
    ].sort_values("preco_mediano", ascending=False)
    main_guest = segments.loc[
        (segments["metodo"] == MAIN_METHOD)
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["metrica"] == "preco_por_hospede")
        & (segments["tratamento_capacidade"] == "todas as capacidades positivas")
        & (segments["n_listings"] >= PRIMARY_AIRBNB_MIN)
    ].sort_values("preco_mediano", ascending=False)
    main_room = segments.loc[
        (segments["metodo"] == MAIN_METHOD)
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["metrica"] == "preco_por_quarto")
        & (segments["tratamento_capacidade"] == "não aplicável")
        & (segments["n_listings"] >= PRIMARY_AIRBNB_MIN)
    ].sort_values("preco_mediano", ascending=False)
    top = main_segments.iloc[0]
    controlled_candidates = contrasts.loc[
        (contrasts["metrica"] == "preco_total")
        & (
            contrasts["segment_key_a"].eq(top["segment_key"])
            | contrasts["segment_key_b"].eq(top["segment_key"])
        )
        & contrasts["suporte_comparacao"].eq("principal")
    ].copy()
    require(
        not controlled_candidates.empty,
        "O segmento de maior preço não possui comparador controlado principal.",
    )
    segment_medians = main_segments.set_index("segment_key")["preco_mediano"]
    controlled_candidates["comparison_key"] = np.where(
        controlled_candidates["segment_key_a"].eq(top["segment_key"]),
        controlled_candidates["segment_key_b"],
        controlled_candidates["segment_key_a"],
    )
    controlled_candidates["comparison_median"] = controlled_candidates[
        "comparison_key"
    ].map(segment_medians)
    top_contrast = controlled_candidates.sort_values(
        "comparison_median", ascending=False
    ).iloc[0]
    comparison_key = top_contrast["comparison_key"]
    comparison = main_segments.loc[main_segments["segment_key"] == comparison_key].iloc[0]
    if top_contrast["segment_key_a"] != top["segment_key"]:
        top_delta = -float(top_contrast["diferenca_rs"])
        top_pct = top_delta / float(comparison["preco_mediano"])
        top_ci = (-float(top_contrast["bootstrap_host_ic95_superior_rs"]), -float(top_contrast["bootstrap_host_ic95_inferior_rs"]))
    else:
        top_delta = float(top_contrast["diferenca_rs"])
        top_pct = float(top_contrast["diferenca_pct_sobre_b"])
        top_ci = (float(top_contrast["bootstrap_host_ic95_inferior_rs"]), float(top_contrast["bootstrap_host_ic95_superior_rs"]))

    thesis = contrasts.loc[contrasts["escopo_comparacao"] == "principal pré-definida"].copy()
    location_thesis = thesis.loc[thesis["familia_comparacao"] == "tese: vantagem de localização"]
    compact_thesis = thesis.loc[thesis["familia_comparacao"] == "tese: vantagem do compacto"]

    location_main = location_thesis.loc[
        (location_thesis["metrica"] == "preco_total")
        & (location_thesis["suporte_comparacao"] == "principal")
    ]
    location_favorable = bool(
        len(location_main)
        and (
            (location_main["diferenca_rs"] > 0)
            & (location_main["evidencia_estatistica"] == "diferença estatisticamente sustentada")
        ).all()
    )
    location_contrary = bool(
        len(location_main)
        and (
            (location_main["diferenca_rs"] < 0)
            & (location_main["evidencia_estatistica"] == "diferença estatisticamente sustentada")
        ).all()
    )
    location_status = "favorável" if location_favorable else "contrária" if location_contrary else "inconclusiva"

    compact_comparators = compact_thesis.loc[compact_thesis["suporte_comparacao"] == "principal", "segment_key_b"].unique()
    comparator_status: dict[str, str] = {}
    for comparator in compact_comparators:
        relevant = compact_thesis.loc[
            (compact_thesis["segment_key_b"] == comparator)
            & compact_thesis["metrica"].isin(["preco_por_hospede", "preco_por_quarto"])
        ]
        favorable = []
        contrary = []
        for _, row in relevant.iterrows():
            stable, _ = robust_direction(robustness, comparator, row["metrica"])
            supported = row["evidencia_estatistica"] == "diferença estatisticamente sustentada"
            favorable.append(bool(supported and row["diferenca_rs"] > 0 and stable))
            contrary.append(bool(supported and row["diferenca_rs"] < 0 and stable))
        if any(favorable) and not any(contrary):
            comparator_status[comparator] = "favorável"
        elif any(contrary) and not any(favorable):
            comparator_status[comparator] = "contrária"
        else:
            comparator_status[comparator] = "inconclusiva"
    compact_favorable = bool(comparator_status) and all(v == "favorável" for v in comparator_status.values())
    compact_contrary = bool(comparator_status) and all(v == "contrária" for v in comparator_status.values())
    compact_status = "favorável" if compact_favorable else "contrária" if compact_contrary else "inconclusiva"

    if location_favorable and compact_favorable:
        thesis_status = "sustentada operacionalmente"
    elif location_favorable ^ compact_favorable:
        thesis_status = "parcialmente sustentada"
    elif location_contrary and compact_contrary:
        thesis_status = "não sustentada"
    else:
        thesis_status = "inconclusiva"
    location_status_display = {
        "favorável": "favorável",
        "contrária": "contrário",
        "inconclusiva": "inconclusivo",
    }[location_status]

    general_location_claims = []
    if not location.empty:
        for pair, group in location.groupby("par_bairros"):
            if group["perfil"].nunique() < 2:
                continue
            signs = np.sign(group["diferenca_a_menos_b_rs"])
            supported = group["evidencia_estatistica"].eq("diferença estatisticamente sustentada")
            if (signs > 0).all() and supported.all():
                general_location_claims.append(f"{group.iloc[0]['bairro_a']} supera {group.iloc[0]['bairro_b']} em {len(group)} perfis equivalentes")
            elif (signs < 0).all() and supported.all():
                general_location_claims.append(f"{group.iloc[0]['bairro_b']} supera {group.iloc[0]['bairro_a']} em {len(group)} perfis equivalentes")

    supported_main = contrasts.loc[
        (contrasts["suporte_comparacao"] == "principal")
        & (
            contrasts["evidencia_estatistica"]
            == "diferença estatisticamente sustentada"
        )
    ].sort_values(["familia_comparacao", "segmento_a", "segmento_b", "metrica"])

    robustness_summary_rows: list[dict[str, Any]] = []
    for (family, segment_b, metric, metric_label), group in robustness.groupby(
        ["familia_comparacao", "segmento_b", "metrica", "metrica_label"]
    ):
        values = group["diferenca_rs"].dropna().astype(float).tolist()
        host_ranges = group.loc[
            group["cenario_sensibilidade"] == "sem maior anfitrião (faixa)"
        ]
        for _, host_row in host_ranges.iterrows():
            if pd.notna(host_row.get("diferenca_min_rs")):
                values.append(float(host_row["diferenca_min_rs"]))
            if pd.notna(host_row.get("diferenca_max_rs")):
                values.append(float(host_row["diferenca_max_rs"]))
        headline = group.loc[group["cenario_sensibilidade"] == "headline"]
        if not values or headline.empty:
            continue
        sign_preserved = all(v > 0 for v in values) or all(v < 0 for v in values)
        robustness_summary_rows.append(
            {
                "familia_comparacao": family,
                "segmento_b": segment_b,
                "metrica": metric,
                "metrica_label": metric_label,
                "diferenca_headline_rs": float(headline.iloc[0]["diferenca_rs"]),
                "diferenca_min_sensibilidades_rs": min(values),
                "diferenca_max_sensibilidades_rs": max(values),
                "sinal_preservado": "sim" if sign_preserved else "não",
                "n_leituras": len(values),
            }
        )
    robustness_summary = pd.DataFrame(robustness_summary_rows)

    location_total = location_thesis.loc[
        location_thesis["metrica"] == "preco_total"
    ]
    location_robust = robustness.loc[
        (robustness["familia_comparacao"] == "tese: vantagem de localização")
        & (robustness["metrica"] == "preco_total")
    ]
    location_calendar = location_robust.loc[
        location_robust["cenario_sensibilidade"] == "calendário ajustado"
    ]
    calendar_sensitivity = robustness.loc[
        robustness["cenario_sensibilidade"] == "calendário ajustado"
    ].sort_values(["segmento_b", "metrica"])

    zero_main = segments.loc[
        (segments["metodo"] == MAIN_METHOD)
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["metrica"] == "preco_total")
        & (segments["tratamento_capacidade"] == "não aplicável")
        & segments["quartos"].eq(0)
    ].sort_values("n_listings", ascending=False)

    thesis_table = thesis.sort_values(["familia_comparacao", "segmento_b", "metrica"])
    lines = [
        "# Ciclo 2 — perfil, localização e tese operacional",
        "",
        "## Conclusão operacional",
        "",
        f"**A tese dos apartamentos de um quarto no Centro foi classificada como {thesis_status}.**",
        "",
        f"O componente de localização ficou **{location_status_display}**. O componente de compacto ficou **{compact_status} apenas em densidade de preço anunciado por capacidade declarada**. Esta é uma conclusão somente sobre preços anunciados; não incorpora compra, demanda, ocupação, receita realizada ou retorno.",
        "",
        "## Perfil com maior preço anunciado total",
        "",
        f"Entre os segmentos principais cobertos em 20/01, **{top['segmento_imoveis']}** tem a maior mediana pontual ({fmt_money(top['preco_mediano'])}; n={int(top['n_listings'])} listings e {int(top['n_hosts'])} anfitriões). O comparador controlado principal mais próximo disponível é **{comparison['segmento_imoveis']}**: diferença de {fmt_money(top_delta)} ({fmt_pct(top_pct)}), com intervalo agrupado por anfitrião de {fmt_money(top_ci[0])} a {fmt_money(top_ci[1])}. Evidência: **{top_contrast['evidencia_estatistica']}**. O segundo colocado geral não é usado como contraste causalmente interpretável quando perfil e bairro mudam juntos.",
        "",
        markdown_table(
            main_segments,
            [
                ("segmento_imoveis", "Segmento de imóveis"),
                ("n_listings", "Listings"),
                ("n_hosts", "Hosts"),
                ("preco_mediano", "Mediana"),
                ("preco_p25", "p25"),
                ("preco_p75", "p75"),
            ],
        ),
        "",
        "![Preço anunciado total nos segmentos principais](figures/airbnb_profile_total_price.svg)",
        "",
        "## Perfil em relação à capacidade declarada",
        "",
        f"**{main_guest.iloc[0]['segmento_imoveis']}** apresenta a maior mediana de preço anunciado por hóspede comportado entre os segmentos principais ({fmt_money(main_guest.iloc[0]['preco_mediano'], 1)}). O mesmo segmento também lidera o preço anunciado por quarto ({fmt_money(main_room.iloc[0]['preco_mediano'], 1)}). Como possui um quarto, seu preço por quarto é numericamente igual ao preço total; a informação analítica vem da comparação dessa razão com imóveis de mais quartos. Essas divisões medem somente densidade de preço anunciado por capacidade declarada: não demonstram demanda, ocupação, receita, retorno nem eficiência por área ou capital. A divisão por quarto pode favorecer mecanicamente imóveis menores porque reduz o denominador.",
        "",
        markdown_table(
            main_guest,
            [
                ("segmento_imoveis", "Segmento de imóveis"),
                ("n_listings", "Listings"),
                ("n_hosts", "Hosts"),
                ("preco_mediano", "Mediana por hóspede"),
                ("preco_p25", "p25"),
                ("preco_p75", "p75"),
            ],
        ),
        "",
        "![Preço anunciado por hóspede comportado](figures/airbnb_price_per_guest.svg)",
        "",
        "## Localização com perfil controlado",
        "",
    ]
    if general_location_claims:
        lines.append("Foi possível sustentar a seguinte leitura geral: " + "; ".join(general_location_claims) + ".")
    else:
        lines.append("**Não há base para declarar um bairro vencedor em termos gerais.** Nenhum par de bairros satisfez simultaneamente dois perfis equivalentes principais, direção coerente e diferenças sustentadas. A resposta de localização permanece condicionada ao perfil.")
    if not location_total.empty:
        loc = location_total.iloc[0]
        calendar_text = ""
        if not location_calendar.empty:
            cal = location_calendar.iloc[0]
            calendar_text = f"; no ajuste de calendário, a diferença muda para {fmt_money(cal['diferenca_rs'])} ({fmt_pct(cal['diferenca_pct_sobre_b'])})"
        lines.append(
            f"No contraste pré-definido de apartamentos de um quarto, Centro tem {fmt_money(loc['mediana_a'])} contra {fmt_money(loc['mediana_b'])} em Meia Praia: {fmt_money(loc['diferenca_rs'])} ({fmt_pct(loc['diferenca_pct_sobre_b'])}), IC95 agrupado de {fmt_money(loc['bootstrap_host_ic95_inferior_rs'])} a {fmt_money(loc['bootstrap_host_ic95_superior_rs'])}{calendar_text}. O comparador tem apenas {int(loc['n_listings_b'])} listings, portanto a leitura é exploratória e inconclusiva."
        )
    lines += [
        "",
        markdown_table(
            location.sort_values(["par_bairros", "perfil"]) if not location.empty else location,
            [
                ("bairro_a", "Bairro A"),
                ("bairro_b", "Bairro B"),
                ("perfil", "Perfil equivalente"),
                ("n_listings_a", "n A"),
                ("n_listings_b", "n B"),
                ("diferenca_a_menos_b_rs", "A − B"),
                ("diferenca_a_menos_b_pct_sobre_b", "% sobre B"),
                ("evidencia_estatistica", "Evidência"),
            ],
        ) if not location.empty else "Não houve pares de bairros com dois lados principais.",
        "",
        "## Contrastes pré-definidos da tese",
        "",
        markdown_table(
            thesis_table,
            [
                ("familia_comparacao", "Componente"),
                ("segmento_b", "Comparador de Centro/1 quarto"),
                ("metrica_label", "Métrica"),
                ("n_listings_a", "n alvo"),
                ("n_hosts_a", "hosts alvo"),
                ("n_listings_b", "n comp."),
                ("n_hosts_b", "hosts comp."),
                ("mediana_a", "Mediana alvo"),
                ("mediana_b", "Mediana comp."),
                ("diferenca_rs", "Diferença"),
                ("diferenca_pct_sobre_b", "% sobre comp."),
                ("bootstrap_host_ic95_inferior_rs", "IC95 inf."),
                ("bootstrap_host_ic95_superior_rs", "IC95 sup."),
                ("evidencia_estatistica", "Evidência"),
                ("suporte_comparacao", "Suporte"),
            ],
        ),
        "",
        "![Contrastes pré-definidos da tese](figures/airbnb_compact_thesis_contrasts.svg)",
        "",
        "O componente compacto é favorável **apenas em densidade de preço anunciado por capacidade declarada**: Centro/1 quarto supera Centro/2 e Centro/3 quartos tanto por hóspede comportado quanto por quarto, com intervalos agrupados acima de zero e sinal preservado nas sensibilidades. Em preço total ocorre o conflito esperado: Centro/1 quarto fica R$ 150 abaixo de Centro/2 quartos, com evidência inconclusiva, e R$ 214 abaixo de Centro/3 quartos, com diferença sustentada. A tese não exigia preço total superior, e essas razões não demonstram desempenho econômico ou demanda.",
        "",
        "O preço total e as métricas por capacidade são leituras diferentes. Quando apontam em direções distintas, o resultado acima preserva o conflito: o preço total mede o valor anunciado da unidade; as razões medem esse preço em relação à capacidade declarada.",
        "",
        "## Comparações com suporte principal e diferença sustentada",
        "",
        f"Das {int((contrasts['suporte_comparacao'] == 'principal').sum())} comparações com pelo menos 30 listings nos dois lados, {len(supported_main)} têm intervalo agrupado que exclui zero. Fora dos contrastes pré-definidos da tese, essas leituras permanecem exploratórias quanto à formulação de conclusões gerais; as demais diferenças são inconclusivas.",
        "",
        markdown_table(
            supported_main,
            [
                ("segmento_a", "Segmento A"),
                ("segmento_b", "Segmento B"),
                ("metrica_label", "Métrica"),
                ("diferenca_rs", "A − B"),
                ("diferenca_pct_sobre_b", "% sobre B"),
                ("bootstrap_host_ic95_inferior_rs", "IC95 inf."),
                ("bootstrap_host_ic95_superior_rs", "IC95 sup."),
            ],
        ),
        "",
        "## Qualidade da capacidade",
        "",
        f"As flags foram definidas antes do cruzamento com preços. A cerca externa global de referência foi {thresholds['cerca_externa_global']:.1f} hóspedes; perfis com pelo menos 30 observações usam sua própria cerca `p75 + 3×IQR`.",
        "",
        markdown_table(capacity_audit, [("regra", "Regra"), ("n_listings", "Listings"), ("tratamento", "Tratamento")]),
        "",
        "Capacidades positivas suspeitas permanecem no headline e são removidas somente na sensibilidade previamente definida. Listings inválidos para a razão continuam nas comparações de preço total.",
        "",
        (
            f"Imóveis de zero quarto foram mantidos separados. O maior segmento observado foi **{zero_main.iloc[0]['segmento_imoveis']}**, com apenas {int(zero_main.iloc[0]['n_listings'])} listings; portanto não houve suporte sequer exploratório para usá-lo contra Centro/1 quarto. Nenhum imóvel de zero quarto foi chamado automaticamente de studio."
            if not zero_main.empty
            else "Não houve segmento de zero quarto com preço na captura principal; nenhum foi chamado automaticamente de studio."
        ),
        "",
        "## Robustez dos contrastes da tese",
        "",
        markdown_table(
            robustness_summary.sort_values(["segmento_b", "metrica"]),
            [
                ("segmento_b", "Comparador"),
                ("metrica_label", "Métrica"),
                ("diferenca_headline_rs", "Headline"),
                ("diferenca_min_sensibilidades_rs", "Menor nas sensibilidades"),
                ("diferenca_max_sensibilidades_rs", "Maior nas sensibilidades"),
                ("sinal_preservado", "Sinal preservado"),
                ("n_leituras", "Leituras"),
            ],
        ),
        "",
        "A tabela resume captura de 20/01, mediana entre capturas, método mais recente, duas sensibilidades de preços suspeitos, ajuste de calendário, peso igual por anfitrião, retirada do maior anfitrião e, para preço por hóspede, retirada pré-definida de capacidades positivas suspeitas. O CSV de robustez preserva cada leitura separadamente.",
        "",
        "### Ajuste de calendário reconciliado com o Ciclo 1",
        "",
        "A referência diária e a escala são calculadas depois de limitar o universo aos imóveis residenciais, reutilizando a função do Ciclo 1. As medianas ajustadas coincidem nos 45 segmentos residenciais; a diferença máxima fica abaixo da tolerância numérica de `1e-10`.",
        "",
        markdown_table(
            calendar_sensitivity,
            [
                ("segmento_b", "Comparador"),
                ("metrica_label", "Métrica"),
                ("n_listings_a", "n alvo"),
                ("n_listings_b", "n comp."),
                ("mediana_a", "Mediana ajustada alvo"),
                ("mediana_b", "Mediana ajustada comp."),
                ("diferenca_rs", "Diferença"),
                ("diferenca_pct_sobre_b", "% sobre comp."),
            ],
        ),
        "",
        "## Limitações que permanecem",
        "",
        "- A amostra com preço cobre somente parte dos listings e é seletiva por bairro e perfil.",
        "- A captura principal cobre datas de estadia entre janeiro e abril; o ajuste de calendário é sensibilidade, não correção completa de sazonalidade.",
        "- Preço anunciado não é receita realizada e a documentação não informa moeda ou inclusão de taxas.",
        "- `listing_type` representa tipologia do imóvel. Não existe classificação confiável de imóvel inteiro, quarto privativo ou compartilhado; a parte 'tipo de anúncio' da pergunta oficial permanece sem resposta segura.",
        "- Centro/1 quarto e Centro/2 quartos têm concentração relevante por anfitrião; o bootstrap agrupado reduz a independência presumida, mas não corrige viés de seleção.",
        "- Preço por hóspede e por quarto não demonstra demanda, ocupação, receita, retorno ou eficiência por área ou capital. A divisão por quarto pode favorecer mecanicamente imóveis menores.",
        "- Diferenças sustentadas estatisticamente não foram classificadas como economicamente relevantes.",
        "",
        "## Checks e escopo",
        "",
        f"{int((checks['status'] == 'OK').sum())} de {len(checks)} checks foram aprovados. O ciclo não usou VivaReal, não estimou ocupação, receita ou retorno e não produziu recomendação de compra.",
        "",
        "## O que confrontar no próximo ciclo",
        "",
        "Os segmentos com maior preço total e os eventuais ganhos por hóspede ou quarto deverão ser confrontados com preço pedido de aquisição, tamanho da amostra do VivaReal, custos observáveis e cenários de ocupação/sazonalidade. Nenhuma vantagem operacional implica, sozinha, melhor investimento.",
    ]
    summary = {
        "thesis_operational_classification": thesis_status,
        "location_component": location_status,
        "compact_component": (
            "favorável apenas em densidade de preço anunciado por capacidade declarada"
            if compact_status == "favorável"
            else compact_status
        ),
        "compact_component_evidence_status": compact_status,
        "compact_comparator_status": comparator_status,
        "top_total_price_segment": top["segmento_imoveis"],
        "top_total_price_median": float(top["preco_mediano"]),
        "top_controlled_comparator": comparison["segmento_imoveis"],
        "top_vs_controlled_comparator_difference": top_delta,
        "top_vs_controlled_comparator_difference_pct": top_pct,
        "general_location_claims": general_location_claims,
    }
    return "\n".join(lines) + "\n", summary


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    raw_hashes = {
        DETAILS_FILE.name: sha256(DETAILS_FILE),
        MESH_FILE.name: sha256(MESH_FILE),
        PRICE_FILE.name: sha256(PRICE_FILE),
    }
    details, mesh, price = read_inputs()
    listing_base = build_listing_base(details, mesh, price)
    capacity, capacity_audit, thresholds = audit_capacity(details, listing_base)
    cycle1 = pd.read_csv(CYCLE1_LISTINGS, dtype={ID: "string", "owner_id": "string"}, low_memory=False)
    cycle1_calendar = pd.read_csv(CYCLE1_CALENDAR)
    calendar_listing, calendar_reference = build_calendar_adjusted_listings(
        listing_base,
        price,
        cycle1,
    )
    listing = build_listing_metrics(cycle1, capacity, calendar_listing, listing_base)
    metric_long = to_metric_long(listing)
    segments = build_segment_summary(metric_long)
    main_total = segments.loc[
        (segments["metodo"] == MAIN_METHOD)
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["metrica"] == "preco_total")
        & (segments["tratamento_capacidade"] == "não aplicável")
    ].copy()
    definitions = build_contrast_definitions(main_total)
    contrasts = build_main_contrasts(metric_long, definitions)
    robustness = build_robustness(metric_long, segments, definitions)
    location = build_location_matrix(main_total, contrasts)
    checks = build_checks(
        details,
        listing,
        metric_long,
        segments,
        contrasts,
        capacity,
        cycle1_calendar,
        raw_hashes,
    )

    transformations = pd.DataFrame(
        [
            {
                "etapa": "Auditoria prévia de capacidade",
                "linhas_entrada": len(details),
                "linhas_saida": len(capacity),
                "registros_afetados": int(capacity["capacidade_positiva_suspeita"].sum()),
                "funcao": "audit_capacity",
                "observacao": "Flags calculadas antes do cruzamento com preços; suspeitos positivos preservados.",
            },
            {
                "etapa": "Métricas por listing",
                "linhas_entrada": len(cycle1),
                "linhas_saida": len(listing),
                "registros_afetados": len(listing),
                "funcao": "build_listing_metrics",
                "observacao": "Uma linha por listing, método e tratamento; calendário ajustado reutiliza exatamente a lógica residencial do ciclo 1.",
            },
            {
                "etapa": "Reconciliação do calendário com ciclo 1",
                "linhas_entrada": len(cycle1_calendar),
                "linhas_saida": len(cycle1_calendar),
                "registros_afetados": len(cycle1_calendar),
                "funcao": "build_checks",
                "observacao": "Compara universo e mediana ajustada de cada segmento com reports/generated/airbnb_price_calendar.csv.",
            },
            {
                "etapa": "Resumo por segmento",
                "linhas_entrada": len(metric_long),
                "linhas_saida": len(segments),
                "registros_afetados": len(metric_long),
                "funcao": "build_segment_summary",
                "observacao": "Mediana e p25/p75 calculados somente depois das métricas por listing.",
            },
            {
                "etapa": "Contrastes controlados",
                "linhas_entrada": len(definitions),
                "linhas_saida": len(contrasts),
                "registros_afetados": len(contrasts),
                "funcao": "build_main_contrasts",
                "observacao": "Bootstrap agrupado por owner_id; tese pré-definida separada das comparações exploratórias.",
            },
        ]
    )

    report, report_summary = build_report(
        segments, contrasts, robustness, location, capacity_audit, thresholds, checks
    )
    summary = {
        "scope": {
            "uses_vivareal": False,
            "estimates_occupancy": False,
            "estimates_revenue": False,
            "estimates_return": False,
            "main_capture": MAIN_CAPTURE.date().isoformat(),
        },
        "source_hashes": raw_hashes,
        "capacity_thresholds": thresholds,
        "calendar_reference_price": calendar_reference,
        "calendar_reconciliation": {
            "segments": int(len(cycle1_calendar)),
            "max_absolute_difference": float(
                checks.loc[
                    checks["check"]
                    == "Medianas ajustadas reconciliam com ciclo 1",
                    "actual",
                ].iloc[0]
            ),
            "tolerance": 1e-10,
        },
        "counts": {
            "listing_metric_rows": len(listing),
            "segment_rows": len(segments),
            "contrast_definitions": len(definitions),
            "contrast_rows": len(contrasts),
            "robustness_rows": len(robustness),
        },
        "results": report_summary,
        "checks": {
            "all_passed": bool((checks["status"] == "OK").all()),
            "passed": int((checks["status"] == "OK").sum()),
            "total": len(checks),
        },
    }

    listing.to_csv(LISTING_OUTPUT, index=False)
    segments.to_csv(SEGMENT_OUTPUT, index=False)
    contrasts.to_csv(CONTRAST_OUTPUT, index=False)
    robustness.to_csv(ROBUSTNESS_OUTPUT, index=False)
    location.to_csv(LOCATION_OUTPUT, index=False)
    capacity_audit.to_csv(CAPACITY_OUTPUT, index=False)
    checks.to_csv(CHECKS_OUTPUT, index=False)
    transformations.to_csv(TRANSFORMATIONS_OUTPUT, index=False)
    SUMMARY_OUTPUT.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    REPORT_OUTPUT.write_text(report, encoding="utf-8")

    main_segments = segments.loc[
        (segments["metodo"] == MAIN_METHOD)
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["metrica"] == "preco_total")
        & (segments["tratamento_capacidade"] == "não aplicável")
        & (segments["n_listings"] >= PRIMARY_AIRBNB_MIN)
    ].sort_values("preco_mediano", ascending=False)
    write_dot_chart(
        FIGURES_DIR / "airbnb_profile_total_price.svg",
        "Preço anunciado total nos segmentos principais",
        main_segments,
        "preco_mediano",
        "preco_p25",
        "preco_p75",
        "segmento_imoveis",
    )
    thesis = contrasts.loc[contrasts["escopo_comparacao"] == "principal pré-definida"]
    write_forest_chart(FIGURES_DIR / "airbnb_compact_thesis_contrasts.svg", thesis)
    center = main_segments.loc[main_segments["bairro"] == "Centro"].sort_values("quartos")
    if len(center):
        write_dot_chart(
            FIGURES_DIR / "airbnb_centro_profiles.svg",
            "Apartamentos no Centro: preço anunciado total por quartos",
            center,
            "preco_mediano",
            "preco_p25",
            "preco_p75",
            "segmento_imoveis",
        )
    efficiency = segments.loc[
        (segments["metodo"] == MAIN_METHOD)
        & (segments["tratamento_outlier"] == ORIGINAL)
        & (segments["metrica"] == "preco_por_hospede")
        & (segments["tratamento_capacidade"] == "todas as capacidades positivas")
        & (segments["n_listings"] >= PRIMARY_AIRBNB_MIN)
    ].sort_values("preco_mediano", ascending=False)
    write_dot_chart(
        FIGURES_DIR / "airbnb_price_per_guest.svg",
        "Preço anunciado por hóspede comportado",
        efficiency,
        "preco_mediano",
        "preco_p25",
        "preco_p75",
        "segmento_imoveis",
    )
    print(
        f"Ciclo 2 concluído: {len(contrasts)} contrastes; "
        f"tese={report_summary['thesis_operational_classification']}; "
        f"checks={'OK' if summary['checks']['all_passed'] else 'FALHA'}"
    )


if __name__ == "__main__":
    main()
