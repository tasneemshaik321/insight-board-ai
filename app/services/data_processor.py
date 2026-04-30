from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd


ALIAS_HINTS = {
    "time": ["date", "period", "month", "week", "year", "timestamp", "order_date"],
    "metric": ["revenue", "sales", "amount", "price", "profit", "cost", "quantity", "units", "value", "score", "rating"],
    "dimension": ["product", "category", "region", "segment", "brand", "market", "type", "item", "name"],
}


@dataclass
class ProcessedDataset:
    raw: pd.DataFrame
    cleaned: pd.DataFrame
    monthly: pd.DataFrame
    category: pd.DataFrame
    secondary_category: pd.DataFrame
    numeric_summary: pd.DataFrame
    metrics: dict[str, Any]
    preview: list[dict[str, Any]]
    schema: dict[str, Any]
    data_quality: dict[str, Any]


def load_dataframe(filename: str, content: bytes) -> pd.DataFrame:
    lowered = filename.lower()
    buffer = BytesIO(content)
    if lowered.endswith(".csv"):
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            buffer.seek(0)
            try:
                return pd.read_csv(buffer, encoding=encoding)
            except UnicodeDecodeError:
                continue
        buffer.seek(0)
        return pd.read_csv(buffer)
    if lowered.endswith(".xlsx") or lowered.endswith(".xls"):
        return pd.read_excel(buffer)
    raise ValueError("Unsupported file type. Upload a CSV or Excel file.")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = {column: str(column).strip().lower().replace(" ", "_") for column in df.columns}
    return df.rename(columns=normalized)


def _best_time_column(df: pd.DataFrame) -> str | None:
    candidates: list[tuple[float, str]] = []
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            candidates.append((1.0, column))
            continue
        if pd.api.types.is_numeric_dtype(series):
            continue
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
        ratio = parsed.notna().mean()
        if any(hint in column for hint in ALIAS_HINTS["time"]):
            ratio += 0.15
        if ratio >= 0.6:
            candidates.append((ratio, column))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    numeric: list[tuple[float, str]] = []
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_numeric_dtype(series):
            numeric.append((1.0, column))
            continue
        if pd.api.types.is_datetime64_any_dtype(series):
            continue
        converted = pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")
        ratio = converted.notna().mean()
        if any(hint in column for hint in ALIAS_HINTS["metric"]):
            ratio += 0.1
        if ratio >= 0.7:
            numeric.append((ratio, column))
    numeric.sort(reverse=True)
    return [column for _, column in numeric]


def _categorical_columns(df: pd.DataFrame, excluded: set[str]) -> list[str]:
    categorical: list[tuple[float, str]] = []
    for column in df.columns:
        if column in excluded:
            continue
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            continue
        unique_count = series.nunique(dropna=True)
        if unique_count == 0:
            continue
        ratio = unique_count / max(len(series), 1)
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            score = 1 - min(ratio, 1)
            if any(hint in column for hint in ALIAS_HINTS["dimension"]):
                score += 0.25
            categorical.append((score, column))
        elif unique_count <= 20:
            categorical.append((0.25, column))
    categorical.sort(reverse=True)
    return [column for _, column in categorical]


def _pick_primary_metric(numeric_columns: list[str]) -> str | None:
    if not numeric_columns:
        return None
    for hint in ["revenue", "sales", "amount", "price", "profit", "value", "score", "rating", "quantity"]:
        for column in numeric_columns:
            if hint in column:
                return column
    return numeric_columns[0]


def _build_schema(
    columns: list[str],
    numeric_columns: list[str],
    categorical_columns: list[str],
    time_column: str | None,
    primary_metric: str | None,
    primary_dimension: str | None,
    secondary_dimension: str | None,
    overrides: dict[str, str | None] | None,
) -> dict[str, Any]:
    return {
        "columns": columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "datetime_columns": [time_column] if time_column else [],
        "inferred_primary_metric": primary_metric,
        "inferred_primary_dimension": primary_dimension,
        "inferred_secondary_dimension": secondary_dimension,
        "inferred_time_column": time_column,
        "applied_mapping": {
            "primary_metric": overrides.get("primary_metric") if overrides else primary_metric,
            "primary_dimension": overrides.get("primary_dimension") if overrides else primary_dimension,
            "secondary_dimension": overrides.get("secondary_dimension") if overrides else secondary_dimension,
            "time_column": overrides.get("time_column") if overrides else time_column,
        },
    }


def _build_data_quality(df: pd.DataFrame) -> dict[str, Any]:
    total_cells = max(df.shape[0] * max(df.shape[1], 1), 1)
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    duplicate_columns = int(df.columns.duplicated().sum())
    missing_by_column = (
        df.isna()
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .rename_axis("column")
        .reset_index(name="missing")
        .to_dict(orient="records")
    )
    return {
        "missing_cells": missing_cells,
        "duplicate_rows": duplicate_rows,
        "duplicate_columns": duplicate_columns,
        "completeness_pct": round(((total_cells - missing_cells) / total_cells) * 100, 2),
        "missing_by_column": missing_by_column,
    }


def _fill_clean_values(df: pd.DataFrame, numeric_columns: list[str], categorical_columns: list[str], time_column: str | None) -> pd.DataFrame:
    result = df.copy()
    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(result[column]):
            result[column] = pd.to_numeric(result[column].astype(str).str.replace(",", "", regex=False), errors="coerce")
        median = result[column].median() if result[column].notna().any() else 0.0
        result[column] = result[column].fillna(median)

    for column in categorical_columns:
        result[column] = result[column].fillna("Unknown").astype(str)

    if time_column:
        result[time_column] = pd.to_datetime(result[time_column], errors="coerce", format="mixed")
        result = result.dropna(subset=[time_column]).copy()
        result["date"] = result[time_column]
    else:
        result["date"] = pd.Timestamp.today().normalize()

    if result.empty:
        raise ValueError("No usable rows were found in the uploaded file after cleaning.")

    result["period"] = result["date"].dt.to_period("M").dt.to_timestamp()
    return result.reset_index(drop=True)


def _build_grouping(df: pd.DataFrame, dimension_column: str | None, metric_column: str | None, label: str) -> pd.DataFrame:
    if not dimension_column or not metric_column:
        return pd.DataFrame(columns=[label, "value"])
    grouped = (
        df.groupby(dimension_column, as_index=False)
        .agg(value=(metric_column, "sum"))
        .sort_values("value", ascending=False)
    )
    return grouped.rename(columns={dimension_column: label})


def process_dataframe(df: pd.DataFrame, overrides: dict[str, str | None] | None = None) -> ProcessedDataset:
    normalized = _normalize_columns(df)
    columns = list(normalized.columns)
    inferred_time_column = _best_time_column(normalized)
    numeric_columns = _numeric_columns(normalized)
    categorical_columns = _categorical_columns(normalized, excluded=set(numeric_columns) | ({inferred_time_column} if inferred_time_column else set()))

    primary_metric = (overrides or {}).get("primary_metric") or _pick_primary_metric(numeric_columns)
    secondary_metric = numeric_columns[1] if len(numeric_columns) > 1 else None
    primary_dimension = (overrides or {}).get("primary_dimension") or (categorical_columns[0] if categorical_columns else None)
    secondary_dimension = (overrides or {}).get("secondary_dimension") or (categorical_columns[1] if len(categorical_columns) > 1 else None)
    time_column = (overrides or {}).get("time_column") or inferred_time_column

    for column in [primary_metric, primary_dimension, secondary_dimension, time_column]:
        if column and column not in columns:
            raise ValueError(f"Mapped column '{column}' is not present in the uploaded file.")

    if primary_metric and primary_metric not in numeric_columns:
        numeric_columns = [primary_metric, *[column for column in numeric_columns if column != primary_metric]]
    if primary_dimension and primary_dimension not in categorical_columns:
        categorical_columns = [primary_dimension, *[column for column in categorical_columns if column != primary_dimension]]
    if secondary_dimension and secondary_dimension not in categorical_columns:
        categorical_columns = [secondary_dimension, *[column for column in categorical_columns if column != secondary_dimension]]

    cleaned = _fill_clean_values(normalized, numeric_columns, categorical_columns, time_column)
    if primary_metric is None:
        raise ValueError("No numeric columns were detected. Upload a dataset with at least one numeric field or map one manually.")

    monthly = pd.DataFrame(columns=["period", "value", "growth_pct"])
    if time_column:
        monthly = (
            cleaned.groupby("period", as_index=False)
            .agg(value=(primary_metric, "sum"))
            .sort_values("period")
        )
        monthly["growth_pct"] = monthly["value"].pct_change() * 100

    category = _build_grouping(cleaned, primary_dimension, primary_metric, "label")
    secondary_category = _build_grouping(cleaned, secondary_dimension, primary_metric, "label")

    numeric_summary = pd.DataFrame(columns=["metric", "sum", "mean", "min", "max", "std"])
    summary_rows = []
    for column in numeric_columns[:8]:
        summary_rows.append(
            {
                "metric": column,
                "sum": float(cleaned[column].sum()),
                "mean": float(cleaned[column].mean()),
                "min": float(cleaned[column].min()),
                "max": float(cleaned[column].max()),
                "std": float(cleaned[column].std(ddof=0) or 0.0),
            }
        )
    numeric_summary = pd.DataFrame(summary_rows)

    total_value = float(cleaned[primary_metric].sum())
    avg_value = float(cleaned[primary_metric].mean())
    latest_growth = monthly["growth_pct"].iloc[-1] if len(monthly) > 1 else None
    top_segment = str(category.iloc[0]["label"]) if not category.empty else "Unknown"

    metrics: dict[str, Any] = {
        "row_count": int(len(cleaned)),
        "column_count": int(len(cleaned.columns)),
        "primary_metric": primary_metric,
        "secondary_metric": secondary_metric,
        "primary_dimension": primary_dimension,
        "secondary_dimension": secondary_dimension,
        "time_column": time_column,
        "has_time_dimension": bool(time_column),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "total_value": round(total_value, 2),
        "average_value": round(avg_value, 2),
        "latest_growth_pct": round(float(latest_growth), 2) if latest_growth is not None and not pd.isna(latest_growth) else None,
        "top_segment": top_segment,
    }

    preview = cleaned.head(10).copy()
    preview["date"] = preview["date"].dt.strftime("%Y-%m-%d")

    schema = _build_schema(
        columns=columns,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        time_column=time_column,
        primary_metric=primary_metric,
        primary_dimension=primary_dimension,
        secondary_dimension=secondary_dimension,
        overrides=overrides,
    )
    data_quality = _build_data_quality(normalized)

    return ProcessedDataset(
        raw=df,
        cleaned=cleaned,
        monthly=monthly,
        category=category,
        secondary_category=secondary_category,
        numeric_summary=numeric_summary,
        metrics=metrics,
        preview=preview.to_dict(orient="records"),
        schema=schema,
        data_quality=data_quality,
    )


def _format_pct(value: float | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return f"{value:.1f}%"


def build_kpis(dataset: ProcessedDataset) -> list[dict[str, str | None]]:
    metrics = dataset.metrics
    primary_metric = metrics.get("primary_metric") or "metric"
    primary_dimension = metrics.get("primary_dimension") or "segment"
    numeric_count = len(metrics.get("numeric_columns", []))

    return [
        {
            "label": f"Total {primary_metric.replace('_', ' ').title()}",
            "value": f"{metrics['total_value']:,.2f}",
            "delta": _format_pct(metrics["latest_growth_pct"]),
        },
        {
            "label": f"Average {primary_metric.replace('_', ' ').title()}",
            "value": f"{metrics['average_value']:,.2f}",
            "delta": None,
        },
        {
            "label": "Numeric Metrics",
            "value": str(numeric_count),
            "delta": None,
        },
        {
            "label": f"Top {primary_dimension.replace('_', ' ').title()}",
            "value": str(metrics["top_segment"]),
            "delta": None,
        },
    ]
