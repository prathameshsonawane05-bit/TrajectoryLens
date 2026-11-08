import { useEffect, useState } from "react";
import { fetchHealth } from "./api";
import "./App.css";

type HealthState =
  | { kind: "loading" }
  | { kind: "ready"; status: string }
  | { kind: "error"; message: string };

export default function App() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((result) => {
        if (!cancelled) {
          setHealth({ kind: "ready", status: result.status });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unknown error";
          setHealth({ kind: "error", message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="page">
      <h1>TrajectoryLens</h1>
      <p className="lede">Backend health</p>
      {health.kind === "loading" ? <p>Checking backend…</p> : null}
      {health.kind === "error" ? (
        <p className="error" role="alert">
          {health.message}
        </p>
      ) : null}
      {health.kind === "ready" ? (
        <p className="status">
          status: <strong>{health.status}</strong>
        </p>
      ) : null}
    </main>
  );
}
