#!/usr/bin/env python3
"""Auditoria reproduzível dos CSVs do desafio de Itapema.

O script é deliberadamente descritivo: não calcula recomendação de investimento.
Ele preserva os arquivos de entrada e grava resultados em reports/generated/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "reports" / "generated"

FILES = {
    "details": "Details_Itapema.csv",
    "hosts": "Hosts_ids_Itapema.csv",
    "mesh": "Mesh_Ids_Data_Itapema.csv",
    "price": "Price_AV_Itapema.csv",
    "vivareal": "VivaReal_Itapema.csv",
}

ID_COLUMNS = {
    "details": ["airbnb_listing_id", "owner_id"],
    "hosts": ["owner_id"],
    "mesh": ["airbnb_listing_id"],
    "price": ["airbnb_listing_id"],
    "vivareal": ["listing_id"],
}

DATE_COLUMNS = {
    "details": ["aquisition_date"],
    "hosts": ["host_snapshot_date"],
    "mesh": ["aquisition_date"],
    "price": ["date", "aquisition_date"],
    "vivareal": ["aquisition_date"],
}

RELEVANT_CATEGORIES = {
    "details": [
        "listing_type",
        "number_of_bedrooms",
        "number_of_guests",
        "can_instant_book",
        "is_professional",
        "is_new_listing",
        "is_guest_favorite",
    ],
    "hosts": [
        "is_superhost",
        "is_verified",
        "years_host",
        "response_rate_shown",
        "response_time_shown",
    ],
    "mesh": ["suburb", "country", "state", "city"],
    "price": [],
    "vivareal": [
        "business_types",
        "listing_type",
        "property_type",
        "bedrooms",
        "suburb",
        "city",
        "state",
        "portal",
        "rental_period",
    ],
}


def json_value(value: Any) -> Any:
    """Converte escalares pandas/numpy para JSON sem perder nulos."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def read_csv(name: str) -> pd.DataFrame:
    dtype = {column: "string" for column in ID_COLUMNS[name]}
    return pd.read_csv(DATA_DIR / FILES[name], dtype=dtype, low_memory=False)


def top_values(series: pd.Series, limit: int = 15) -> list[dict[str, Any]]:
    counts = series.value_counts(dropna=False).head(limit)
    total = len(series)
    result = []
    for value, count in counts.items():
        label = None if pd.isna(value) else json_value(value)
        result.append(
            {
                "value": label,
                "count": int(count),
                "share": float(count / total) if total else None,
            }
        )
    return result


def numeric_summary(series: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {}
    quantiles = numeric.quantile([0, 0.01, 0.05, 0.5, 0.95, 0.99, 1])
    return {
        "min": json_value(quantiles.loc[0.0]),
        "p01": json_value(quantiles.loc[0.01]),
        "p05": json_value(quantiles.loc[0.05]),
        "median": json_value(quantiles.loc[0.5]),
        "p95": json_value(quantiles.loc[0.95]),
        "p99": json_value(quantiles.loc[0.99]),
        "max": json_value(quantiles.loc[1.0]),
        "negative_count": int((numeric < 0).sum()),
        "zero_count": int((numeric == 0).sum()),
    }


def column_dictionary(name: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for column in frame.columns:
        series = frame[column]
        non_null = series.dropna()
        example_values = [json_value(value) for value in non_null.head(3).tolist()]
        row = {
            "file": FILES[name],
            "column": column,
            "pandas_dtype": str(series.dtype),
            "rows": int(len(series)),
            "missing_count": int(series.isna().sum()),
            "missing_share": float(series.isna().mean()),
            "distinct_non_null": int(series.nunique(dropna=True)),
            "examples": example_values,
        }
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            row["numeric_summary"] = numeric_summary(series)
        rows.append(row)
    return rows


def date_summary(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    result = {}
    for column in DATE_COLUMNS[name]:
        parsed = pd.to_datetime(frame[column], errors="coerce")
        result[column] = {
            "min": json_value(parsed.min()),
            "max": json_value(parsed.max()),
            "invalid_or_missing_count": int(parsed.isna().sum()),
            "distinct_timestamps": int(parsed.nunique(dropna=True)),
            "distinct_dates": int(parsed.dt.date.nunique()),
        }
    return result


def identifier_summary(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    result = {}
    for column in ID_COLUMNS[name]:
        counts = frame[column].value_counts(dropna=False)
        duplicated_rows = int(counts[counts > 1].sum())
        result[column] = {
            "missing_count": int(frame[column].isna().sum()),
            "distinct_non_null": int(frame[column].nunique(dropna=True)),
            "is_unique_non_null": bool(frame[column].dropna().is_unique),
            "ids_with_multiple_rows": int((counts > 1).sum()),
            "rows_on_duplicated_ids": duplicated_rows,
            "max_rows_per_id": int(counts.max()) if not counts.empty else 0,
        }
    return result


def category_summary(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    return {
        column: top_values(frame[column])
        for column in RELEVANT_CATEGORIES[name]
        if column in frame.columns
    }


def exact_duplicate_summary(frame: pd.DataFrame) -> dict[str, int]:
    duplicated = frame.duplicated(keep=False)
    return {
        "duplicate_rows_all_columns": int(duplicated.sum()),
        "duplicate_groups_all_columns": int(
            frame.loc[duplicated].value_counts(dropna=False).shape[0]
        ),
    }


def coordinate_summary(frame: pd.DataFrame) -> dict[str, Any]:
    lat = pd.to_numeric(frame["latitude"], errors="coerce")
    lon = pd.to_numeric(frame["longitude"], errors="coerce")
    valid_world = lat.between(-90, 90) & lon.between(-180, 180)
    # Caixa ampla para detectar pontos claramente fora de Itapema, não para definir município.
    broad_itapema_box = lat.between(-27.2, -27.0) & lon.between(-48.75, -48.5)
    return {
        "latitude": numeric_summary(lat),
        "longitude": numeric_summary(lon),
        "missing_coordinate_pairs": int((lat.isna() | lon.isna()).sum()),
        "outside_world_bounds": int((~valid_world & lat.notna() & lon.notna()).sum()),
        "outside_broad_itapema_box": int(
            (~broad_itapema_box & lat.notna() & lon.notna()).sum()
        ),
        "distinct_coordinate_pairs": int(
            pd.DataFrame({"lat": lat, "lon": lon}).dropna().drop_duplicates().shape[0]
        ),
    }


def set_metrics(left: pd.Series, right: pd.Series) -> dict[str, Any]:
    left_set = set(left.dropna().astype(str))
    right_set = set(right.dropna().astype(str))
    matched = left_set & right_set
    return {
        "left_distinct": len(left_set),
        "right_distinct": len(right_set),
        "matched_distinct": len(matched),
        "left_orphan_distinct": len(left_set - right_set),
        "right_orphan_distinct": len(right_set - left_set),
        "left_coverage": len(matched) / len(left_set) if left_set else None,
        "right_coverage": len(matched) / len(right_set) if right_set else None,
    }


def validate_hosts(details: pd.DataFrame, hosts: pd.DataFrame) -> dict[str, Any]:
    metrics = set_metrics(details["owner_id"], hosts["owner_id"])
    detail_counts = details["owner_id"].value_counts()
    host_counts = hosts["owner_id"].value_counts()
    orphan_owners = set(details["owner_id"].dropna()) - set(hosts["owner_id"].dropna())
    host_attribute_columns = [
        column
        for column in hosts.columns
        if column not in {"owner_id", "host_snapshot_date"}
    ]
    host_attribute_variation = {
        column: int(
            (
                hosts.groupby("owner_id")[column].nunique(dropna=False)
                > 1
            ).sum()
        )
        for column in host_attribute_columns
    }
    raw_join_rows = int(details.merge(hosts, on="owner_id", how="left").shape[0])
    composite = details.merge(
        hosts,
        left_on=["owner_id", "aquisition_date"],
        right_on=["owner_id", "host_snapshot_date"],
        how="left",
        indicator=True,
        validate="many_to_one",
    )
    metrics.update(
        {
            "left_key": "Details.owner_id",
            "right_key": "Hosts.owner_id",
            "cardinality": "N:1" if hosts["owner_id"].dropna().is_unique else "N:N",
            "detail_rows_with_missing_key": int(details["owner_id"].isna().sum()),
            "host_rows_with_missing_key": int(hosts["owner_id"].isna().sum()),
            "detail_rows_without_match": int(details["owner_id"].isin(orphan_owners).sum()),
            "host_rows_without_detail": int(
                (~hosts["owner_id"].isin(set(details["owner_id"].dropna()))).sum()
            ),
            "owners_with_repeated_rows": int((host_counts > 1).sum()),
            "max_rows_per_owner_in_hosts": int(host_counts.max()),
            "max_listings_per_host": int(detail_counts.max()),
            "raw_owner_id_join_rows": raw_join_rows,
            "raw_owner_id_join_multiplier": float(raw_join_rows / len(details)),
            "composite_key": (
                "Details.(owner_id,aquisition_date) -> "
                "Hosts.(owner_id,host_snapshot_date)"
            ),
            "composite_cardinality": "N:1",
            "composite_matched_detail_rows": int((composite["_merge"] == "both").sum()),
            "composite_orphan_detail_rows": int((composite["_merge"] != "both").sum()),
            "owners_with_attribute_variation": host_attribute_variation,
        }
    )
    return metrics


def validate_mesh(details: pd.DataFrame, mesh: pd.DataFrame) -> dict[str, Any]:
    key = "airbnb_listing_id"
    metrics = set_metrics(details[key], mesh[key])
    mesh_counts = mesh[key].value_counts()
    location_counts = (
        mesh.assign(
            coordinate=mesh["latitude"].astype(str) + "|" + mesh["longitude"].astype(str),
            suburb_norm=mesh["suburb"].astype("string").str.strip().str.casefold(),
        )
        .groupby(key, dropna=False)
        .agg(distinct_coordinates=("coordinate", "nunique"), distinct_suburbs=("suburb_norm", "nunique"))
    )
    detail_set = set(details[key].dropna())
    mesh_set = set(mesh[key].dropna())
    metrics.update(
        {
            "left_key": "Details.airbnb_listing_id",
            "right_key": "Mesh.airbnb_listing_id",
            "cardinality": "1:1" if mesh[key].dropna().is_unique else "1:N",
            "detail_rows_without_match": int((~details[key].isin(mesh_set)).sum()),
            "mesh_rows_without_detail": int((~mesh[key].isin(detail_set)).sum()),
            "listings_with_multiple_mesh_rows": int((mesh_counts > 1).sum()),
            "max_mesh_rows_per_listing": int(mesh_counts.max()),
            "listings_with_multiple_coordinates": int(
                (location_counts["distinct_coordinates"] > 1).sum()
            ),
            "listings_with_multiple_suburbs": int(
                (location_counts["distinct_suburbs"] > 1).sum()
            ),
            "missing_suburb_rows": int(mesh["suburb"].isna().sum()),
            "coordinate_quality": coordinate_summary(mesh),
        }
    )
    return metrics


def validate_price(details: pd.DataFrame, price: pd.DataFrame) -> dict[str, Any]:
    key = "airbnb_listing_id"
    metrics = set_metrics(details[key], price[key])
    detail_set = set(details[key].dropna())
    price_set = set(price[key].dropna())
    price_counts = price[key].value_counts()
    parsed_stay = pd.to_datetime(price["date"], errors="coerce")
    parsed_capture = pd.to_datetime(price["aquisition_date"], errors="coerce")
    pair_counts = price.groupby([key, "date"], dropna=False).size()
    exact_grain_counts = price.groupby([key, "date", "aquisition_date"], dropna=False).size()
    capture_per_pair = price.groupby([key, "date"], dropna=False)["aquisition_date"].nunique()
    capture_before_or_on_stay = parsed_capture.dt.normalize() <= parsed_stay.dt.normalize()
    metrics.update(
        {
            "left_key": "Details.airbnb_listing_id",
            "right_key": "Price.airbnb_listing_id",
            "cardinality": "1:N",
            "detail_rows_without_match": int((~details[key].isin(price_set)).sum()),
            "price_rows_without_detail": int((~price[key].isin(detail_set)).sum()),
            "listings_with_price_history": int(price[key].nunique()),
            "min_rows_per_listing": int(price_counts.min()),
            "median_rows_per_listing": float(price_counts.median()),
            "max_rows_per_listing": int(price_counts.max()),
            "listing_stay_date_pairs_with_multiple_rows": int((pair_counts > 1).sum()),
            "max_rows_per_listing_stay_date": int(pair_counts.max()),
            "listing_stay_capture_keys_with_duplicates": int((exact_grain_counts > 1).sum()),
            "listing_stay_pairs_with_multiple_captures": int((capture_per_pair > 1).sum()),
            "max_captures_per_listing_stay_pair": int(capture_per_pair.max()),
            "rows_captured_after_stay_date": int((~capture_before_or_on_stay).sum()),
            "price_numeric": numeric_summary(price["price"]),
        }
    )
    return metrics


def price_semantics(price: pd.DataFrame) -> dict[str, Any]:
    stay = pd.to_datetime(price["date"], errors="coerce")
    capture = pd.to_datetime(price["aquisition_date"], errors="coerce")
    lead_days = (stay.dt.normalize() - capture.dt.normalize()).dt.days
    capture_counts = price["aquisition_date"].value_counts().sort_index()
    capture_dates = capture.dt.date.value_counts().sort_index()
    working = price.assign(capture_day=capture.dt.date)
    captures_per_listing = working.groupby("airbnb_listing_id")["aquisition_date"].nunique()
    capture_days_per_listing = working.groupby("airbnb_listing_id")["capture_day"].nunique()
    listing_capture_days = working.groupby(["airbnb_listing_id", "capture_day"]).size()
    listing_stay_capture_day = working.groupby(
        ["airbnb_listing_id", "date", "capture_day"], dropna=False
    ).size()
    stay_capture_prices = price.groupby(["airbnb_listing_id", "date"])["price"].agg(
        rows="size", distinct_prices="nunique", min_price="min", max_price="max"
    )
    return {
        "columns_present": list(price.columns),
        "availability_column_present": False,
        "fee_columns_present": [],
        "currency_column_present": False,
        "stay_date": {
            "min": json_value(stay.min()),
            "max": json_value(stay.max()),
            "distinct_dates": int(stay.dt.date.nunique()),
        },
        "capture_timestamp": {
            "min": json_value(capture.min()),
            "max": json_value(capture.max()),
            "distinct_timestamps": int(capture.nunique()),
            "distinct_dates": int(capture.dt.date.nunique()),
            "rows_by_capture_date": {
                str(key): int(value) for key, value in capture_dates.items()
            },
            "largest_timestamp_groups": {
                str(key): int(value) for key, value in capture_counts.tail(10).items()
            },
        },
        "capture_structure": {
            "listings_per_capture_day": {
                str(key): int(value)
                for key, value in working.groupby("capture_day")[
                    "airbnb_listing_id"
                ].nunique().items()
            },
            "capture_days_per_listing": {
                str(int(key)): int(value)
                for key, value in capture_days_per_listing.value_counts()
                .sort_index()
                .items()
            },
            "capture_timestamps_per_listing": numeric_summary(captures_per_listing),
            "rows_per_listing_capture_day": numeric_summary(listing_capture_days),
            "duplicate_listing_stay_capture_day_keys": int(
                (listing_stay_capture_day > 1).sum()
            ),
            "interpretation": (
                "O dia da captura funciona como snapshot; timestamps diferentes no mesmo "
                "dia particionam datas de estadia, sem duplicar listing+estadia+dia."
            ),
        },
        "lead_days": numeric_summary(lead_days),
        "listing_stay_pairs": int(stay_capture_prices.shape[0]),
        "pairs_with_multiple_rows": int((stay_capture_prices["rows"] > 1).sum()),
        "pairs_with_price_change": int((stay_capture_prices["distinct_prices"] > 1).sum()),
        "max_price_change_for_pair": json_value(
            (stay_capture_prices["max_price"] - stay_capture_prices["min_price"]).max()
        ),
    }


def price_coverage_by_cohort(
    details: pd.DataFrame, mesh: pd.DataFrame, price: pd.DataFrame
) -> dict[str, list[dict[str, Any]]]:
    population = details.merge(
        mesh[["airbnb_listing_id", "suburb"]],
        on="airbnb_listing_id",
        how="left",
        validate="one_to_one",
    )
    population["has_price"] = population["airbnb_listing_id"].isin(
        set(price["airbnb_listing_id"].dropna())
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for column in ["listing_type", "number_of_bedrooms", "suburb"]:
        grouped = (
            population.groupby(column, dropna=False)["has_price"]
            .agg(price_listings="sum", total_listings="size", coverage="mean")
            .reset_index()
        )
        result[column] = [
            {key: json_value(value) for key, value in row.items()}
            for row in grouped.to_dict(orient="records")
        ]
    return result


def vivareal_quality(frame: pd.DataFrame) -> dict[str, Any]:
    duplicate_ids = frame.loc[
        frame.duplicated("listing_id", keep=False), "listing_id"
    ].unique()
    differing_duplicate_ids = 0
    for listing_id in duplicate_ids:
        if frame.loc[frame["listing_id"] == listing_id].drop_duplicates().shape[0] > 1:
            differing_duplicate_ids += 1
    return {
        "duplicate_listing_ids": int(len(duplicate_ids)),
        "exact_duplicate_pairs": int(frame.duplicated(keep=False).sum() / 2),
        "duplicate_ids_with_different_rows": differing_duplicate_ids,
        "condo_fee_equals_sale_price": int(
            (frame["monthly_condo_fee"] == frame["sale_price"]).sum()
        ),
        "iptu_equals_sale_price": int((frame["yearly_iptu"] == frame["sale_price"]).sum()),
        "apartment_area_above_1000": int(
            (
                (frame["listing_type"] == "apartamento")
                & (frame["usable_area"] > 1_000)
            ).sum()
        ),
        "sale_price_below_100000": int((frame["sale_price"] < 100_000).sum()),
    }


def cross_file_columns(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    column_files: dict[str, list[str]] = {}
    for name, frame in frames.items():
        for column in frame.columns:
            column_files.setdefault(column, []).append(name)
    return [
        {"column": column, "files": names}
        for column, names in sorted(column_files.items())
        if len(names) > 1
    ]


def additional_relationship_diagnostics(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    details = frames["details"]
    mesh = frames["mesh"]
    vivareal = frames["vivareal"]
    merged_locations = details[["airbnb_listing_id", "latitude", "longitude"]].merge(
        mesh[["airbnb_listing_id", "latitude", "longitude", "suburb"]],
        on="airbnb_listing_id",
        how="inner",
        suffixes=("_details", "_mesh"),
        validate="one_to_one" if mesh["airbnb_listing_id"].is_unique else None,
    )
    lat_diff = (
        pd.to_numeric(merged_locations["latitude_details"], errors="coerce")
        - pd.to_numeric(merged_locations["latitude_mesh"], errors="coerce")
    ).abs()
    lon_diff = (
        pd.to_numeric(merged_locations["longitude_details"], errors="coerce")
        - pd.to_numeric(merged_locations["longitude_mesh"], errors="coerce")
    ).abs()

    airbnb_suburbs = set(mesh["suburb"].dropna().astype(str).str.strip().str.casefold())
    vivareal_suburbs = set(
        vivareal["suburb"].dropna().astype(str).str.strip().str.casefold()
    )
    airbnb_types = set(
        details["listing_type"].dropna().astype(str).str.strip().str.casefold()
    )
    vivareal_types = set(
        vivareal["listing_type"].dropna().astype(str).str.strip().str.casefold()
    )
    airbnb_bedrooms = set(pd.to_numeric(details["number_of_bedrooms"], errors="coerce").dropna())
    vivareal_bedrooms = set(pd.to_numeric(vivareal["bedrooms"], errors="coerce").dropna())
    airbnb_ids = set(details["airbnb_listing_id"].dropna().astype(str))
    vivareal_ids = set(vivareal["listing_id"].dropna().astype(str))

    return {
        "details_mesh_coordinates": {
            "joined_rows": int(len(merged_locations)),
            "exact_coordinate_matches": int(((lat_diff == 0) & (lon_diff == 0)).sum()),
            "within_1e_5_degrees": int(((lat_diff <= 1e-5) & (lon_diff <= 1e-5)).sum()),
            "rows_with_any_coordinate_difference": int(((lat_diff > 0) | (lon_diff > 0)).sum()),
            "max_absolute_latitude_difference": json_value(lat_diff.max()),
            "max_absolute_longitude_difference": json_value(lon_diff.max()),
        },
        "airbnb_vivareal_aggregate_dimensions": {
            "literal_listing_id_overlap": len(airbnb_ids & vivareal_ids),
            "shared_normalized_suburbs": sorted(airbnb_suburbs & vivareal_suburbs),
            "airbnb_only_normalized_suburbs": sorted(airbnb_suburbs - vivareal_suburbs),
            "vivareal_only_normalized_suburbs": sorted(vivareal_suburbs - airbnb_suburbs),
            "shared_normalized_listing_types": sorted(airbnb_types & vivareal_types),
            "airbnb_only_normalized_listing_types": sorted(airbnb_types - vivareal_types),
            "vivareal_only_normalized_listing_types": sorted(vivareal_types - airbnb_types),
            "shared_bedroom_counts": sorted(json_value(v) for v in airbnb_bedrooms & vivareal_bedrooms),
        },
    }


def suspicious_values(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    if name == "details":
        checks = {
            "bedrooms_negative": int((frame["number_of_bedrooms"] < 0).sum()),
            "bedrooms_zero": int((frame["number_of_bedrooms"] == 0).sum()),
            "bedrooms_above_10": int((frame["number_of_bedrooms"] > 10).sum()),
            "guests_nonpositive": int((frame["number_of_guests"] <= 0).sum()),
            "guests_above_30": int((frame["number_of_guests"] > 30).sum()),
            "bathrooms_negative": int((frame["number_of_bathrooms"] < 0).sum()),
            "star_rating_outside_0_5": int(
                ((frame["star_rating"] < 0) | (frame["star_rating"] > 5)).sum()
            ),
            "zero_star_with_reviews": int(
                ((frame["star_rating"] == 0) & (frame["number_of_reviews"] > 0)).sum()
            ),
            "cleaning_fee_negative": int((frame["cleaning_fee"] < 0).sum()),
            "min_nights_negative": int((frame["min_nights"] < 0).sum()),
        }
    elif name == "hosts":
        checks = {
            "host_star_outside_0_5": int(
                ((frame["star_rating_host"] < 0) | (frame["star_rating_host"] > 5)).sum()
            ),
            "years_host_negative": int((frame["years_host"] < 0).sum()),
            "months_host_outside_0_11": int(
                ((frame["months_host"] < 0) | (frame["months_host"] > 11)).sum()
            ),
        }
    elif name == "price":
        checks = {
            "price_nonpositive": int((frame["price"] <= 0).sum()),
            "price_above_10000": int((frame["price"] > 10_000).sum()),
            "price_above_100000": int((frame["price"] > 100_000).sum()),
        }
    elif name == "vivareal":
        checks = {
            "sale_price_nonpositive": int((frame["sale_price"] <= 0).sum()),
            "sale_price_below_100000": int((frame["sale_price"] < 100_000).sum()),
            "sale_price_above_50000000": int((frame["sale_price"] > 50_000_000).sum()),
            "usable_area_nonpositive": int((frame["usable_area"] <= 0).sum()),
            "usable_area_above_2000": int((frame["usable_area"] > 2_000).sum()),
            "bedrooms_negative": int((frame["bedrooms"] < 0).sum()),
            "bedrooms_above_20": int((frame["bedrooms"] > 20).sum()),
            "condo_fee_negative": int((frame["monthly_condo_fee"] < 0).sum()),
            "condo_fee_above_10000": int((frame["monthly_condo_fee"] > 10_000).sum()),
        }
    return checks


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = {name: read_csv(name) for name in FILES}

    audits: dict[str, Any] = {}
    dictionary_rows: list[dict[str, Any]] = []
    for name, frame in frames.items():
        dictionary = column_dictionary(name, frame)
        dictionary_rows.extend(dictionary)
        audits[name] = {
            "file": FILES[name],
            "rows": int(frame.shape[0]),
            "columns": int(frame.shape[1]),
            "column_names": list(frame.columns),
            "memory_mb": float(frame.memory_usage(deep=True).sum() / 1024**2),
            "exact_duplicates": exact_duplicate_summary(frame),
            "identifiers": identifier_summary(name, frame),
            "dates": date_summary(name, frame),
            "categories": category_summary(name, frame),
            "suspicious_values": suspicious_values(name, frame),
            "coordinate_quality": coordinate_summary(frame)
            if {"latitude", "longitude"}.issubset(frame.columns)
            else None,
        }

    relationships = {
        "details_to_hosts": validate_hosts(frames["details"], frames["hosts"]),
        "details_to_mesh": validate_mesh(frames["details"], frames["mesh"]),
        "details_to_price": validate_price(frames["details"], frames["price"]),
    }

    report = {
        "source_files": {
            name: str((DATA_DIR / file).relative_to(ROOT))
            for name, file in FILES.items()
        },
        "audits": audits,
        "relationships": relationships,
        "cross_file_columns": cross_file_columns(frames),
        "additional_relationship_diagnostics": additional_relationship_diagnostics(frames),
        "price_semantics": price_semantics(frames["price"]),
        "price_coverage_by_cohort": price_coverage_by_cohort(
            frames["details"], frames["mesh"], frames["price"]
        ),
        "vivareal_quality": vivareal_quality(frames["vivareal"]),
    }

    with (OUTPUT_DIR / "audit_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    flat_dictionary = []
    for row in dictionary_rows:
        flat = dict(row)
        flat["examples"] = json.dumps(flat["examples"], ensure_ascii=False)
        flat["numeric_summary"] = json.dumps(
            flat.get("numeric_summary", {}), ensure_ascii=False
        )
        flat_dictionary.append(flat)
    pd.DataFrame(flat_dictionary).to_csv(
        OUTPUT_DIR / "data_dictionary.csv", index=False
    )

    relationship_rows = []
    for relation, metrics in relationships.items():
        relationship_rows.append(
            {
                "relation": relation,
                "left_key": metrics["left_key"],
                "right_key": metrics["right_key"],
                "cardinality": metrics["cardinality"],
                "left_distinct": metrics["left_distinct"],
                "right_distinct": metrics["right_distinct"],
                "matched_distinct": metrics["matched_distinct"],
                "left_orphan_distinct": metrics["left_orphan_distinct"],
                "right_orphan_distinct": metrics["right_orphan_distinct"],
                "left_coverage": metrics["left_coverage"],
                "right_coverage": metrics["right_coverage"],
            }
        )
    pd.DataFrame(relationship_rows).to_csv(
        OUTPUT_DIR / "relationships.csv", index=False
    )

    print(
        "Auditoria concluída: "
        f"{sum(frame.shape[0] for frame in frames.values()):,} linhas lidas; "
        f"resultados em {OUTPUT_DIR.relative_to(ROOT)}/"
    )


if __name__ == "__main__":
    main()
