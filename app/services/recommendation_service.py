from __future__ import annotations

from app.services.data_processor import ProcessedDataset


def build_recommendations(dataset: ProcessedDataset, anomalies: list[dict]) -> tuple[list[str], list[str], list[str]]:
    metrics = dataset.metrics
    primary_metric = (metrics.get("primary_metric") or "metric").replace("_", " ")
    primary_dimension = (metrics.get("primary_dimension") or "segment").replace("_", " ")

    recommendations: list[str] = []
    risks: list[str] = []
    opportunities: list[str] = []

    if metrics.get("has_time_dimension") and metrics.get("latest_growth_pct") is not None:
        growth = float(metrics["latest_growth_pct"])
        if growth < 0:
            risks.append(f"{primary_metric.title()} is declining in the latest period.")
            recommendations.append(f"Review the drivers behind the recent drop in {primary_metric} and prioritize recovery actions in weaker periods.")
        else:
            opportunities.append(f"{primary_metric.title()} is growing in the latest period and may support scaling the strongest segments.")

    if not dataset.category.empty:
        top_share = float(dataset.category.iloc[0]["value"]) / max(float(dataset.category["value"].sum()), 1.0)
        top_label = str(dataset.category.iloc[0]["label"])
        if top_share > 0.5:
            risks.append(f"{primary_metric.title()} is highly concentrated in {top_label}, which can increase dependency risk.")
        opportunities.append(f"{top_label} is the strongest {primary_dimension} and is a good candidate for deeper focus.")
        recommendations.append(f"Compare lower-performing {primary_dimension} values against {top_label} to identify repeatable success patterns.")

    if anomalies:
        risks.append("Outliers were detected and should be reviewed before making decisions from the dashboard.")
        recommendations.append("Inspect flagged rows or periods to confirm whether anomalies are true signals or data-quality issues.")

    if len(metrics.get("numeric_columns", [])) <= 1:
        recommendations.append("Add more numeric fields to unlock richer trend, comparison, and anomaly analysis.")

    if not recommendations:
        recommendations.append("Use the highest-volume dimensions as the first candidates for deeper drill-down.")
    if not risks:
        risks.append("No major structural risks were detected in the inferred dataset profile.")
    if not opportunities:
        opportunities.append("The inferred schema is stable enough to support further segmentation and benchmarking.")

    dedupe = lambda items: list(dict.fromkeys(items))
    return dedupe(recommendations), dedupe(risks), dedupe(opportunities)
