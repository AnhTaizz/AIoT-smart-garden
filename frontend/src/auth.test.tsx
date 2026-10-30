import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { sendChat } from "./api";
import { clearSession, getSession, setSession } from "./auth";

const TOKEN = "session-token-abcdefghijklmnopqrstuvwxyz";
const telemetry = {
  id: 1, device_id: "node_01", boot_id: "boot_a", sequence: 7, clock_synced: true,
  measured_at: "2026-10-30T10:00:00.000Z", received_at: "2026-10-30T10:00:00.100Z",
  uptime_ms: 1000, temperature_c: 27.7, air_humidity_pct: 61.5, soil_moisture_pct: 40.2,
  sensor_status: { aht20: "ok", soil: "ok" }, simulated: true, payload_schema: "telemetry-v1",
  stale: false, stale_after_seconds: 30,
};
const state = {
  device_id: "node_01", boot_id: "boot_a", state_sequence: 3, mode: "MANUAL", relay_state: "off",
  last_command_id: null, last_command_sequence: null, clock_synced: true,
  reported_at: "2026-10-30T10:00:00.000Z", received_at: "2026-10-30T10:00:00.100Z",
  stale: false, stale_after_seconds: 30,
};

type Reply = { ok: boolean; status: number; json: () => Promise<unknown> };
const json = (status: number, body: unknown): Reply => ({ ok: status < 400, status, json: async () => body });

interface Options {
  login?: () => Reply | Promise<Reply>;
  role?: "operator" | "viewer";
  protectedStatus?: () => number;
  commandStatus?: number;
}

/** A fake backend that enforces the bearer token like the real one. */
function backend(options: Options = {}) {
  const role = options.role ?? "operator";
  const calls: Array<{ url: string; method: string; auth: string | undefined; body?: string }> = [];
  const mock = vi.fn((input: string, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const headers = (init?.headers ?? {}) as Record<string, string>;
    calls.push({ url, method, auth: headers.Authorization, body: init?.body as string | undefined });
    if (url.endsWith("/health")) return Promise.resolve(json(200, { status: "ok" }));
    if (url.endsWith("/ready")) return Promise.resolve(json(200, { status: "ready", checks: { postgres: "up" } }));
    if (url.endsWith("/auth/login")) {
      return Promise.resolve(options.login ? options.login() : json(200, {
        access_token: TOKEN, token_type: "bearer", expires_at: new Date(Date.now() + 3_600_000).toISOString(),
        user: { username: "operator", role },
      }));
    }
    if (headers.Authorization !== `Bearer ${TOKEN}`) {
      return Promise.resolve(json(401, { detail: { code: "auth_required", message: "Cần đăng nhập" } }));
    }
    const status = options.protectedStatus?.() ?? 200;
    if (status !== 200) return Promise.resolve(json(status, { detail: { code: "invalid_session", message: "Phiên hết hạn" } }));
    if (url.endsWith("/auth/logout")) return Promise.resolve(json(200, { status: "logged_out" }));
    if (url.endsWith("/control-access")) {
      return Promise.resolve(json(200, role === "operator"
        ? { commands_allowed: true, reason: null, role }
        : { commands_allowed: false, reason: "forbidden", role }));
    }
    if (url.includes("/latest")) return Promise.resolve(json(200, telemetry));
    if (url.includes("/state")) return Promise.resolve(json(200, state));
    if (url.includes("/telemetry")) return Promise.resolve(json(200, { device_id: "node_01", count: 1, order: "asc", items: [telemetry] }));
    if (url.includes("/commands") && method === "POST") {
      return Promise.resolve(json(options.commandStatus ?? 401, { detail: { code: "invalid_session", message: "Phiên hết hạn" } }));
    }
    if (url.includes("/commands")) return Promise.resolve(json(200, { device_id: "node_01", count: 0, items: [] }));
    if (url.endsWith("/chat")) return Promise.resolve(json(200, { reply: "ok", context: { status: "disabled" } }));
    return Promise.reject(new Error(`unhandled ${url}`));
  });
  vi.stubGlobal("fetch", mock);
  return { mock, calls };
}

async function logIn(password = "a-long-password") {
  fireEvent.change(screen.getByLabelText("Tên đăng nhập"), { target: { value: "operator" } });
  fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
}

const gardenCalls = <T extends { url: string }>(calls: T[]) => calls.filter((c) => /\/devices\/|\/commands\/|\/chat|\/control-access/.test(c.url));

beforeEach(() => clearSession("logout"));
afterEach(() => {
  clearSession("logout");
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Login gate", () => {
  it("shows only the login form and fetches no garden data without a session", async () => {
    const { calls } = backend();
    render(<App />);
    expect(screen.getByRole("heading", { name: "Đăng nhập vận hành" })).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(gardenCalls(calls)).toHaveLength(0);
    expect(screen.queryByText("27.7")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Bật bơm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Trợ lý nông nghiệp/ })).not.toBeInTheDocument();
  });

  it("logs in, keeps the token in memory only, and sends it on every protected call", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const { calls } = backend();
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByText("27.7")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("button", { name: "Bật bơm" })).not.toBeDisabled());
    expect(screen.getByTestId("session-user")).toHaveTextContent("operator · Vận hành");
    const login = calls.find((c) => c.url.endsWith("/auth/login"))!;
    expect(login.auth).toBeUndefined();
    expect(JSON.parse(login.body!)).toEqual({ username: "operator", password: "a-long-password" });
    const protectedCalls = gardenCalls(calls);
    expect(protectedCalls.length).toBeGreaterThan(0);
    expect(protectedCalls.every((c) => c.auth === `Bearer ${TOKEN}`)).toBe(true);
    expect(setItem).not.toHaveBeenCalled();
    expect(getSession()?.token).toBe(TOKEN);
    expect(document.body.innerHTML).not.toContain("a-long-password");
  });

  it.each([
    ["wrong password", () => json(401, { detail: { code: "invalid_credentials", message: "Tên đăng nhập hoặc mật khẩu không đúng." } }), /mật khẩu không đúng/],
    ["lockout", () => json(429, { detail: { code: "login_rate_limited", message: "Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau.", retry_after_seconds: 42 } }), /quá nhiều lần.*42 giây/],
    ["not configured", () => json(503, { detail: { code: "auth_not_configured", message: "Backend chưa cấu hình tài khoản vận hành nên không thể đăng nhập." } }), /chưa cấu hình tài khoản/],
    ["malformed reply", () => json(200, { access_token: "x" }), /không hợp lệ/],
  ])("shows a clear error on %s and stays locked", async (_name, reply, message) => {
    const { calls } = backend({ login: reply });
    render(<App />);
    await logIn("bad-password-1");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message as RegExp));
    expect(getSession()).toBeNull();
    expect(gardenCalls(calls)).toHaveLength(0);
    expect((screen.getByLabelText("Mật khẩu") as HTMLInputElement).value).toBe("");
  });

  it("reports a network failure during login", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Không kết nối được backend/));
  });
});

describe("Session end", () => {
  it("returns to login when the server answers 401 during polling", async () => {
    let status = 200;
    const { calls } = backend({ protectedStatus: () => status });
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByText("27.7")).toBeInTheDocument());
    status = 401;
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra và làm mới dữ liệu" }));
    await waitFor(() => expect(screen.getByText(/không còn hợp lệ/)).toBeInTheDocument());
    expect(screen.queryByText("27.7")).not.toBeInTheDocument();
    expect(getSession()).toBeNull();
    // Unmounted dashboard: nothing keeps polling with the dead token.
    const after = calls.length;
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(calls.length).toBe(after);
  });

  it("does not retry a pump command that got 401 and goes back to login", async () => {
    const { calls } = backend({ commandStatus: 401 });
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByRole("button", { name: "Bật bơm" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Bật bơm" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Đăng nhập vận hành" })).toBeInTheDocument());
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(calls.filter((c) => c.method === "POST" && c.url.includes("/commands"))).toHaveLength(1);
  });

  it("locks the dashboard when the session reaches its expiry time", async () => {
    backend({
      login: () => json(200, {
        access_token: TOKEN, token_type: "bearer", expires_at: new Date(Date.now() + 300).toISOString(),
        user: { username: "operator", role: "operator" },
      }),
    });
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByTestId("session-user")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Phiên đăng nhập đã hết hạn/)).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.queryByRole("button", { name: "Bật bơm" })).not.toBeInTheDocument();
  });

  it("confirms a server-side logout only after the server answered", async () => {
    const { calls } = backend();
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByText("27.7")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
    await waitFor(() => expect(screen.getByTestId("session-end-notice")).toHaveTextContent(/Máy chủ đã xác nhận/));
    const logout = calls.filter((c) => c.url.endsWith("/auth/logout"));
    expect(logout).toHaveLength(1);
    expect(logout[0].method).toBe("POST");
    expect(logout[0].auth).toBe(`Bearer ${TOKEN}`);
    expect(getSession()).toBeNull();
  });

  it("treats a 401 from logout as already logged out on the server", async () => {
    const base = backend();
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByText("27.7")).toBeInTheDocument());
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => String(url).endsWith("/auth/logout")
      ? Promise.resolve(json(401, { detail: { code: "invalid_session" } }))
      : base.mock(url, init)));
    fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
    await waitFor(() => expect(screen.getByTestId("session-end-notice")).toHaveTextContent(/Máy chủ đã xác nhận/));
  });

  it.each([
    ["network error", () => Promise.reject(new TypeError("offline"))],
    ["HTTP 500", () => Promise.resolve(json(500, { detail: { code: "database_unavailable", message: "DB lỗi" } }))],
    ["timeout", () => Promise.reject(new DOMException("Aborted", "AbortError"))],
  ])("on %s: leaves this device but does not claim the server revoked the token", async (_name, fail) => {
    const base = backend();
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByText("27.7")).toBeInTheDocument());
    const logoutCalls: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (String(url).endsWith("/auth/logout")) {
        logoutCalls.push(String(url));
        return (fail as () => Promise<Reply>)();
      }
      return base.mock(url, init);
    }));
    fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
    const notice = await screen.findByTestId("session-end-notice");
    expect(notice).toHaveTextContent(/Đã thoát trên thiết bị này/);
    expect(notice).toHaveTextContent(/CHƯA xác nhận/);
    expect(notice).toHaveTextContent(/hết hạn lúc \d{2}:\d{2}/);
    expect(notice).not.toHaveTextContent(/Máy chủ đã xác nhận/);
    expect(getSession()).toBeNull();
    // The revoke is tried once, never retried automatically.
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(logoutCalls).toHaveLength(1);
  });

  it("locks pump controls immediately while the logout request is pending", async () => {
    const base = backend({ commandStatus: 202 });
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByRole("button", { name: "Bật bơm" })).not.toBeDisabled());
    let finish!: (reply: Reply) => void;
    const mock = vi.fn((url: string, init?: RequestInit) => String(url).endsWith("/auth/logout")
      ? new Promise<Reply>((resolve) => { finish = resolve; })
      : base.mock(url, init));
    vi.stubGlobal("fetch", mock);
    fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
    expect(screen.getByRole("button", { name: "Bật bơm" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Tắt bơm" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Đang đăng xuất…" })).toBeDisabled();
    expect(screen.getByText(/Đang đăng xuất; điều khiển bơm đã khóa/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Bật bơm" }));
    expect(mock.mock.calls.filter(([, init]) => init?.method === "POST" && !String(init?.body ?? "").includes("username"))
      .filter(([url]) => String(url).includes("/commands"))).toHaveLength(0);
    await act(async () => { finish(json(200, { status: "logged_out" })); });
    await screen.findByTestId("session-end-notice");
  });

  it("a late 401 from the old session does not end a new login after an unconfirmed logout", async () => {
    // The old session has a slow read in flight when the user logs out offline.
    const base = backend();
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByText("27.7")).toBeInTheDocument());
    let releaseOld!: (reply: Reply) => void;
    let offline = true;
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      const path = String(url);
      if (offline && path.endsWith("/auth/logout")) return Promise.reject(new TypeError("offline"));
      if (offline && path.includes("/latest")) return new Promise<Reply>((resolve) => { releaseOld = resolve; });
      return base.mock(url, init);
    }));
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra và làm mới dữ liệu" }));
    await waitFor(() => expect(releaseOld).toBeDefined());
    fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
    await screen.findByText(/CHƯA xác nhận/);
    offline = false;
    const NEW = "second-session-token-0123456789abcdef";
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      const headers = (init?.headers ?? {}) as Record<string, string>;
      if (String(url).endsWith("/auth/login")) {
        return Promise.resolve(json(200, { access_token: NEW, token_type: "bearer",
          expires_at: new Date(Date.now() + 3_600_000).toISOString(), user: { username: "operator", role: "operator" } }));
      }
      if (headers.Authorization === `Bearer ${NEW}`) {
        return base.mock(url, { ...init, headers: { ...headers, Authorization: `Bearer ${TOKEN}` } });
      }
      return base.mock(url, init);
    }));
    await logIn();
    await waitFor(() => expect(getSession()?.token).toBe(NEW));
    // Now the old request finally fails with 401: it must not log the user out.
    await act(async () => { releaseOld(json(401, { detail: { code: "invalid_session" } })); });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(getSession()?.token).toBe(NEW);
    expect(screen.getByTestId("session-user")).toBeInTheDocument();
  });

  it("ignores a late 401 for an older token after a new login", async () => {
    setSession({ token: "old-token-0123456789abcdef", username: "operator", role: "operator", expiresAt: Date.now() + 60_000 });
    let release!: (reply: Reply) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Reply>((resolve) => { release = resolve; })));
    const pending = sendChat("Chào", [], "node_01", false).catch(() => undefined);
    setSession({ token: TOKEN, username: "operator", role: "operator", expiresAt: Date.now() + 60_000 });
    await act(async () => { release(json(401, { detail: { code: "invalid_session" } })); await pending; });
    expect(getSession()?.token).toBe(TOKEN);
  });
});

describe("Viewer account", () => {
  it("shows data but keeps pump buttons locked", async () => {
    const { calls } = backend({ role: "viewer" });
    render(<App />);
    await logIn();
    await waitFor(() => expect(screen.getByText(/chỉ có quyền xem/)).toBeInTheDocument());
    expect(screen.getByText("27.7")).toBeInTheDocument();
    expect(screen.getByTestId("session-user")).toHaveTextContent("Chỉ xem");
    expect(screen.getByRole("button", { name: "Bật bơm" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Tắt bơm" })).toBeDisabled();
    expect(calls.filter((c) => c.method === "POST" && c.url.includes("/commands"))).toHaveLength(0);
  });
});
