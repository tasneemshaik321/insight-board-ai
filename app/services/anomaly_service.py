from __future__ import annotations

import pandas as pd

from app.services.data_processor import ProcessedDataset


def detect_anomalies(dataset: ProcessedDataset) -> list[dict]:
    metrics = dataset.metrics
    primary_metric = metrics.get("primary_metric")
    if not primary_metric:
        return []

    anomalies: list[dict] = []

    if metrics.get("has_time_dimension") and len(dataset.monthly) > 2:
        monthly = dataset.monthly.copy()
        mean_value = monthly["value"].mean()
        std_value = monthly["value"].std(ddof=0) or 0.0
        for _, row in monthly.iterrows():
            if std_value and abs(row["value"] - mean_value) > 1.8 * std_value:
                anomalies.append(
                    {
                        "metric": primary_metric.replace("_", " ").title(),
                        "period": pd.to_datetime(row["period"]).strftime("%b %Y"),
                        "value": round(float(row["value"]), 2),
                        "severity": "high",
                        "explanation": "This period is materially outside the dataset's normal range.",
                    }
                )
        growth_std = monthly["growth_pct"].fillna(0.0).std(ddof=0) or 0.0
        if growth_std:
            growth_mean = monthly["growth_pct"].fillna(0.0).mean()
            growth_outliers = monthly[(monthly["growth_pct"].fillna(0.0) - growth_mean).abs() > 2.2 * growth_std]
            for _, row in growth_outliers.iterrows():
                anomalies.append(
                    {
                        "metric": "Growth Rate",
                        "period": pd.to_datetime(row["period"]).strftime("%b %Y"),
                        "value": round(float(row["growth_pct"]), 2),
                        "severity": "medium",
                        "explanation": "Period-over-period change is unusually sharp versus the rest of the series.",
                    }
                )

    series = dataset.cleaned[primary_metric]
    std_value = series.std(ddof=0) or 0.0
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    iqr_mask = pd.Series(False, index=dataset.cleaned.index)
    if iqr:
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        iqr_mask = (series < lower_bound) | (series > upper_bound)

    z_mask = pd.Series(False, index=dataset.cleaned.index)
    if std_value:
        z_scores = ((series - series.mean()) / std_value).abs()
        z_mask = z_scores > 2.5

    outlier_rows = dataset.cleaned.loc[(iqr_mask | z_mask), [primary_metric]].head(5)
    for index, row in outlier_rows.iterrows():
        anomalies.append(
            {
                "metric": primary_metric.replace("_", " ").title(),
                "period": f"Row {index + 1}",
                "value": round(float(row[primary_metric]), 2),
                "severity": "medium",
                "explanation": "This row looks like an outlier compared with the rest of the dataset.",
            }
        )
    quality = dataset.data_quality
    if quality["duplicate_rows"] > 0:
        anomalies.append(
            {
                "metric": "Duplicate Rows",
                "period": "Dataset",
                "value": float(quality["duplicate_rows"]),
                "severity": "medium",
                "explanation": "Duplicate rows were found and may distort summary statistics.",
            }
        )
    if quality["missing_cells"] > 0 and quality["completeness_pct"] < 95:
        anomalies.append(
            {
                "metric": "Missing Data",
                "period": "Dataset",
                "value": float(quality["missing_cells"]),
                "severity": "medium",
                "explanation": "Missing values are high enough to influence downstream analysis.",
            }
        )

    unique = {(item["metric"], item["period"], item["value"]): item for item in anomalies}
    return list(unique.values())
