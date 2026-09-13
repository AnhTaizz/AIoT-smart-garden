import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

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
});
