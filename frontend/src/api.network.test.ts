import { afterEach, expect, it, vi } from "vitest";
import { fetchCommand, fetchControlAccess, parseControlAccess, sendCommand } from "./api";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it("aborts a hung status request instead of leaving polling stuck", async () => {
  vi.useFakeTimers();
  const fetchMock = vi.fn((_input, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  }));
  vi.stubGlobal("fetch", fetchMock);
  const promise = fetchCommand("pending-command");
  const rejected = expect(promise).rejects.toThrow("Aborted");
  await vi.advanceTimersByTimeAsync(10000);
  await rejected;
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("does not replay a pump POST after a network failure", async () => {
  const fetchMock = vi.fn().mockRejectedValue(new TypeError("offline"));
  vi.stubGlobal("fetch", fetchMock);
  await expect(sendCommand("node_01", "pump_on", 10)).rejects.toThrow("offline");
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][1].method).toBe("POST");
});

it("times out a hung control-access check instead of reporting it allowed", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_input, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  })));
  const rejected = expect(fetchControlAccess()).rejects.toThrow("Aborted");
  await vi.advanceTimersByTimeAsync(10000);
  await rejected;
});

it("rejects non-2xx control-access responses", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false, status: 500, json: async () => ({ detail: { code: "http_500", message: "boom" } }),
  }));
  await expect(fetchControlAccess()).rejects.toThrow("boom");
});

it("accepts only an explicit allow; any refusal is denied; anything else throws", () => {
  expect(parseControlAccess({ commands_allowed: true, reason: null })).toEqual({ commands_allowed: true, reason: null });
  expect(parseControlAccess({ commands_allowed: false, reason: "other" }).commands_allowed).toBe(false);
  for (const body of [null, {}, [], "ok", { commands_allowed: 1 }, { commands_allowed: true }, { commands_allowed: true, reason: "x" }]) {
    expect(() => parseControlAccess(body)).toThrow();
  }
});
