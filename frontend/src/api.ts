export type BackendStatus = "checking" | "online" | "offline";
export type DatabaseStatus =
  | "checking"
  | "ready"
  | "not-ready"
  | "unavailable";

export interface SystemStatus {
  backend: BackendStatus;
  database: DatabaseStatus;
}

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || "/api";
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

async function checkBackend(signal: AbortSignal): Promise<BackendStatus> {
  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return "offline";
    }

    const body: unknown = await response.json();
    return isRecord(body) && body.status === "ok" ? "online" : "offline";
  } catch {
    return "offline";
  }
}

async function checkDatabase(signal: AbortSignal): Promise<DatabaseStatus> {
  try {
    const response = await fetch(`${apiBaseUrl}/ready`, {
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const body: unknown = await response.json();

    if (
      response.ok &&
      isRecord(body) &&
      body.status === "ready" &&
      isRecord(body.checks) &&
      body.checks.postgres === "up"
    ) {
      return "ready";
    }

    if (response.status === 503) {
      return "not-ready";
    }

    return "unavailable";
  } catch {
    return "unavailable";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export async function fetchSystemStatus(
  signal: AbortSignal,
): Promise<SystemStatus> {
  const [backend, database] = await Promise.all([
    checkBackend(signal),
    checkDatabase(signal),
  ]);

  return { backend, database };
}

