import { useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, createRun, errorMessage, parseTrajectoryText, type Run } from "../api";

type UploadState =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "error"; message: string; issues: string[] }
  | { kind: "done"; run: Run };

export default function UploadPage() {
  const [state, setState] = useState<UploadState>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);

  async function uploadText(text: string): Promise<void> {
    setState({ kind: "uploading" });
    try {
      const body = parseTrajectoryText(text);
      const run = await createRun(body);
      setState({ kind: "done", run });
    } catch (error: unknown) {
      const issues = error instanceof ApiError ? error.issues : [];
      setState({ kind: "error", message: errorMessage(error), issues });
    }
  }

  async function uploadFile(file: File): Promise<void> {
    const text = await file.text();
    await uploadText(text);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file !== undefined) {
      void uploadFile(file);
    }
  }

  return (
    <main className="page">
      <h1>Upload</h1>
      <p className="lede">
        Add one trajectory JSON file. <code>expected_findings</code> is a local label and is left out of the
        upload.
      </p>
      <label
        className={dragging ? "dropzone dragging" : "dropzone"}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          type="file"
          accept="application/json,.json"
          disabled={state.kind === "uploading"}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file !== undefined) {
              void uploadFile(file);
            }
            event.target.value = "";
          }}
        />
        {state.kind === "uploading" ? "Uploading…" : "Drop a JSON file here, or choose one."}
      </label>
      {state.kind === "error" ? (
        <div className="error" role="alert">
          <p>{state.message}</p>
          {state.issues.length > 1 ? (
            <ul>
              {state.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {state.kind === "done" ? (
        <p className="success">
          Stored <Link to={`/runs/${encodeURIComponent(state.run.run_id)}`}>{state.run.run_id}</Link>.
        </p>
      ) : null}
    </main>
  );
}
