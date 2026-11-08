import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  analyzeRun,
  errorMessage,
  fetchFindings,
  fetchRun,
  type Finding,
  type Run,
  type Step,
} from "../api";
import { findingLabel } from "../failureTypes";

type DetailState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      run: Run;
      findings: Finding[];
      analyzing: boolean;
      analyzeError: string | null;
    };

function findingsFor(findings: Finding[], step: Step): Finding[] {
  return findings.filter((finding) => finding.step_index === step.index);
}

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [state, setState] = useState<DetailState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    Promise.all([fetchRun(runId), fetchFindings(runId)])
      .then(([run, findings]) => {
        if (!cancelled) {
          setState({ kind: "ready", run, findings, analyzing: false, analyzeError: null });
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
  }, [runId]);

  async function rerun(): Promise<void> {
    if (state.kind !== "ready" || state.analyzing) {
      return;
    }
    setState({ ...state, analyzing: true, analyzeError: null });
    try {
      const findings = await analyzeRun(runId);
      setState({ kind: "ready", run: state.run, findings, analyzing: false, analyzeError: null });
    } catch (error: unknown) {
      setState({
        kind: "ready",
        run: state.run,
        findings: state.findings,
        analyzing: false,
        analyzeError: errorMessage(error),
      });
    }
  }

  return (
    <main className="page">
      <p className="back">
        <Link to="/">All runs</Link>
      </p>
      {state.kind === "loading" ? <p>Loading run…</p> : null}
      {state.kind === "error" ? (
        <p className="error" role="alert">
          {state.message}
        </p>
      ) : null}
      {state.kind === "ready" ? (
        <>
          <header className="detail-head">
            <div>
              <h1>{state.run.run_id}</h1>
              <p className="lede">{state.run.task_id}</p>
              <p className="meta">
                <span className={`badge status-${state.run.final_status}`}>{state.run.final_status}</span>
                <span>{state.run.model}</span>
                <span>{state.run.agent_claimed_success ? "Claimed success" : "Did not claim success"}</span>
              </p>
            </div>
            <button type="button" onClick={() => void rerun()} disabled={state.analyzing}>
              {state.analyzing ? "Running analysis…" : "Re-run analysis"}
            </button>
          </header>
          {state.analyzeError !== null ? (
            <p className="error" role="alert">
              {state.analyzeError}
            </p>
          ) : null}
          <ol className="timeline">
            {state.run.steps.map((step) => {
              const stepFindings = findingsFor(state.findings, step);
              return (
                <li
                  key={step.index}
                  className={stepFindings.length > 0 ? "step has-finding" : "step"}
                  data-type={step.type}
                >
                  <div className="step-head">
                    <span className="step-index">{step.index}</span>
                    <span className={`badge type-${step.type}`}>{step.type.replaceAll("_", " ")}</span>
                    {step.file !== null ? <code>{step.file}</code> : null}
                    {step.exit_code !== null ? <span>exit {step.exit_code}</span> : null}
                    {step.tests_failed !== null ? (
                      <span>
                        {step.tests_passed ?? 0} passed, {step.tests_failed} failed
                      </span>
                    ) : null}
                  </div>
                  {step.content.length > 0 ? <p className="step-content">{step.content}</p> : null}
                  {stepFindings.map((finding) => (
                    <p key={`${finding.type}-${finding.step_index}-${finding.explanation}`} className="finding">
                      <span className={`badge severity-${finding.severity}`}>{findingLabel(finding.type)}</span>
                      {finding.explanation}
                    </p>
                  ))}
                  <details>
                    <summary>{step.output.length > 0 ? "Output" : "No output"}</summary>
                    <pre>{step.output.length > 0 ? step.output : ""}</pre>
                  </details>
                </li>
              );
            })}
          </ol>
        </>
      ) : null}
    </main>
  );
}
