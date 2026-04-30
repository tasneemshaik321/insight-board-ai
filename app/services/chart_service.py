from __future__ import annotations

import json

import plotly.express as px

from app.services.data_processor import ProcessedDataset


def _serialize_figure(figure) -> dict:
    return json.loads(figure.to_json())


def build_charts(dataset: ProcessedDataset) -> list[dict]:
    charts: list[dict] = []
    metrics = dataset.metrics
    primary_metric = metrics.get("primary_metric")
    primary_dimension = metrics.get("primary_dimension")
    secondary_dimension = metrics.get("secondary_dimension")

    if metrics.get("has_time_dimension") and len(dataset.monthly) > 1:
        monthly = dataset.monthly.copy()
        monthly["period_label"] = monthly["period"].dt.strftime("%b %Y")
        line_figure = px.line(
            monthly,
            x="period_label",
            y="value",
            markers=True,
            title=f"{primary_metric} trend",
            template="plotly_white",
        )
        charts.append(
            {
                "title": f"{primary_metric.replace('_', ' ').title()} Trend",
                "kind": "line",
                "figure": _serialize_figure(line_figure),
                "description": f"Tracks {primary_metric.replace('_', ' ')} across reporting periods.",
            }
        )

    if not dataset.category.empty:
        category = dataset.category.head(10)
        bar_figure = px.bar(
            category,
            x="label",
            y="value",
            title=f"{primary_metric} by {primary_dimension}",
            template="plotly_white",
        )
        charts.append(
            {
                "title": f"{primary_dimension.replace('_', ' ').title()} Comparison",
                "kind": "bar",
                "figure": _serialize_figure(bar_figure),
                "description": f"Compares {primary_metric.replace('_', ' ')} across {primary_dimension.replace('_', ' ')} values.",
            }
        )

    if not dataset.secondary_category.empty:
        pie_source = dataset.secondary_category.head(8)
        pie_figure = px.pie(
            pie_source,
            names="label",
            values="value",
            title=f"{primary_metric} mix by {secondary_dimension}",
            template="plotly_white",
        )
        charts.append(
            {
                "title": f"{secondary_dimension.replace('_', ' ').title()} Distribution",
                "kind": "pie",
                "figure": _serialize_figure(pie_figure),
                "description": f"Shows how {primary_metric.replace('_', ' ')} is distributed by {secondary_dimension.replace('_', ' ')}.",
            }
        )

    if not dataset.numeric_summary.empty:
        numeric_source = dataset.numeric_summary.head(8)
        numeric_figure = px.bar(
            numeric_source,
            x="metric",
            y="mean",
            title="Average values across numeric fields",
            template="plotly_white",
        )
        charts.append(
            {
                "title": "Numeric Field Summary",
                "kind": "bar",
                "figure": _serialize_figure(numeric_figure),
                "description": "Highlights the average value of inferred numeric columns.",
            }
        )

    return charts
