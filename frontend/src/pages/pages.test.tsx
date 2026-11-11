import { StrictMode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const messageStep = {
  index: 0,
  type: "message",
  content: "hello",
  file: null,
  output: "",
  exit_code: null,
  tests_passed: null,
  tests_failed: null,
  error_signature: null,
};

const finding = {
  type: "symptom_fix",
  step_index: 0,
  severity: "medium",
  explanation: "The same error remained.",
};

function demoRun(finalStatus: "pass" | "fail" = "fail", runId = "demo-1") {
  return {
    run_id: runId,
    task_id: "cache lookup",
    model: "lumen-lite",
    final_status: finalStatus,
    agent_claimed_success: false,
    created_at: "2026-01-01T00:00:00Z",
    steps: [messageStep],
  };
}

function summaryOf(run: ReturnType<typeof demoRun>) {
  return {
    run_id: run.run_id,
    task_id: run.task_id,
    model: run.model,
    final_status: run.final_status,
    agent_claimed_success: run.agent_claimed_success,
    created_at: run.created_at,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
}

function installFetch(
  handle: (url: string, init: RequestInit | undefined) => Response,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    return Promise.resolve(handle(requestUrl(input), init));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  return render(
    <StrictMode>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </BrowserRouter>
    </StrictMode>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("pages", () => {
  it("shows an alert when the chosen file is not JSON", async () => {
    installFetch((url) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    const user = userEvent.setup();
    renderAt("/upload");
    const input = screen.getByLabelText(/choose one/i);
    await user.upload(input, new File(["{"], "bad.json", { type: "application/json" }));
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "The file is not valid JSON.",
    );
  });

  it("posts one trajectory without expected_findings and links to the run", async () => {
    const stored = demoRun();
    const fetchMock = installFetch((url, init) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url === "/runs" && init?.method === "POST") {
        return jsonResponse(201, stored);
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    const user = userEvent.setup();
    renderAt("/upload");
    const file = new File(
      [
        JSON.stringify({
          ...stored,
          expected_findings: ["symptom_fix"],
        }),
      ],
      "demo-1.json",
      { type: "application/json" },
    );
    await user.upload(screen.getByLabelText(/choose one/i), file);
    const link = await screen.findByRole("link", { name: "demo-1" });
    expect(link.getAttribute("href")).toBe("/runs/demo-1");
    const post = fetchMock.mock.calls.find((call) => {
      const init = call[1] as RequestInit | undefined;
      return requestUrl(call[0] as RequestInfo | URL) === "/runs" && init?.method === "POST";
    });
    const raw = (post?.[1] as RequestInit | undefined)?.body;
    expect(typeof raw).toBe("string");
    expect(String(raw).includes("expected_findings")).toBe(false);
    expect(JSON.parse(String(raw))).toMatchObject({
      run_id: "demo-1",
      task_id: "cache lookup",
    });
  });

  it("shows the existing-run message when the upload conflicts", async () => {
    installFetch((url, init) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url === "/runs" && init?.method === "POST") {
        return jsonResponse(409, { detail: "run_id already exists" });
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    const user = userEvent.setup();
    renderAt("/upload");
    await user.upload(
      screen.getByLabelText(/choose one/i),
      new File([JSON.stringify(demoRun())], "demo-1.json", { type: "application/json" }),
    );
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "run_id already exists");
  });

  it("shows the stored run, its status, and its finding count", async () => {
    const run = demoRun();
    installFetch((url) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url.startsWith("/runs?")) {
        return jsonResponse(200, {
          items: [summaryOf(run)],
          total: 1,
          limit: 100,
          offset: 0,
        });
      }
      if (url === "/runs/demo-1/findings") {
        return jsonResponse(200, [finding]);
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    renderAt("/");
    const row = (await screen.findByRole("link", { name: "demo-1" })).closest("tr");
    expect(row?.textContent).toContain("demo-1");
    expect(row?.textContent).toContain("fail");
    expect(row?.textContent).toContain("1");
  });

  it("shows a database error and no table when the run list fails", async () => {
    installFetch((url) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url.startsWith("/runs?")) {
        return jsonResponse(500, { detail: "database unavailable" });
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    renderAt("/");
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "database unavailable");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("shows an empty state that links to upload", async () => {
    installFetch((url) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url.startsWith("/runs?")) {
        return jsonResponse(200, { items: [], total: 0, limit: 100, offset: 0 });
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    renderAt("/");
    const empty = await screen.findByText(/No runs yet\./);
    expect(empty.textContent).toContain("No runs yet.");
    const link = screen.getByRole("link", { name: "Upload a trajectory" });
    expect(link.getAttribute("href")).toBe("/upload");
  });

  it("filters the table to failed runs", async () => {
    const failed = demoRun("fail", "demo-1");
    const passed = demoRun("pass", "demo-pass");
    installFetch((url) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url.startsWith("/runs?")) {
        return jsonResponse(200, {
          items: [summaryOf(failed), summaryOf(passed)],
          total: 2,
          limit: 100,
          offset: 0,
        });
      }
      if (url === "/runs/demo-1/findings") {
        return jsonResponse(200, [finding]);
      }
      if (url === "/runs/demo-pass/findings") {
        return jsonResponse(200, []);
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    const user = userEvent.setup();
    renderAt("/");
    await screen.findByRole("link", { name: "demo-pass" });
    await user.selectOptions(screen.getByRole("combobox", { name: /^Status/ }), "fail");
    expect(screen.getByRole("link", { name: "demo-1" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "demo-pass" })).toBeNull();
  });

  it("opens the run and shows the finding on its step", async () => {
    const run = demoRun();
    installFetch((url) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url.startsWith("/runs?")) {
        return jsonResponse(200, {
          items: [summaryOf(run)],
          total: 1,
          limit: 100,
          offset: 0,
        });
      }
      if (url === "/runs/demo-1/findings") {
        return jsonResponse(200, [finding]);
      }
      if (url === "/runs/demo-1") {
        return jsonResponse(200, run);
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    const user = userEvent.setup();
    renderAt("/");
    await user.click(await screen.findByRole("link", { name: "demo-1" }));
    expect(await screen.findByRole("heading", { name: "demo-1" })).toBeTruthy();
    const step = document.querySelector(".has-finding");
    expect(step?.classList.contains("has-finding")).toBe(true);
    expect(step?.textContent).toContain("Symptom fix");
  });

  it("shows an alert when the run is missing", async () => {
    installFetch((url) => {
      if (url === "/health") {
        return jsonResponse(200, { status: "ok" });
      }
      if (url === "/runs/demo-1" || url === "/runs/demo-1/findings") {
        return jsonResponse(404, { detail: "run not found" });
      }
      return jsonResponse(500, { detail: "unexpected request" });
    });
    renderAt("/runs/demo-1");
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "run not found");
  });
});
