import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage, fetchSummary, type Summary } from "../api";
import { BarChart } from "../components/Charts";
import { findingColor, findingLabel } from "../failureTypes";

type SummaryState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; summary: Summary };

export default function SummaryPage() {
  const [state, setState] = useState<SummaryState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchSummary()
      .then((summary) => {
        if (!cancelled) {
          setState({ kind: "ready", summary });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ kind: "error", message: errorMessage(error) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const summary = state.kind === "ready" ? state.summary : null;
  const runCount = summary === null ? 0 : summary.pass_count + summary.fail_count;

  return (
    <main className="page">
      <h1>Summary</h1>
      <p className="lede">Finding counts across the stored runs. Model names are labels only.</p>
      {state.kind === "loading" ? <p>Loading summary…</p> : null}
      {state.kind === "error" ? (
        <p className="error" role="alert">
          {state.message}
        </p>
      ) : null}
      {summary !== null && runCount === 0 ? (
        <p className="empty">
          No runs yet. <Link to="/upload">Upload a trajectory</Link>.
        </p>
      ) : null}
      {summary !== null && runCount > 0 ? (
        <>
          <p className="meta">
            <span className="badge status-pass">{summary.pass_count} passed</span>
            <span className="badge status-fail">{summary.fail_count} failed</span>
          </p>
          {summary.by_type.length === 0 ? (
            <p className="empty">No findings yet. Open a run and choose Re-run analysis.</p>
          ) : null}
          <BarChart
            title="Findings by type"
            rows={summary.by_type.map((row) => ({
              label: findingLabel(row.type),
              value: row.count,
              color: findingColor(row.type),
            }))}
          />
          <BarChart
            title="Findings by model"
            rows={summary.by_model.map((row) => ({
              label: row.model,
              value: row.count,
              color: "#1d4ed8",
            }))}
          />
          <section className="ranking">
            <h2>Most common failure types</h2>
            {summary.top_failure_types.length === 0 ? <p className="empty">None yet.</p> : null}
            {summary.top_failure_types.length > 0 ? (
              <ol>
                {summary.top_failure_types.map((row) => (
                  <li key={row.type}>
                    <span className="swatch" style={{ background: findingColor(row.type) }} />
                    {findingLabel(row.type)}
                    <strong>{row.count}</strong>
                  </li>
                ))}
              </ol>
            ) : null}
          </section>
        </>
      ) : null}
    </main>
  );
}
