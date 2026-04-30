from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.services.data_processor import ProcessedDataset


def _fallback_summary(
    dataset: ProcessedDataset,
    charts: list[dict],
    anomalies: list[dict],
    recommendations: list[str],
    risks: list[str],
    opportunities: list[str],
) -> dict:
    metrics = dataset.metrics
    primary_metric = (metrics.get("primary_metric") or "metric").replace("_", " ")
    primary_dimension = (metrics.get("primary_dimension") or "segment").replace("_", " ")
    secondary_dimension = metrics.get("secondary_dimension")

    if metrics.get("has_time_dimension") and metrics.get("latest_growth_pct") is not None:
        growth_text = f"{primary_metric} changed by {metrics['latest_growth_pct']:.1f}% in the latest period"
    else:
        growth_text = f"the dataset centers on {primary_metric}"

    executive_summary = (
        f"This dataset contains {metrics['row_count']} rows and {metrics['column_count']} columns. "
        f"The inferred primary measure is {primary_metric}, and {growth_text}. "
        f"The leading {primary_dimension} is {metrics['top_segment']} with a total {primary_metric} of {metrics['total_value']:,.2f}."
    )

    if secondary_dimension:
        executive_summary += f" Secondary analysis also uses {secondary_dimension.replace('_', ' ')} as a supporting dimension."
    if anomalies:
        executive_summary += f" {len(anomalies)} anomalies were flagged for review."

    chart_explanations = []
    for chart in charts:
        if chart["kind"] == "line":
            chart_explanations.append("The line chart shows how the inferred primary metric changes over time.")
        elif chart["kind"] == "pie":
            chart_explanations.append("The distribution view highlights concentration across a secondary dimension.")
        else:
            chart_explanations.append("The comparison chart helps identify which inferred segments contribute most strongly.")

    return {
        "executive_summary": executive_summary,
        "chart_explanations": chart_explanations,
        "recommendations": recommendations,
        "risks": risks,
        "opportunities": opportunities,
    }


def generate_insights(
    dataset: ProcessedDataset,
    charts: list[dict],
    anomalies: list[dict],
    recommendations: list[str],
    risks: list[str],
    opportunities: list[str],
) -> dict:
    if not settings.openai_api_key:
        return _fallback_summary(dataset, charts, anomalies, recommendations, risks, opportunities)

    try:
        payload = {
            "metrics": dataset.metrics,
            "monthly_records": dataset.monthly.tail(12).to_dict(orient="records"),
            "category_records": dataset.category.head(8).to_dict(orient="records"),
            "secondary_records": dataset.secondary_category.head(8).to_dict(orient="records"),
            "numeric_summary": dataset.numeric_summary.head(8).to_dict(orient="records"),
            "anomalies": anomalies,
            "recommendations_seed": recommendations,
            "risks_seed": risks,
            "opportunities_seed": opportunities,
        }

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a business and data analyst. Return valid JSON with keys: executive_summary, "
                        "chart_explanations, recommendations, risks, opportunities. Tailor the analysis to the "
                        "inferred schema rather than assuming a sales dataset."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Analyze this inferred dataset profile: {json.dumps(payload, default=str)}",
                },
            ],
        )
        parsed = json.loads(response.output_text)
    except Exception:
        return _fallback_summary(dataset, charts, anomalies, recommendations, risks, opportunities)

    return {
        "executive_summary": parsed.get("executive_summary", ""),
        "chart_explanations": parsed.get("chart_explanations", []),
        "recommendations": parsed.get("recommendations", recommendations),
        "risks": parsed.get("risks", risks),
        "opportunities": parsed.get("opportunities", opportunities),
    }
