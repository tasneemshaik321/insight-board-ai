from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KPIItem(BaseModel):
    label: str
    value: str
    delta: str | None = None


class ChartPayload(BaseModel):
    title: str
    kind: str
    figure: dict[str, Any]
    description: str


class InsightBundle(BaseModel):
    executive_summary: str
    chart_explanations: list[str]
    recommendations: list[str]
    risks: list[str]
    opportunities: list[str]


class AnomalyItem(BaseModel):
    metric: str
    period: str
    value: float
    severity: str
    explanation: str


class SchemaProfile(BaseModel):
    columns: list[str]
    numeric_columns: list[str]
    categorical_columns: list[str]
    datetime_columns: list[str]
    inferred_primary_metric: str | None = None
    inferred_primary_dimension: str | None = None
    inferred_secondary_dimension: str | None = None
    inferred_time_column: str | None = None
    applied_mapping: dict[str, str | None]


class DataQualityReport(BaseModel):
    missing_cells: int
    duplicate_rows: int
    duplicate_columns: int
    completeness_pct: float
    missing_by_column: list[dict[str, Any]] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    analysis_id: str
    filename: str
    row_count: int
    metrics: dict[str, Any]
    kpis: list[KPIItem]
    charts: list[ChartPayload]
    anomalies: list[AnomalyItem]
    insights: InsightBundle
    schema_info: SchemaProfile = Field(alias="schema")
    data_quality: DataQualityReport
    preview: list[dict[str, Any]] = Field(default_factory=list)
