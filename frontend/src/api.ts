export interface HealthResponse {
  status: string;
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null || !("status" in value)) {
    return false;
  }
  return typeof value.status === "string";
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch("/health");
  if (!response.ok) {
    throw new Error(`Health check failed (${response.status})`);
  }
  const body: unknown = await response.json();
  if (!isHealthResponse(body)) {
    throw new Error("Health check returned an unexpected payload");
  }
  return body;
}
