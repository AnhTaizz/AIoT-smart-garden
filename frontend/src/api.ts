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

export type RelayState = "on" | "off";
export type DeviceMode = "MANUAL" | "AUTO";
export type CommandAction = "pump_on" | "pump_off";
export type CommandStatus = "pending" | "applied" | "rejected" | "timeout";
export type AckStatus = "accepted" | "rejected" | "applied";

export interface SensorStatusMap {
  aht20?: "ok" | "error";
  soil?: "ok" | "error";
  [key: string]: string | undefined;
}

export interface TelemetryData {
  id: number;
  device_id: string;
  boot_id: string;
  sequence: number;
  clock_synced: boolean;
  measured_at: string | null;
  received_at: string;
  uptime_ms: number;
  temperature_c: number | null;
  air_humidity_pct: number | null;
  soil_moisture_pct: number | null;
  sensor_status: SensorStatusMap;
  simulated: boolean;
  payload_schema: string;
  stale: boolean;
  stale_after_seconds: number;
}

export interface TelemetryHistoryResponse {
  device_id: string;
  count: number;
  order: "asc" | "desc";
  items: TelemetryData[];
}

export interface DeviceStateData {
  device_id: string;
  boot_id: string;
  state_sequence: number;
  mode: DeviceMode;
  relay_state: RelayState;
  last_command_id: string | null;
  last_command_sequence: number | null;
  clock_synced: boolean;
  reported_at: string | null;
  received_at: string;
  stale: boolean;
  stale_after_seconds: number;
}

export interface CommandOut {
  command_id: string;
  device_id: string;
  command_sequence: number;
  action: CommandAction;
  params: { duration_seconds?: number };
  target_boot_id: string | null;
  status: CommandStatus;
  device_ack: AckStatus | null;
  reason: string | null;
  created_at: string;
  expires_at: string;
  published_at: string | null;
  acked_at: string | null;
  ack_boot_id: string | null;
  state_confirmed_at: string | null;
  confirmed_relay_state: RelayState | null;
  confirmed_state_sequence: number | null;
  confirmed_boot_id: string | null;
  finalized_at: string | null;
  late_ack: AckStatus | null;
  late_ack_at: string | null;
}

export interface CommandListResponse {
  device_id: string;
  count: number;
  items: CommandOut[];
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  fields?: string[];
  limit_seconds?: number;
  command_id?: string;
}

export class ApiError extends Error {
  code: string;
  status: number;
  fields?: string[];
  limitSeconds?: number;

  constructor(status: number, detail: ApiErrorDetail) {
    super(detail.message || detail.code);
    this.name = "ApiError";
    this.status = status;
    this.code = detail.code;
    this.fields = detail.fields;
    this.limitSeconds = detail.limit_seconds;
  }
}

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || "/api";
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }

  let detail: ApiErrorDetail = {
    code: `http_${response.status}`,
    message: `Yêu cầu thất bại với mã HTTP ${response.status}`,
  };

  try {
    const body: unknown = await response.json();
    if (isRecord(body) && isRecord(body.detail)) {
      detail = body.detail as unknown as ApiErrorDetail;
    }
  } catch {
    // Non-JSON response, keep generic error
  }

  throw new ApiError(response.status, detail);
}

export async function fetchSystemStatus(
  signal?: AbortSignal,
): Promise<SystemStatus> {
  const [backend, database] = await Promise.all([
    checkBackend(signal),
    checkDatabase(signal),
  ]);

  return { backend, database };
}

async function checkBackend(signal?: AbortSignal): Promise<BackendStatus> {
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

async function checkDatabase(signal?: AbortSignal): Promise<DatabaseStatus> {
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

export async function fetchLatestTelemetry(
  deviceId: string,
  signal?: AbortSignal,
): Promise<TelemetryData | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/devices/${encodeURIComponent(deviceId)}/latest`, {
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (response.status === 404) {
      return null;
    }

    return await handleResponse<TelemetryData>(response);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function fetchTelemetryHistory(
  deviceId: string,
  limit: number = 20,
  order: "asc" | "desc" = "asc",
  signal?: AbortSignal,
): Promise<TelemetryData[]> {
  try {
    const url = `${apiBaseUrl}/devices/${encodeURIComponent(deviceId)}/telemetry?limit=${limit}&order=${order}`;
    const response = await fetch(url, {
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (response.status === 404) {
      return [];
    }

    const data = await handleResponse<TelemetryHistoryResponse>(response);
    return data.items;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return [];
    }
    throw error;
  }
}

export async function fetchDeviceState(
  deviceId: string,
  signal?: AbortSignal,
): Promise<DeviceStateData | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/devices/${encodeURIComponent(deviceId)}/state`, {
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (response.status === 404) {
      return null;
    }

    return await handleResponse<DeviceStateData>(response);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function sendCommand(
  deviceId: string,
  action: CommandAction,
  durationSeconds?: number,
  signal?: AbortSignal,
): Promise<CommandOut> {
  const body: { action: CommandAction; duration_seconds?: number } = { action };
  if (action === "pump_on" && durationSeconds !== undefined) {
    body.duration_seconds = durationSeconds;
  }

  const response = await fetch(`${apiBaseUrl}/devices/${encodeURIComponent(deviceId)}/commands`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
    signal,
  });

  return await handleResponse<CommandOut>(response);
}

export async function fetchCommand(
  commandId: string,
  signal?: AbortSignal,
): Promise<CommandOut> {
  const response = await fetch(`${apiBaseUrl}/commands/${encodeURIComponent(commandId)}`, {
    signal,
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  return await handleResponse<CommandOut>(response);
}

export async function fetchRecentCommands(
  deviceId: string,
  limit: number = 5,
  signal?: AbortSignal,
): Promise<CommandOut[]> {
  try {
    const response = await fetch(`${apiBaseUrl}/devices/${encodeURIComponent(deviceId)}/commands?limit=${limit}`, {
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (response.status === 404) {
      return [];
    }

    const data = await handleResponse<CommandListResponse>(response);
    return data.items;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return [];
    }
    throw error;
  }
}
