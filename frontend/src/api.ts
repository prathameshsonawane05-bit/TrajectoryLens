export interface HealthResponse {
  status: string;
}

export interface Step {
  index: number;
  type: "command" | "edit" | "test_run" | "message";
  content: string;
  file: string | null;
  output: string;
  exit_code: number | null;
  tests_passed: number | null;
  tests_failed: number | null;
  error_signature: string | null;
}

export interface RunSummary {
  run_id: string;
  task_id: string;
  model: string;
  final_status: "pass" | "fail";
  agent_claimed_success: boolean;
  created_at: string;
}

export interface Run extends RunSummary {
  steps: Step[];
}

export interface RunListResponse {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface Finding {
  type: string;
  step_index: number;
  severity: "low" | "medium" | "high";
  explanation: string;
}

export interface TypeCount {
  type: string;
  count: number;
}

export interface ModelCount {
  model: string;
  count: number;
}

export interface Summary {
  pass_count: number;
  fail_count: number;
  by_type: TypeCount[];
  by_model: ModelCount[];
  top_failure_types: TypeCount[];
}

export class ApiError extends Error {
  readonly status: number;
  readonly issues: string[];

  constructor(status: number, message: string, issues: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.issues = issues;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === "number";
}

function isHealthResponse(value: unknown): value is HealthResponse {
  return isRecord(value) && typeof value.status === "string";
}

function isStep(value: unknown): value is Step {
  if (!isRecord(value)) {
    return false;
  }
  const stepType = value.type;
  return (
    typeof value.index === "number" &&
    (stepType === "command" ||
      stepType === "edit" ||
      stepType === "test_run" ||
      stepType === "message") &&
    typeof value.content === "string" &&
    isNullableString(value.file) &&
    typeof value.output === "string" &&
    isNullableNumber(value.exit_code) &&
    isNullableNumber(value.tests_passed) &&
    isNullableNumber(value.tests_failed) &&
    isNullableString(value.error_signature)
  );
}

function isStatus(value: unknown): value is RunSummary["final_status"] {
  return value === "pass" || value === "fail";
}

function isRunSummary(value: unknown): value is RunSummary {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.task_id === "string" &&
    typeof value.model === "string" &&
    isStatus(value.final_status) &&
    typeof value.agent_claimed_success === "boolean" &&
    typeof value.created_at === "string"
  );
}

function isRun(value: unknown): value is Run {
  return (
    isRunSummary(value) &&
    "steps" in value &&
    Array.isArray(value.steps) &&
    value.steps.every(isStep)
  );
}

function isRunList(value: unknown): value is RunListResponse {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isRunSummary) &&
    typeof value.total === "number" &&
    typeof value.limit === "number" &&
    typeof value.offset === "number"
  );
}

function isSeverity(value: unknown): value is Finding["severity"] {
  return value === "low" || value === "medium" || value === "high";
}

function isFinding(value: unknown): value is Finding {
  return (
    isRecord(value) &&
    typeof value.type === "string" &&
    typeof value.step_index === "number" &&
    isSeverity(value.severity) &&
    typeof value.explanation === "string"
  );
}

function formatLoc(loc: unknown[]): string {
  let text = "";
  for (const part of loc) {
    if (part === "body") {
      continue;
    }
    if (typeof part === "number") {
      text += `[${part}]`;
    } else if (typeof part === "string") {
      text = text.length > 0 ? `${text}.${part}` : part;
    }
  }
  return text;
}

function issueText(value: unknown): string | null {
  if (!isRecord(value) || typeof value.msg !== "string") {
    return null;
  }
  const loc = Array.isArray(value.loc) ? formatLoc(value.loc) : "";
  return loc.length > 0 ? `${loc}: ${value.msg}` : value.msg;
}

async function readError(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  if (isRecord(body) && typeof body.detail === "string") {
    return new ApiError(response.status, body.detail);
  }
  if (isRecord(body) && Array.isArray(body.detail)) {
    const issues = body.detail.map(issueText).filter((item): item is string => item !== null);
    const message = issues[0] ?? "The trajectory was rejected";
    return new ApiError(response.status, message, issues);
  }
  return new ApiError(response.status, `Request failed (${response.status})`);
}

async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw await readError(response);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json() as Promise<unknown>;
}

function isTypeCount(value: unknown): value is TypeCount {
  return isRecord(value) && typeof value.type === "string" && typeof value.count === "number";
}

function isModelCount(value: unknown): value is ModelCount {
  return isRecord(value) && typeof value.model === "string" && typeof value.count === "number";
}

function isSummary(value: unknown): value is Summary {
  return (
    isRecord(value) &&
    typeof value.pass_count === "number" &&
    typeof value.fail_count === "number" &&
    Array.isArray(value.by_type) &&
    value.by_type.every(isTypeCount) &&
    Array.isArray(value.by_model) &&
    value.by_model.every(isModelCount) &&
    Array.isArray(value.top_failure_types) &&
    value.top_failure_types.every(isTypeCount)
  );
}

export async function fetchHealth(): Promise<HealthResponse> {
  const body = await requestJson("/health");
  if (!isHealthResponse(body)) {
    throw new Error("Health check returned an unexpected payload");
  }
  return body;
}

export async function fetchSummary(): Promise<Summary> {
  const body = await requestJson("/summary");
  if (!isSummary(body)) {
    throw new Error("Summary returned an unexpected payload");
  }
  return body;
}

export async function fetchRuns(limit: number, offset: number): Promise<RunListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const body = await requestJson(`/runs?${params.toString()}`);
  if (!isRunList(body)) {
    throw new Error("Run list returned an unexpected payload");
  }
  return body;
}

export async function fetchAllRuns(): Promise<RunSummary[]> {
  const pageSize = 100;
  const first = await fetchRuns(pageSize, 0);
  const items = [...first.items];
  let offset = items.length;
  while (offset < first.total) {
    const page = await fetchRuns(pageSize, offset);
    if (page.items.length === 0) {
      break;
    }
    items.push(...page.items);
    offset += page.items.length;
  }
  return items;
}

export async function fetchRun(runId: string): Promise<Run> {
  const body = await requestJson(`/runs/${encodeURIComponent(runId)}`);
  if (!isRun(body)) {
    throw new Error("Run returned an unexpected payload");
  }
  return body;
}

export async function fetchFindings(runId: string): Promise<Finding[]> {
  const body = await requestJson(`/runs/${encodeURIComponent(runId)}/findings`);
  if (!Array.isArray(body) || !body.every(isFinding)) {
    throw new Error("Findings returned an unexpected payload");
  }
  return body;
}

export async function analyzeRun(runId: string): Promise<Finding[]> {
  const body = await requestJson(`/runs/${encodeURIComponent(runId)}/analyze`, {
    method: "POST",
  });
  if (!Array.isArray(body) || !body.every(isFinding)) {
    throw new Error("Analysis returned an unexpected payload");
  }
  return body;
}

export function parseTrajectoryText(text: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    throw new Error("The file is not valid JSON.");
  }
  if (Array.isArray(parsed)) {
    throw new Error("Upload one trajectory object. This file is a list of runs.");
  }
  if (!isRecord(parsed)) {
    throw new Error("A trajectory must be a JSON object.");
  }
  const body = { ...parsed };
  delete body.expected_findings;
  return body;
}

export async function createRun(body: Record<string, unknown>): Promise<Run> {
  const response = await requestJson("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!isRun(response)) {
    throw new Error("Upload returned an unexpected payload");
  }
  return response;
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong";
}
