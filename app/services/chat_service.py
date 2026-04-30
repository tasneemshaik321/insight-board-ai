from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings


def answer_question(analysis: dict, question: str) -> dict[str, str]:
    if not question.strip():
        return {"answer": "Ask a question about the uploaded dataset to get an answer.", "source": "local"}

    context = {
        "filename": analysis.get("filename"),
        "metrics": analysis.get("metrics"),
        "schema": analysis.get("schema"),
        "data_quality": analysis.get("data_quality"),
        "anomalies": analysis.get("anomalies"),
        "insights": analysis.get("insights"),
    }

    if settings.openai_api_key:
        try:
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.responses.create(
                model=settings.openai_model,
                input=[
                    {
                        "role": "system",
                        "content": "You are a concise dataset analyst. Answer only from the provided dataset summary and admit uncertainty when needed.",
                    },
                    {
                        "role": "user",
                        "content": f"Dataset summary: {json.dumps(context, default=str)}\n\nQuestion: {question}",
                    },
                ],
            )
            return {"answer": response.output_text.strip(), "source": "openai"}
        except Exception:
            pass

    metrics = analysis.get("metrics", {})
    schema = analysis.get("schema", {})
    question_lower = question.lower()
    if "metric" in question_lower or "measure" in question_lower:
        metric = metrics.get("primary_metric") or "No primary metric was inferred"
        return {"answer": f"The current primary metric is `{metric}` based on the inferred schema.", "source": "local"}
    if "column" in question_lower or "schema" in question_lower:
        columns = ", ".join(schema.get("columns", [])[:12]) or "No columns found."
        return {"answer": f"The dataset columns include: {columns}.", "source": "local"}
    if "anomal" in question_lower:
        count = len(analysis.get("anomalies", []))
        return {"answer": f"The analysis flagged {count} anomaly signals in the current dataset.", "source": "local"}

    return {
        "answer": (
            f"This dataset has {metrics.get('row_count', 0)} rows. "
            f"The inferred primary metric is {metrics.get('primary_metric') or 'not available'}, "
            f"and the leading segment is {metrics.get('top_segment') or 'not available'}."
        ),
        "source": "local",
    }
