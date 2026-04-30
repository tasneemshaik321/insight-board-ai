import { useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";

const emptyMapping = {
  primary_metric: "",
  primary_dimension: "",
  secondary_dimension: "",
  time_column: ""
};

function ChartCard({ chart, index }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) {
      return undefined;
    }
    Plotly.newPlot(ref.current, chart.figure.data, chart.figure.layout, {
      responsive: true,
      displayModeBar: false
    });
    return () => {
      if (ref.current) {
        Plotly.purge(ref.current);
      }
    };
  }, [chart, index]);

  return (
    <article className="panel chart-panel">
      <div className="panel-header">
        <h2>{chart.title}</h2>
      </div>
      <p>{chart.description}</p>
      <div ref={ref} className="chart-host" />
    </article>
  );
}

function ListPanel({ title, items, id }) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      <ul id={id}>
        {items.map((item) => (
          <li key={`${title}-${item}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function App() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("Waiting for a CSV or Excel file.");
  const [analysis, setAnalysis] = useState(null);
  const [mapping, setMapping] = useState(emptyMapping);
  const [question, setQuestion] = useState("");
  const [chatAnswer, setChatAnswer] = useState("Ask a question after analysis to get a dataset-aware answer.");

  const runAnalysis = async (mappingOverride = {}) => {
    if (!file) {
      setStatus("Choose a CSV or Excel file first.");
      return;
    }

    setStatus("Analyzing dataset...");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mapping", JSON.stringify(mappingOverride));

    const response = await fetch("/api/analyze", { method: "POST", body: formData });
    const rawText = await response.text();
    let payload = null;
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = null;
    }
    if (!response.ok) {
      throw new Error(payload?.detail || rawText || "Analysis failed");
    }
    if (!payload) {
      throw new Error("The server returned an unexpected response.");
    }

    setAnalysis(payload);
    setMapping({
      primary_metric: payload.schema.applied_mapping.primary_metric || payload.schema.inferred_primary_metric || "",
      primary_dimension: payload.schema.applied_mapping.primary_dimension || payload.schema.inferred_primary_dimension || "",
      secondary_dimension: payload.schema.applied_mapping.secondary_dimension || payload.schema.inferred_secondary_dimension || "",
      time_column: payload.schema.applied_mapping.time_column || payload.schema.inferred_time_column || ""
    });
    setStatus("Analysis complete.");
  };

  const submitUpload = async (event) => {
    event.preventDefault();
    try {
      await runAnalysis({});
    } catch (error) {
      setStatus(error.message);
    }
  };

  const submitMapping = async (event) => {
    event.preventDefault();
    try {
      await runAnalysis(mapping);
    } catch (error) {
      setStatus(error.message);
    }
  };

  const submitChat = async (event) => {
    event.preventDefault();
    if (!analysis) {
      setChatAnswer("Analyze a dataset first.");
      return;
    }
    const formData = new FormData();
    formData.append("analysis_id", analysis.analysis_id);
    formData.append("question", question);
    const response = await fetch("/api/chat", { method: "POST", body: formData });
    const payload = await response.json();
    if (!response.ok) {
      setChatAnswer(payload.detail || "Chat request failed.");
      return;
    }
    setChatAnswer(`${payload.answer} (${payload.source})`);
  };

  const exportReport = () => {
    if (!analysis) {
      setStatus("Analyze a dataset before exporting a report.");
      return;
    }
    window.open(`/api/report/${analysis.analysis_id}`, "_blank");
  };

  const buildOptions = (values, allowBlank = false) => {
    const items = allowBlank ? ["", ...values] : values;
    return items.map((value) => (
      <option key={`${value || "blank"}-${allowBlank}`} value={value}>
        {value || "None"}
      </option>
    ));
  };

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Business analytics reporting</p>
          <h1>Turn structured CSV data into executive summaries, chart explanations, anomaly commentary, and action points.</h1>
          <p className="lede">
            Designed for monthly performance reporting workflows, this application helps analytics teams upload
            structured data and automatically generate dashboards, chart-to-text narratives, trend-based summaries,
            and recommended next steps.
          </p>
          <div className="hero-points">
            <div className="hero-point"><span>Input</span><strong>Sales, KPI, and trend datasets</strong></div>
            <div className="hero-point"><span>Output</span><strong>Executive-ready monthly performance report</strong></div>
            <div className="hero-point"><span>Highlights</span><strong>Chart-to-text, anomaly commentary, and recommendations</strong></div>
          </div>
        </div>
        <form className="upload-card" onSubmit={submitUpload}>
          <label htmlFor="file-input" className="upload-label">Upload monthly performance dataset</label>
          <input
            id="file-input"
            name="file"
            type="file"
            accept=".csv,.xlsx,.xls"
            required
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <button type="submit">Generate Performance Report</button>
          <p className="status-text">{status}</p>
        </form>
      </section>

      <section className="workflow-strip">
        <article className="workflow-card">
          <span>01</span>
          <h2>Structured Input</h2>
          <p>Upload sales data, KPI metrics, or monthly and weekly performance records.</p>
        </article>
        <article className="workflow-card">
          <span>02</span>
          <h2>Automated Analysis</h2>
          <p>The app infers schema, builds charts, checks data quality, and detects anomalies.</p>
        </article>
        <article className="workflow-card">
          <span>03</span>
          <h2>Narrative Output</h2>
          <p>Receive executive summaries, chart commentary, trend narratives, and recommended actions.</p>
        </article>
      </section>

      {!analysis ? (
        <section className="preview-strip">
          <article className="preview-card">
            <span className="preview-label">Executive Summary</span>
            <h2>Readable performance narrative</h2>
            <p>Automatically converts raw performance tables into concise executive summaries and trend commentary.</p>
          </article>
          <article className="preview-card">
            <span className="preview-label">Anomaly Detection</span>
            <h2>Faster issue spotting</h2>
            <p>Highlights sudden drops, spikes, missing-data concerns, and unusual outliers before analysts write the report.</p>
          </article>
          <article className="preview-card">
            <span className="preview-label">Action Points</span>
            <h2>Decision-ready outputs</h2>
            <p>Surfaces recommendations, risk signals, and opportunity areas for business review meetings.</p>
          </article>
        </section>
      ) : null}

      {analysis ? (
        <section className="results">
          <div className="utility-row">
            <div className="panel schema-panel">
              <div className="panel-header">
                <h2>Dataset Profile</h2>
                <span>{analysis.filename} - {analysis.row_count} rows</span>
              </div>
              <div className="chip-group">
                <div className="schema-chip"><span>Primary metric</span><strong>{analysis.schema.inferred_primary_metric || "None"}</strong></div>
                <div className="schema-chip"><span>Primary dimension</span><strong>{analysis.schema.inferred_primary_dimension || "None"}</strong></div>
                <div className="schema-chip"><span>Secondary dimension</span><strong>{analysis.schema.inferred_secondary_dimension || "None"}</strong></div>
                <div className="schema-chip"><span>Time column</span><strong>{analysis.schema.inferred_time_column || "None"}</strong></div>
              </div>
              <div className="quality-grid">
                <div className="quality-card"><span>Completeness</span><strong>{analysis.data_quality.completeness_pct}%</strong></div>
                <div className="quality-card"><span>Missing cells</span><strong>{analysis.data_quality.missing_cells}</strong></div>
                <div className="quality-card"><span>Duplicate rows</span><strong>{analysis.data_quality.duplicate_rows}</strong></div>
                <div className="quality-card"><span>Duplicate columns</span><strong>{analysis.data_quality.duplicate_columns}</strong></div>
              </div>
            </div>

            <div className="panel mapping-panel">
              <div className="panel-header">
                <h2>Manual Mapping</h2>
                <button type="button" className="secondary-button" onClick={exportReport}>Export PDF</button>
              </div>
              <form className="mapping-form" onSubmit={submitMapping}>
                <label>
                  Primary metric
                  <select value={mapping.primary_metric} onChange={(event) => setMapping((current) => ({ ...current, primary_metric: event.target.value }))}>
                    {buildOptions(analysis.schema.numeric_columns)}
                  </select>
                </label>
                <label>
                  Primary dimension
                  <select value={mapping.primary_dimension} onChange={(event) => setMapping((current) => ({ ...current, primary_dimension: event.target.value }))}>
                    {buildOptions(analysis.schema.categorical_columns, true)}
                  </select>
                </label>
                <label>
                  Secondary dimension
                  <select value={mapping.secondary_dimension} onChange={(event) => setMapping((current) => ({ ...current, secondary_dimension: event.target.value }))}>
                    {buildOptions(analysis.schema.categorical_columns, true)}
                  </select>
                </label>
                <label>
                  Time column
                  <select value={mapping.time_column} onChange={(event) => setMapping((current) => ({ ...current, time_column: event.target.value }))}>
                    {buildOptions(analysis.schema.columns, true)}
                  </select>
                </label>
                <button type="submit">Re-run with Mapping</button>
              </form>
            </div>
          </div>

          <div className="kpi-grid">
            {analysis.kpis.map((kpi) => (
              <article key={kpi.label} className="kpi-card">
                <p>{kpi.label}</p>
                <strong>{kpi.value}</strong>
                <span>{kpi.delta || ""}</span>
              </article>
            ))}
          </div>

          <div className="panel">
            <div className="panel-header">
              <h2>Executive Summary</h2>
              <span>{analysis.metrics.has_time_dimension ? "Monthly trend-aware analysis" : "Snapshot analysis"}</span>
            </div>
            <p>{analysis.insights.executive_summary}</p>
          </div>

          <div className="utility-row">
            <div className="panel">
              <h2>Chart-to-Text Explanation</h2>
              <ul>
                {analysis.insights.chart_explanations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="panel">
              <h2>Trend Narrative</h2>
              <div className="narrative-card">
                {analysis.metrics.has_time_dimension
                  ? `The current report uses ${analysis.metrics.primary_metric} as the main measure and tracks how it changes over time so analysts can explain trend direction, turning points, and unusual shifts.`
                  : "No reliable time column was inferred, so this report focuses on segment comparison, metric distribution, and structural patterns instead of month-over-month trends."}
              </div>
            </div>
          </div>

          <div className="chart-grid">
            {analysis.charts.map((chart, index) => (
              <ChartCard key={`${chart.title}-${index}`} chart={chart} index={index} />
            ))}
          </div>

          <div className="insight-grid">
            <ListPanel title="Recommended Action Points" items={analysis.insights.recommendations} />
            <ListPanel title="Risk Insights" items={analysis.insights.risks} />
            <ListPanel title="Opportunity Areas" items={analysis.insights.opportunities} />
          </div>

          <div className="utility-row">
            <div className="panel">
              <h2>Anomaly Commentary</h2>
              <div className="anomaly-list">
                {analysis.anomalies.length === 0 ? (
                  <p>No major anomalies detected.</p>
                ) : (
                  analysis.anomalies.map((anomaly) => (
                    <article key={`${anomaly.metric}-${anomaly.period}-${anomaly.value}`} className="anomaly-card">
                      <strong>{anomaly.metric} - {anomaly.period}</strong>
                      <p>{anomaly.explanation}</p>
                      <span>{anomaly.severity.toUpperCase()} | {anomaly.value}</span>
                    </article>
                  ))
                )}
              </div>
            </div>

            <div className="panel chat-panel">
              <h2>Report Assistant</h2>
              <form className="chat-form" onSubmit={submitChat}>
                <textarea
                  value={question}
                  placeholder="Ask a question like: What is driving this month's performance trend?"
                  onChange={(event) => setQuestion(event.target.value)}
                  required
                />
                <button type="submit">Ask Assistant</button>
              </form>
              <div className="chat-response">{chatAnswer}</div>
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}
