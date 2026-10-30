import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App, { mergeCommands } from "./App";
import type { CommandOut } from "./api";

const mockTelemetry = {
  id: 1,
  device_id: "node_01",
  boot_id: "boot_test123",
  sequence: 42,
  clock_synced: true,
  measured_at: "2026-09-29T04:00:00.000Z",
  received_at: "2026-09-29T04:00:00.100Z",
  uptime_ms: 120000,
  temperature_c: 28.4,
  air_humidity_pct: 65.2,
  soil_moisture_pct: 45.8,
  sensor_status: { aht20: "ok", soil: "ok" },
  simulated: true,
  payload_schema: "telemetry-v1",
  stale: false,
  stale_after_seconds: 30,
};

const mockDeviceState = {
  device_id: "node_01",
  boot_id: "boot_test123",
  state_sequence: 10,
  mode: "MANUAL",
  relay_state: "off",
  last_command_id: null,
  last_command_sequence: null,
  clock_synced: true,
  reported_at: "2026-09-29T04:00:00.000Z",
  received_at: "2026-09-29T04:00:00.100Z",
  stale: false,
  stale_after_seconds: 30,
};

function setupMockFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const urlStr = String(url);

    if (urlStr.endsWith("/health")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["/health"] ?? { status: "ok" },
      });
    }

    if (urlStr.endsWith("/ready")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["/ready"] ?? { status: "ready", checks: { postgres: "up" } },
      });
    }

    if (urlStr.endsWith("/control-access")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["/control-access"] ?? { commands_allowed: true, reason: null },
      });
    }

    if (urlStr.includes("/devices/node_01/latest")) {
      if (overrides["/latest"] === null) {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: async () => ({ detail: { code: "no_telemetry" } }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["/latest"] ?? mockTelemetry,
      });
    }

    if (urlStr.includes("/devices/node_01/state")) {
      if (overrides["/state"] === null) {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: async () => ({ detail: { code: "no_state" } }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["/state"] ?? mockDeviceState,
      });
    }

    if (urlStr.includes("/devices/node_01/telemetry")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["/telemetry"] ?? {
          device_id: "node_01",
          count: 1,
          order: "asc",
          items: [mockTelemetry],
        },
      });
    }

    if (urlStr.includes("/devices/node_01/commands")) {
      if (init?.method === "POST") {
        return Promise.resolve({
          ok: true,
          status: 202,
          json: async () => overrides["POST /commands"] ?? {
            command_id: "cmd-uuid-1234",
            device_id: "node_01",
            command_sequence: 1,
            action: "pump_on",
            params: { duration_seconds: 10 },
            target_boot_id: "boot_test123",
            status: "pending",
            device_ack: null,
            reason: null,
            created_at: "2026-09-29T04:00:00.000Z",
            expires_at: "2026-09-29T04:00:15.000Z",
          },
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["/commands"] ?? {
          device_id: "node_01",
          count: 0,
          items: [],
        },
      });
    }

    if (urlStr.includes("/commands/cmd-uuid-1234")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => overrides["GET /command"] ?? {
          command_id: "cmd-uuid-1234",
          device_id: "node_01",
          command_sequence: 1,
          action: "pump_on",
          params: { duration_seconds: 10 },
          target_boot_id: "boot_test123",
          status: "applied",
          device_ack: "applied",
          reason: null,
          confirmed_relay_state: "on",
          created_at: "2026-09-29T04:00:00.000Z",
          expires_at: "2026-09-29T04:00:15.000Z",
        },
      });
    }

    return Promise.reject(new Error(`Unhandled mock for URL: ${urlStr}`));
  });
}

describe("Dashboard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("hiển thị trạng thái mất kết nối mà không tạo số đo giả", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("backend-status")).toHaveTextContent(
        "Mất kết nối",
      );
    });
    expect(screen.getByTestId("database-status")).toHaveTextContent(
      "Không thể kiểm tra",
    );
    expect(screen.getAllByText("Chưa có dữ liệu")).toHaveLength(5);
    expect(screen.getByRole("button", { name: "Bật bơm" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Tắt bơm" })).toBeDisabled();
  });

  it("hiển thị telemetry thật và trạng thái thiết bị khi kết nối online", async () => {
    vi.stubGlobal("fetch", setupMockFetch());

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("backend-status")).toHaveTextContent("Đang hoạt động");
    });

    expect(screen.getByTestId("database-status")).toHaveTextContent("Sẵn sàng");

    // Telemetry values
    await waitFor(() => {
      expect(screen.getByText("28.4")).toBeInTheDocument();
      expect(screen.getByText("65.2")).toBeInTheDocument();
      expect(screen.getByText("45.8")).toBeInTheDocument();
    });

    // Badges
    expect(screen.getByText("Dữ liệu mô phỏng")).toBeInTheDocument();
    expect(screen.getByText("Trực tuyến")).toBeInTheDocument();

    // Relay state
    expect(screen.getByText("ĐANG TẮT")).toBeInTheDocument();

    // Buttons should be enabled
    expect(screen.getByRole("button", { name: "Bật bơm" })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Tắt bơm" })).not.toBeDisabled();
  });

  it("hiển thị 'Lỗi cảm biến' khi cảm biến bị lỗi và không bao giờ hiển thị số 0", async () => {
    const errorTelemetry = {
      ...mockTelemetry,
      temperature_c: null,
      air_humidity_pct: null,
      soil_moisture_pct: null,
      sensor_status: { aht20: "error", soil: "error" },
    };

    vi.stubGlobal("fetch", setupMockFetch({ "/latest": errorTelemetry }));

    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText("Lỗi cảm biến")).toHaveLength(3);
    });
  });

  it("gửi lệnh Bật bơm và theo dõi vòng đời lệnh chuyển sang applied", async () => {
    let commandStatus = "pending";

    const customFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const urlStr = String(url);
      if (urlStr.endsWith("/health")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: "ok" }) });
      if (urlStr.endsWith("/ready")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: "ready", checks: { postgres: "up" } }) });
      if (urlStr.endsWith("/control-access")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ commands_allowed: true, reason: null }) });
      if (urlStr.includes("/devices/node_01/latest")) return Promise.resolve({ ok: true, status: 200, json: async () => mockTelemetry });
      if (urlStr.includes("/devices/node_01/state")) return Promise.resolve({ ok: true, status: 200, json: async () => mockDeviceState });
      if (urlStr.includes("/devices/node_01/telemetry")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ device_id: "node_01", count: 0, items: [] }) });
      if (urlStr.includes("/devices/node_01/commands")) {
        if (init?.method === "POST") {
          return Promise.resolve({
            ok: true,
            status: 202,
            json: async () => ({
              command_id: "cmd-uuid-1234",
              device_id: "node_01",
              command_sequence: 1,
              action: "pump_on",
              params: { duration_seconds: 10 },
              target_boot_id: "boot_test123",
              status: "pending",
              device_ack: null,
              reason: null,
              created_at: "2026-09-29T04:00:00.000Z",
              expires_at: "2026-09-29T04:00:15.000Z",
            }),
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ device_id: "node_01", count: 0, items: [] }) });
      }
      if (urlStr.includes("/commands/cmd-uuid-1234")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            command_id: "cmd-uuid-1234",
            device_id: "node_01",
            command_sequence: 1,
            action: "pump_on",
            params: { duration_seconds: 10 },
            target_boot_id: "boot_test123",
            status: commandStatus,
            device_ack: commandStatus === "applied" ? "applied" : null,
            reason: null,
            confirmed_relay_state: commandStatus === "applied" ? "on" : null,
            created_at: "2026-09-29T04:00:00.000Z",
            expires_at: "2026-09-29T04:00:15.000Z",
          }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL ${urlStr}`));
    });

    vi.stubGlobal("fetch", customFetch);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Bật bơm" })).not.toBeDisabled();
    });

    // Click Bật bơm
    fireEvent.click(screen.getByRole("button", { name: "Bật bơm" }));

    // Phải hiển thị tracker pending
    await waitFor(() => {
      expect(screen.getByText("Đang gửi lệnh bật bơm...")).toBeInTheDocument();
    });

    // Nút Bật bơm phải bị disabled khi pending
    expect(screen.getByRole("button", { name: "Bật bơm" })).toBeDisabled();

    // Giả lập thiết bị áp dụng thành công lệnh
    commandStatus = "applied";

    await waitFor(
      () => {
        expect(
          screen.getByText("Thiết bị đã bật bơm thành công trong 10 giây (ACK + state khớp lệnh)."),
        ).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it("gửi lệnh Tắt bơm khi bấm nút Tắt bơm", async () => {
    let sentAction: string | null = null;

    const customFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const urlStr = String(url);
      if (urlStr.endsWith("/health")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: "ok" }) });
      if (urlStr.endsWith("/ready")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: "ready", checks: { postgres: "up" } }) });
      if (urlStr.endsWith("/control-access")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ commands_allowed: true, reason: null }) });
      if (urlStr.includes("/devices/node_01/latest")) return Promise.resolve({ ok: true, status: 200, json: async () => mockTelemetry });
      if (urlStr.includes("/devices/node_01/state")) return Promise.resolve({ ok: true, status: 200, json: async () => mockDeviceState });
      if (urlStr.includes("/devices/node_01/telemetry")) return Promise.resolve({ ok: true, status: 200, json: async () => ({ device_id: "node_01", count: 0, items: [] }) });
      if (urlStr.includes("/devices/node_01/commands")) {
        if (init?.method === "POST") {
          const body = JSON.parse(String(init.body));
          sentAction = body.action;
          return Promise.resolve({
            ok: true,
            status: 202,
            json: async () => ({
              command_id: "cmd-off-5678",
              device_id: "node_01",
              command_sequence: 2,
              action: "pump_off",
              params: {},
              target_boot_id: null,
              status: "applied",
              device_ack: "applied",
              reason: null,
              created_at: "2026-09-29T04:00:00.000Z",
              expires_at: "2026-09-29T04:00:15.000Z",
            }),
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ device_id: "node_01", count: 0, items: [] }) });
      }
      return Promise.reject(new Error(`Unhandled URL ${urlStr}`));
    });

    vi.stubGlobal("fetch", customFetch);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Tắt bơm" })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Tắt bơm" }));

    await waitFor(() => {
      expect(sentAction).toBe("pump_off");
    });
  });
});


describe("Remote command lifecycle", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it.each([
    ["timeout", null, /Quá thời hạn phản hồi/],
    ["rejected", "clock_unsynced", /Thiết bị chưa đồng bộ giờ UTC/],
  ])("shows backend %s without reporting applied", async (status, reason, message) => {
    vi.stubGlobal("fetch", setupMockFetch({"GET /command": {
      command_id: "cmd-uuid-1234", device_id: "node_01", action: "pump_on",
      params: {duration_seconds: 10}, status, reason, device_ack: null,
    }}));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", {name: "Bật bơm"})).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", {name: "Bật bơm"}));
    await waitFor(() => expect(screen.getByText(message as RegExp)).toBeInTheDocument(), {timeout: 3000});
    expect(screen.queryByText(/Thiết bị đã bật bơm thành công/)).not.toBeInTheDocument();
    // Nothing re-sends pump_on after a final timeout/rejection.
    await new Promise((resolve) => setTimeout(resolve, 1500));
    const mock = vi.mocked(fetch);
    expect(mock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  });

  it("recovers command status after network loss without sending ON twice", async () => {
    let reads = 0;
    const base = setupMockFetch();
    const mock = vi.fn((url: string, init?: RequestInit) => {
      if (String(url).endsWith("/commands/cmd-uuid-1234") && ++reads === 1) {
        return Promise.reject(new TypeError("temporary network loss"));
      }
      return base(url, init);
    });
    vi.stubGlobal("fetch", mock);
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", {name: "Bật bơm"})).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", {name: "Bật bơm"}));
    await waitFor(() => expect(screen.getByText(/Thiết bị đã bật bơm thành công/)).toBeInTheDocument(), {timeout: 4000});
    expect(reads).toBe(2);
    expect(mock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  });
});


describe("B/C state distinctions", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("locks pump buttons when the backend reports remote control disabled", async () => {
    const mock = setupMockFetch({"/control-access": {commands_allowed: false, reason: "remote_control_disabled"}});
    vi.stubGlobal("fetch", mock);
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Điều khiển bơm từ xa đang tắt/)).toBeInTheDocument());
    // Read-only data stays visible.
    expect(screen.getByText("28.4")).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "Bật bơm"})).toBeDisabled();
    expect(screen.getByRole("button", {name: "Tắt bơm"})).toBeDisabled();
    expect(mock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("shows the backend 403 message if a remote command is still refused", async () => {
    const base = setupMockFetch();
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve({ok: false, status: 403, json: async () => ({detail: {
          code: "remote_control_disabled",
          message: "Điều khiển bơm qua Internet đang tắt vì API chưa có xác thực.",
        }})});
      }
      return base(url, init);
    }));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", {name: "Bật bơm"})).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", {name: "Bật bơm"}));
    await waitFor(() => expect(screen.getByText(/qua Internet đang tắt/)).toBeInTheDocument());
    expect(screen.queryByText(/Đang đợi ACK/)).not.toBeInTheDocument();
  });

  it("distinguishes an API failure from a device that has not sent data", async () => {
    const base = setupMockFetch();
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (String(url).includes("/devices/node_01/latest")) {
        return Promise.resolve({ok: false, status: 503, json: async () => ({detail: {code: "database_unavailable"}})});
      }
      return base(url, init);
    }));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Không tải được số đo mới nhất/));
    expect(screen.getAllByText("Lỗi tải dữ liệu")).toHaveLength(3);
    expect(screen.getByText("Lỗi API telemetry")).toBeInTheDocument();
  });

  it("shows no-data (404) without an API error", async () => {
    vi.stubGlobal("fetch", setupMockFetch({"/latest": null, "/state": null}));
    render(<App />);
    await waitFor(() => expect(screen.getByText("Chưa kết nối thiết bị")).toBeInTheDocument());
    expect(screen.getAllByText("Chưa có dữ liệu").length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("marks a stale device state as unconfirmed instead of live", async () => {
    vi.stubGlobal("fetch", setupMockFetch({
      "/state": {...mockDeviceState, relay_state: "on", stale: true},
      "/latest": {...mockTelemetry, stale: true, simulated: false},
    }));
    render(<App />);
    await waitFor(() => expect(screen.getByText("Trạng thái cũ: bật")).toBeInTheDocument());
    expect(screen.queryByText("ĐANG BẬT")).not.toBeInTheDocument();
    expect(screen.getByText(/có thể\s+đang offline/)).toBeInTheDocument();
    expect(screen.getByText("Dữ liệu cũ (Stale)")).toBeInTheDocument();
    expect(screen.getByText("Thiết bị thật")).toBeInTheDocument();
  });

  it("labels timeout separately and flags a late ACK without calling it applied", async () => {
    vi.stubGlobal("fetch", setupMockFetch({"/commands": {device_id: "node_01", count: 1, items: [{
      command_id: "cmd-late", device_id: "node_01", command_sequence: 3, action: "pump_on",
      params: {duration_seconds: 5}, status: "timeout", device_ack: null, reason: null,
      created_at: "2026-09-29T04:00:00.000Z", expires_at: "2026-09-29T04:00:15.000Z",
      late_ack: "applied", late_ack_at: "2026-09-29T04:00:20.000Z",
    }]}}));
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Hết thời gian chờ · ACK đến trễ/)).toBeInTheDocument());
    expect(screen.queryByText("Thành công")).not.toBeInTheDocument();
  });
});


type MockResponse = { ok: boolean; status: number; json: () => Promise<unknown> };

function deferred() {
  let resolve!: (value: MockResponse) => void;
  const promise = new Promise<MockResponse>((done) => { resolve = done; });
  return { promise, resolve };
}

const okJson = (body: unknown): MockResponse => ({ ok: true, status: 200, json: async () => body });

function postCalls(mock: ReturnType<typeof vi.fn>) {
  return mock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
}

/** Capture the 5 s dashboard poll so tests trigger ticks deterministically. */
function capturePollTicks() {
  const ticks: Array<() => void> = [];
  const realSetInterval = window.setInterval.bind(window);
  vi.spyOn(window, "setInterval").mockImplementation(((handler: TimerHandler, ms?: number) => {
    if (ms === 5000 && typeof handler === "function") {
      ticks.push(handler as () => void);
      return 0;
    }
    return realSetInterval(handler, ms);
  }) as typeof window.setInterval);
  return ticks;
}

describe("Control access fails closed", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  const withAccess = (respond: () => Promise<MockResponse>) => {
    const base = setupMockFetch();
    const mock = vi.fn((url: string, init?: RequestInit) =>
      String(url).endsWith("/control-access") ? respond() : base(url, init));
    vi.stubGlobal("fetch", mock);
    return mock;
  };

  it.each([
    ["HTTP 500", () => Promise.resolve({ok: false, status: 500, json: async () => ({detail: {code: "http_500"}})})],
    ["network error", () => Promise.reject(new TypeError("Failed to fetch"))],
    ["empty object", () => Promise.resolve(okJson({}))],
    ["string boolean", () => Promise.resolve(okJson({commands_allowed: "true", reason: null}))],
    ["allowed with a reason", () => Promise.resolve(okJson({commands_allowed: true, reason: "x"}))],
    ["null body", () => Promise.resolve(okJson(null))],
    ["non-JSON body", () => Promise.resolve({ok: true, status: 200, json: async () => { throw new SyntaxError("bad"); }})],
  ])("locks the pump on %s without marking the backend offline", async (_name, respond) => {
    const mock = withAccess(respond as () => Promise<MockResponse>);
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Không xác minh được quyền điều khiển/)).toBeInTheDocument());
    expect(screen.getByTestId("backend-status")).toHaveTextContent("Đang hoạt động");
    expect(screen.getByText("28.4")).toBeInTheDocument();
    const on = screen.getByRole("button", {name: "Bật bơm"});
    expect(on).toBeDisabled();
    expect(screen.getByRole("button", {name: "Tắt bơm"})).toBeDisabled();
    fireEvent.click(on);
    expect(postCalls(mock)).toHaveLength(0);
  });

  it("stays locked while the check hangs, then unlocks only on an explicit allow", async () => {
    const pending = deferred();
    const mock = withAccess(() => pending.promise);
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Đang xác minh quyền điều khiển/)).toBeInTheDocument());
    expect(screen.getByRole("button", {name: "Bật bơm"})).toBeDisabled();
    expect(postCalls(mock)).toHaveLength(0);
    pending.resolve(okJson({commands_allowed: true, reason: null}));
    await waitFor(() => expect(screen.getByRole("button", {name: "Bật bơm"})).not.toBeDisabled());
    expect(screen.queryByTestId("control-notice")).not.toBeInTheDocument();
  });

  it("treats a refusal with an unknown reason as denied", async () => {
    withAccess(() => Promise.resolve(okJson({commands_allowed: false, reason: "auth_required"})));
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Điều khiển bơm từ xa đang tắt/)).toBeInTheDocument());
    expect(screen.getByRole("button", {name: "Bật bơm"})).toBeDisabled();
  });

  it("re-locks when a later access check fails", async () => {
    const ticks = capturePollTicks();
    let fail = false;
    withAccess(() => fail
      ? Promise.reject(new TypeError("offline"))
      : Promise.resolve(okJson({commands_allowed: true, reason: null})));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", {name: "Bật bơm"})).not.toBeDisabled());
    fail = true;
    act(() => ticks[ticks.length - 1]());
    await waitFor(() => expect(screen.getByRole("button", {name: "Bật bơm"})).toBeDisabled());
    expect(screen.getByText(/Không xác minh được quyền điều khiển/)).toBeInTheDocument();
  });
});

describe("Polling order and outdated data", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("drops a slow response from before a manual refresh", async () => {
    const slow = deferred();
    let latestCalls = 0;
    const base = setupMockFetch();
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (String(url).includes("/devices/node_01/latest")) {
        latestCalls += 1;
        if (latestCalls === 1) return slow.promise;
        return Promise.resolve(okJson({...mockTelemetry, sequence: 50, temperature_c: 31.5}));
      }
      return base(url, init);
    }));
    render(<App />);
    await waitFor(() => expect(latestCalls).toBe(1));
    fireEvent.click(screen.getByRole("button", {name: "Kiểm tra và làm mới dữ liệu"}));
    await waitFor(() => expect(screen.getByText("31.5")).toBeInTheDocument());
    // The old request finishes last with older data; it must not win.
    await act(async () => { slow.resolve(okJson({...mockTelemetry, sequence: 49, temperature_c: 20.1})); });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.getByText("31.5")).toBeInTheDocument();
    expect(screen.queryByText("20.1")).not.toBeInTheDocument();
  });

  it("never runs two polls at once; a tick during a slow poll is queued once", async () => {
    const ticks = capturePollTicks();
    const slow = deferred();
    let latestCalls = 0;
    const base = setupMockFetch();
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (String(url).includes("/devices/node_01/latest")) {
        latestCalls += 1;
        if (latestCalls === 1) return slow.promise;
        return Promise.resolve(okJson({...mockTelemetry, sequence: 61, temperature_c: 33.3}));
      }
      return base(url, init);
    }));
    render(<App />);
    await waitFor(() => expect(latestCalls).toBe(1));
    act(() => { ticks[0](); ticks[0](); ticks[0](); });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(latestCalls).toBe(1);
    await act(async () => { slow.resolve(okJson({...mockTelemetry, sequence: 60, temperature_c: 22.2})); });
    // Exactly one queued follow-up runs after the slow poll, and its newer value stays.
    await waitFor(() => expect(screen.getByText("33.3")).toBeInTheDocument());
    expect(latestCalls).toBe(2);
    expect(screen.queryByText("22.2")).not.toBeInTheDocument();
  });

  it("keeps the last good reading after an API error but marks it as not live", async () => {
    const ticks = capturePollTicks();
    let broken = false;
    const base = setupMockFetch();
    const error = () => Promise.resolve({ok: false, status: 503, json: async () => ({detail: {code: "database_unavailable"}})});
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      const path = String(url);
      if (broken && (path.includes("/latest") || path.includes("/state"))) return error();
      return base(url, init);
    }));
    render(<App />);
    await waitFor(() => expect(screen.getByText("Trực tuyến")).toBeInTheDocument());
    expect(screen.getByText("ĐANG TẮT")).toBeInTheDocument();
    broken = true;
    act(() => ticks[0]());
    await waitFor(() => expect(screen.getByText("Chưa cập nhật (lỗi API)")).toBeInTheDocument());
    expect(screen.getByText("28.4")).toBeInTheDocument();
    expect(screen.queryByText("Trực tuyến")).not.toBeInTheDocument();
    expect(screen.getByText("Chưa cập nhật: tắt")).toBeInTheDocument();
    expect(screen.queryByText("ĐANG TẮT")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/không phải số đo realtime/);
    expect(screen.getByText(/Số đo cuối cùng lúc/)).toBeInTheDocument();
  });

  it("stops writing after unmount", async () => {
    const ticks = capturePollTicks();
    const slow = deferred();
    let latestCalls = 0;
    const base = setupMockFetch();
    const mock = vi.fn((url: string, init?: RequestInit) => {
      if (String(url).includes("/devices/node_01/latest")) {
        latestCalls += 1;
        return slow.promise;
      }
      return base(url, init);
    });
    vi.stubGlobal("fetch", mock);
    const errors = vi.spyOn(console, "error");
    const { unmount } = render(<App />);
    await waitFor(() => expect(latestCalls).toBe(1));
    unmount();
    const callsAtUnmount = mock.mock.calls.length;
    await act(async () => { slow.resolve(okJson(mockTelemetry)); });
    act(() => ticks[0]());
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(mock.mock.calls.length).toBe(callsAtUnmount);
    expect(errors).not.toHaveBeenCalled();
  });
});

describe("mergeCommands", () => {
  const command = (status: CommandOut["status"]) => ({command_id: "c1", status}) as CommandOut;

  it("does not let an older list move a final command back to pending", () => {
    expect(mergeCommands([command("pending")], [command("applied")])[0].status).toBe("applied");
    expect(mergeCommands([command("timeout")], [command("pending")])[0].status).toBe("timeout");
    expect(mergeCommands([command("pending")], [])[0].status).toBe("pending");
  });
});
