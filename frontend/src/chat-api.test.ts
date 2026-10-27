import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChat } from "./api";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("chat API transport", () => {
  it("uses the local proxy and the custom backend contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ reply: "Kiểm tra đất", context: { status: "disabled" } }) });
    vi.stubGlobal("fetch", fetchMock);
    await sendChat("Tưới thế nào?", [], "node_01", false);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/chat");
    expect(JSON.parse(init.body)).toEqual({ message: "Tưới thế nào?", history: [], device_id: "node_01", include_garden_context: false });
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("shows the normalized Vietnamese error from the backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 504, json: async () => ({ detail: { code: "chat_timeout", message: "Model phản hồi quá lâu" } }) }));
    await expect(sendChat("Chào", [], "node_01", true)).rejects.toThrow("Model phản hồi quá lâu");
  });

  it("times out a hung request and releases its timer", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    })));
    const result = sendChat("Chào", [], "node_01", true);
    const assertion = expect(result).rejects.toThrow("Trợ lý phản hồi quá lâu");
    await vi.advanceTimersByTimeAsync(145000);
    await assertion;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("propagates cancellation when starting a new conversation", async () => {
    const controller = new AbortController();
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    })));
    const result = sendChat("Chào", [], "node_01", true, controller.signal);
    controller.abort();
    await expect(result).rejects.toMatchObject({ name: "AbortError" });
  });
});
