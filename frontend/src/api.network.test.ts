import { afterEach, expect, it, vi } from "vitest";
import { fetchCommand, sendCommand } from "./api";

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
