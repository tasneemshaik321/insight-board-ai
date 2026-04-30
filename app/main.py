from __future__ import annotations

import json
import logging
import math
import traceback
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.models import DashboardResponse
from app.services.anomaly_service import detect_anomalies
from app.services.chart_service import build_charts
from app.services.chat_service import answer_question
from app.services.data_processor import build_kpis, load_dataframe, process_dataframe
from app.services.insight_service import generate_insights
from app.services.recommendation_service import build_recommendations
from app.services.report_service import build_pdf_report


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR.parent / "server_error.log"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
ANALYSIS_STORE: dict[str, dict[str, Any]] = {}

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

app = FastAPI(title="Insight Engine", version="2.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def _sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_json(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _sanitize_for_json(value.item())
        except Exception:
            pass
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


def _parse_mapping(mapping_raw: str | None) -> dict[str, str | None]:
    if not mapping_raw:
        return {}
    try:
        parsed = json.loads(mapping_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Column mapping must be valid JSON.") from exc
    allowed = {"primary_metric", "primary_dimension", "secondary_dimension", "time_column"}
    return {key: (value or None) for key, value in parsed.items() if key in allowed}


def _run_analysis(filename: str, content: bytes, mapping: dict[str, str | None]) -> dict[str, Any]:
    df = load_dataframe(filename, content)
    dataset = process_dataframe(df, overrides=mapping)
    charts = build_charts(dataset)
    anomalies = detect_anomalies(dataset)
    recommendations, risks, opportunities = build_recommendations(dataset, anomalies)
    insights = generate_insights(dataset, charts, anomalies, recommendations, risks, opportunities)
    kpis = build_kpis(dataset)

    analysis_id = str(uuid4())
    payload = DashboardResponse(
        analysis_id=analysis_id,
        filename=filename,
        row_count=len(dataset.cleaned),
        metrics=dataset.metrics,
        kpis=kpis,
        charts=charts,
        anomalies=anomalies,
        insights=insights,
        schema=dataset.schema,
        data_quality=dataset.data_quality,
        preview=dataset.preview,
    )
    safe_payload = _sanitize_for_json(jsonable_encoder(payload))
    ANALYSIS_STORE[analysis_id] = safe_payload
    return safe_payload


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.error("Unhandled error on %s\n%s", request.url.path, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {exc}",
            "log_file": str(LOG_FILE),
        },
    )


@app.get("/", response_class=HTMLResponse)
async def home() -> Response:
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        """
        <html>
          <body style="font-family: sans-serif; padding: 32px;">
            <h1>Frontend build not found</h1>
            <p>Install and build the React frontend first:</p>
            <pre>cd frontend
npm install
npm run build</pre>
            <p>Then restart the FastAPI server.</p>
          </body>
        </html>
        """
    )


@app.get("/assets/{asset_path:path}")
async def frontend_assets(asset_path: str) -> Response:
    asset_file = FRONTEND_ASSETS / asset_path
    if asset_file.exists():
        return FileResponse(asset_file)
    raise HTTPException(status_code=404, detail="Frontend asset not found.")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    mapping: str | None = Form(default=None),
) -> JSONResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        payload = _run_analysis(file.filename or "uploaded_file", content, _parse_mapping(mapping))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
    return JSONResponse(content=payload)


@app.post("/api/chat")
async def chat_with_analysis(
    analysis_id: str = Form(...),
    question: str = Form(...),
) -> JSONResponse:
    analysis = ANALYSIS_STORE.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis session not found. Re-run the dataset analysis first.")
    answer = answer_question(analysis, question)
    return JSONResponse(content=answer)


@app.get("/api/report/{analysis_id}")
async def export_report(analysis_id: str) -> Response:
    analysis = ANALYSIS_STORE.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis session not found. Re-run the dataset analysis first.")
    pdf_bytes = build_pdf_report(analysis)
    filename = f"{Path(analysis.get('filename', 'report')).stem}_report.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
