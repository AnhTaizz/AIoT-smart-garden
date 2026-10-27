import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ChatAssistant from "./ChatAssistant";
import { sendChat, type ChatReply } from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(),
  sendChat: vi.fn(),
}));

const reply: ChatReply = {
  reply: "## Nhận định\n\n**Kiểm tra đất** trước khi tưới.\n\n1. Kiểm tra thoát nước.\n2. Quan sát rễ.",
  context: {
    status: "included", device_id: "node_01", captured_at: "2026-10-27T03:00:00Z",
    telemetry: { received_at: "2026-10-27T02:59:00Z", measured_at: null, stale: true, simulated: true, clock_synced: false, temperature_c: 28, air_humidity_pct: 65, soil_moisture_pct: null, sensor_status: { aht20: "ok", soil: "error" } },
    state: null,
    warnings: ["Đây là dữ liệu cảm biến mô phỏng."],
  },
  prompt_version: "smart-garden-agro-v1",
  reply_source: "model",
};

afterEach(() => vi.resetAllMocks());

function openChat() {
  render(<ChatAssistant deviceId="node_01" />);
  fireEvent.click(screen.getByRole("button", { name: "Trợ lý nông nghiệp" }));
}

function ask(question = "Cây bị vàng lá") {
  fireEvent.change(screen.getByRole("textbox", { name: "Câu hỏi của bạn" }), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));
}

describe("Trợ lý nông nghiệp", () => {
  it("opens, supports Escape and restores keyboard focus", () => {
    openChat();
    expect(screen.getByRole("textbox")).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Trợ lý nông nghiệp" })).toHaveFocus();
  });

  it("sends server-owned context selection and renders Markdown with source labels", async () => {
    vi.mocked(sendChat).mockResolvedValue(reply);
    openChat();
    ask();
    await screen.findByRole("heading", { name: "Nhận định" });
    expect(sendChat).toHaveBeenCalledWith("Cây bị vàng lá", [], "node_01", true, expect.any(AbortSignal));
    expect(screen.getByText("Kiểm tra đất").tagName).toBe("STRONG");
    fireEvent.click(screen.getByText(/Dữ liệu gửi kèm/));
    expect(screen.getByText("Mô phỏng")).toBeInTheDocument();
    expect(screen.getByText("Dữ liệu cũ")).toBeInTheDocument();
    expect(screen.getByText("Không khả dụng")).toBeInTheDocument();
    expect(screen.getByText("Đây là dữ liệu cảm biến mô phỏng.")).toBeInTheDocument();
  });

  it("keeps conversation when closed, and sends complete history on follow-up", async () => {
    vi.mocked(sendChat).mockResolvedValue(reply);
    openChat();
    ask();
    await screen.findByRole("heading", { name: "Nhận định" });
    fireEvent.click(screen.getByRole("button", { name: "Đóng trò chuyện" }));
    fireEvent.click(screen.getByRole("button", { name: "Trợ lý nông nghiệp" }));
    expect(screen.getByText("Cây bị vàng lá")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox"));
    ask("Tôi nên kiểm tra gì tiếp?");
    await waitFor(() => expect(sendChat).toHaveBeenCalledTimes(2));
    expect(vi.mocked(sendChat).mock.calls[1][1]).toEqual([
      { role: "user", content: "Cây bị vàng lá" }, { role: "assistant", content: reply.reply },
    ]);
    expect(vi.mocked(sendChat).mock.calls[1][3]).toBe(false);
  });

  it("does not duplicate user messages on retry", async () => {
    vi.mocked(sendChat).mockRejectedValueOnce(new Error("Kaggle mất kết nối")).mockResolvedValueOnce(reply);
    openChat();
    ask();
    await screen.findByRole("alert");
    expect(screen.getByRole("textbox")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    await screen.findByRole("heading", { name: "Nhận định" });
    expect(screen.getAllByText("Cây bị vàng lá")).toHaveLength(1);
    expect(vi.mocked(sendChat).mock.calls[1][1]).toEqual([]);
  });

  it("lets users edit a failed question without leaving an unmatched history turn", async () => {
    vi.mocked(sendChat).mockRejectedValueOnce(new Error("Mất kết nối")).mockResolvedValueOnce(reply);
    openChat();
    ask();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Sửa câu hỏi" }));
    expect(screen.getByRole("textbox")).toHaveValue("Cây bị vàng lá");
    ask("Cây cà chua bị vàng lá già");
    await screen.findByRole("heading", { name: "Nhận định" });
    expect(vi.mocked(sendChat).mock.calls[1][1]).toEqual([]);
  });

  it("blocks duplicate sends and ignores a late response after a new conversation", async () => {
    let resolve!: (value: ChatReply) => void;
    vi.mocked(sendChat).mockImplementation(() => new Promise((done) => { resolve = done; }));
    openChat();
    ask();
    expect(screen.getByRole("button", { name: "Gửi câu hỏi" })).toBeDisabled();
    const signal = vi.mocked(sendChat).mock.calls[0][4];
    fireEvent.click(screen.getByRole("button", { name: "Cuộc trò chuyện mới" }));
    expect(signal?.aborted).toBe(true);
    resolve(reply);
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Nhận định" })).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Vườn của bạn hôm nay thế nào?" })).toBeInTheDocument();
  });

  it("handles Enter to send and Shift+Enter to keep editing", async () => {
    vi.mocked(sendChat).mockResolvedValue(reply);
    openChat();
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Cách kiểm tra đất?" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(sendChat).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter" });
    await screen.findByRole("heading", { name: "Nhận định" });
    expect(sendChat).toHaveBeenCalledTimes(1);
  });

  it("does not render raw HTML, external images, or javascript links", async () => {
    vi.mocked(sendChat).mockResolvedValue({ ...reply, reply: '<script>alert(1)</script>\n\n![tracking](https://example.com/pixel)\n\n[x](javascript:alert%281%29)' });
    openChat();
    ask();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    const panel = screen.getByRole("dialog");
    expect(panel.querySelector("script")).toBeNull();
    expect(panel.querySelector("img")).toBeNull();
    expect(panel.querySelector('a[href^="javascript:"]')).toBeNull();
  });

  it("labels a server fact response when the model contradicted device data", async () => {
    vi.mocked(sendChat).mockResolvedValue({ ...reply, reply_source: "garden_facts" });
    openChat();
    ask();
    await screen.findByText(/Lời tư vấn của model chưa khớp dữ liệu/);
  });
});
