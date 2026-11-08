import { useEffect, useState } from "react";
import { errorMessage, fetchAllRuns, fetchFindings, type Finding, type RunSummary } from "./api";

export interface RunRow {
  run: RunSummary;
  findings: Finding[];
}

type CatalogState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; rows: RunRow[] };

export function useRunCatalog(): CatalogState {
  const [state, setState] = useState<CatalogState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchAllRuns()
      .then(async (runs) => {
        const findings = await Promise.all(runs.map((run) => fetchFindings(run.run_id)));
        if (cancelled) {
          return;
        }
        setState({
          kind: "ready",
          rows: runs.map((run, index) => ({ run, findings: findings[index] ?? [] })),
        });
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

  return state;
}
