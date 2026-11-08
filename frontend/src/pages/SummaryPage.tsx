import { useMemo } from "react";
import { Link } from "react-router-dom";
import { BarChart, ModelChart, type ModelBar } from "../components/Charts";
import { FAILURE_TYPES, findingColor, findingLabel } from "../failureTypes";
import { useRunCatalog } from "../useRunCatalog";

export default function SummaryPage() {
  const catalog = useRunCatalog();
  const rows = catalog.kind === "ready" ? catalog.rows : [];

  const summary = useMemo(() => {
    const typeCounts = new Map<string, number>();
    for (const type of FAILURE_TYPES) {
      typeCounts.set(type, 0);
    }
    const modelCounts = new Map<string, Map<string, number>>();
    for (const row of rows) {
      const byType = modelCounts.get(row.run.model) ?? new Map<string, number>();
      modelCounts.set(row.run.model, byType);
      for (const finding of row.findings) {
        typeCounts.set(finding.type, (typeCounts.get(finding.type) ?? 0) + 1);
        byType.set(finding.type, (byType.get(finding.type) ?? 0) + 1);
      }
    }
    const typeRows = [...typeCounts.entries()]
      .map(([type, value]) => ({
        label: findingLabel(type),
        value,
        color: findingColor(type),
      }))
      .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label));
    const modelRows: ModelBar[] = [...modelCounts.entries()]
      .map(([model, counts]) => ({
        model,
        counts: [...counts.entries()]
          .map(([type, count]) => ({ type, count }))
          .sort((left, right) => right.count - left.count || left.type.localeCompare(right.type)),
      }))
      .sort((left, right) => left.model.localeCompare(right.model));
    const ranked = typeRows.filter((row) => row.value > 0);
    const total = typeRows.reduce((sum, row) => sum + row.value, 0);
    return { typeRows, modelRows, ranked, total };
  }, [rows]);

  return (
    <main className="page">
      <h1>Summary</h1>
      <p className="lede">Finding counts across the stored runs.</p>
      {catalog.kind === "loading" ? <p>Loading summary…</p> : null}
      {catalog.kind === "error" ? (
        <p className="error" role="alert">
          {catalog.message}
        </p>
      ) : null}
      {catalog.kind === "ready" && rows.length === 0 ? (
        <p className="empty">
          No runs yet. <Link to="/upload">Upload a trajectory</Link>.
        </p>
      ) : null}
      {catalog.kind === "ready" && rows.length > 0 ? (
        <>
          {summary.total === 0 ? (
            <p className="empty">No findings yet. Open a run and choose Re-run analysis.</p>
          ) : null}
          <BarChart title="Findings by type" rows={summary.typeRows} />
          <ModelChart rows={summary.modelRows} />
          <section className="ranking">
            <h2>Most common failure types</h2>
            {summary.ranked.length === 0 ? <p className="empty">None yet.</p> : null}
            {summary.ranked.length > 0 ? (
              <ol>
                {summary.ranked.map((row) => (
                  <li key={row.label}>
                    <span className="swatch" style={{ background: row.color }} />
                    {row.label}
                    <strong>{row.value}</strong>
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
