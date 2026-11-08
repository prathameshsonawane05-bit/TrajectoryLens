import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FAILURE_TYPES, findingLabel } from "../failureTypes";
import { useRunCatalog } from "../useRunCatalog";

export default function RunsPage() {
  const catalog = useRunCatalog();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"all" | "pass" | "fail">("all");
  const [model, setModel] = useState("all");
  const [failureType, setFailureType] = useState("all");

  const rows = catalog.kind === "ready" ? catalog.rows : [];
  const models = useMemo(() => {
    return [...new Set(rows.map((row) => row.run.model))].sort();
  }, [rows]);
  const failureOptions = useMemo(() => {
    const seen = new Set<string>(FAILURE_TYPES);
    for (const row of rows) {
      for (const finding of row.findings) {
        seen.add(finding.type);
      }
    }
    return [...seen];
  }, [rows]);

  const shown = rows.filter((row) => {
    if (status !== "all" && row.run.final_status !== status) {
      return false;
    }
    if (model !== "all" && row.run.model !== model) {
      return false;
    }
    if (failureType !== "all" && !row.findings.some((finding) => finding.type === failureType)) {
      return false;
    }
    return true;
  });

  return (
    <main className="page">
      <h1>Runs</h1>
      <p className="lede">Trajectories stored in TrajectoryLens, newest first.</p>
      <form className="filters">
        <label>
          Status
          <select
            value={status}
            onChange={(event) => {
              const value = event.target.value;
              setStatus(value === "pass" || value === "fail" ? value : "all");
            }}
          >
            <option value="all">All</option>
            <option value="pass">Pass</option>
            <option value="fail">Fail</option>
          </select>
        </label>
        <label>
          Model
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            <option value="all">All</option>
            {models.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Failure type
          <select value={failureType} onChange={(event) => setFailureType(event.target.value)}>
            <option value="all">All</option>
            {failureOptions.map((item) => (
              <option key={item} value={item}>
                {findingLabel(item)}
              </option>
            ))}
          </select>
        </label>
      </form>

      {catalog.kind === "loading" ? <p>Loading runs…</p> : null}
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
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Model</th>
                <th>Task</th>
                <th>Status</th>
                <th>Findings</th>
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 ? (
                <tr>
                  <td colSpan={5} className="empty">
                    No runs match these filters.
                  </td>
                </tr>
              ) : (
                shown.map((row) => (
                  <tr
                    key={row.run.run_id}
                    className="click-row"
                    onClick={() => navigate(`/runs/${encodeURIComponent(row.run.run_id)}`)}
                  >
                    <td>
                      <Link to={`/runs/${encodeURIComponent(row.run.run_id)}`}>{row.run.run_id}</Link>
                    </td>
                    <td>{row.run.model}</td>
                    <td>{row.run.task_id}</td>
                    <td>
                      <span className={`badge status-${row.run.final_status}`}>{row.run.final_status}</span>
                    </td>
                    <td>{row.findings.length}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </main>
  );
}
