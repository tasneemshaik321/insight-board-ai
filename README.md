# Insight Engine

Insight Engine is a FastAPI starter project that turns raw business data into:

- KPI metrics and cleaned aggregates
- interactive charts
- anomaly detection
- AI-generated executive summaries
- recommendations for action
- a React-based reporting dashboard

## Features

- CSV and Excel upload support
- Pandas-based preprocessing with missing-value handling
- KPI aggregation for revenue, profit margin, growth, top product, and top category
- Plotly dashboard charts for trends, category comparisons, and distribution
- Statistical anomaly detection for revenue spikes and drops
- Recommendation generation from performance patterns
- Optional OpenAI-powered narrative generation with a local fallback summary
- React frontend for upload, dashboard review, manual mapping, chat, and export
- Manual column mapping for difficult datasets
- Schema and data-quality inspection panels
- Dataset Q&A assistant
- PDF report export for demo-ready outputs

## Project structure

```text
app/
  main.py
  config.py
  models.py
  services/
frontend/
  src/
sample_data/
requirements.txt
```

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

For React development only:

```bash
cd frontend
npm install
npm run dev
```

## OpenAI integration

Create a local `.env` file in the project root if you want AI-written summaries:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

You can copy `.env.example` to `.env` and replace the placeholder value with your real key.

Without an API key, the app still returns rule-based narrative summaries and recommendations.

## API

`POST /api/analyze`

- form-data field: `file`
- accepts `.csv`, `.xlsx`, `.xls`
- returns KPIs, charts, anomaly flags, preview rows, and narrative insights

## Sample data

Use [sample_data/sales_sample.csv](sample_data/sales_sample.csv) to test the workflow quickly.
