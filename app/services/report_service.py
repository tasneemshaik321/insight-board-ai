from __future__ import annotations

from io import BytesIO


def build_pdf_report(analysis: dict) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("PDF export requires reportlab. Run `pip install -r requirements.txt`.") from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Insight Engine Report", styles["Title"]))
    elements.append(Paragraph(analysis.get("filename", "Uploaded dataset"), styles["Heading2"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(analysis["insights"]["executive_summary"], styles["BodyText"]))
    elements.append(Spacer(1, 12))

    kpi_rows = [["KPI", "Value", "Delta"]]
    for item in analysis.get("kpis", []):
        kpi_rows.append([item["label"], item["value"], item.get("delta") or "-"])
    kpi_table = Table(kpi_rows, hAlign="LEFT")
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d8c6ab")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(kpi_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Schema Profile", styles["Heading3"]))
    schema = analysis.get("schema", {})
    schema_text = (
        f"Primary metric: {schema.get('inferred_primary_metric') or 'N/A'}<br/>"
        f"Primary dimension: {schema.get('inferred_primary_dimension') or 'N/A'}<br/>"
        f"Secondary dimension: {schema.get('inferred_secondary_dimension') or 'N/A'}<br/>"
        f"Time column: {schema.get('inferred_time_column') or 'N/A'}"
    )
    elements.append(Paragraph(schema_text, styles["BodyText"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Recommendations", styles["Heading3"]))
    for item in analysis["insights"].get("recommendations", []):
        elements.append(Paragraph(f"- {item}", styles["BodyText"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Anomalies", styles["Heading3"]))
    anomaly_rows = [["Metric", "Period", "Severity", "Value"]]
    for item in analysis.get("anomalies", [])[:10]:
        anomaly_rows.append([item["metric"], item["period"], item["severity"], str(item["value"])])
    if len(anomaly_rows) == 1:
        anomaly_rows.append(["None", "-", "-", "-"])
    anomaly_table = Table(anomaly_rows, hAlign="LEFT")
    anomaly_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ecdcc2")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(anomaly_table)

    doc.build(elements)
    return buffer.getvalue()
