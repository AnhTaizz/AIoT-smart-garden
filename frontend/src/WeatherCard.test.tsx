import { render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import WeatherCard from "./WeatherCard";
import { fetchWeather, parseWeather, type WeatherData } from "./api";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, fetchWeather: vi.fn() };
});
afterEach(() => vi.resetAllMocks());

const base: WeatherData = {
  status: "fresh",
  reason: null,
  message: null,
  fetched_at: "2026-11-01T03:00:00Z",
  valid_until: "2026-11-01T05:00:00Z",
  summary: {
    window_start: "2026-11-01T03:10:00Z",
    window_end: "2026-11-01T09:10:00Z",
    hours_in_window: 7,
    hours_with_data: 6,
    max_precipitation_probability_pct: 80,
    total_precipitation_mm: 2.5,
  },
  hours: [
    { time: "2026-11-01T03:00:00Z", precipitation_probability_pct: 80, precipitation_mm: 2.5, temperature_c: 27 },
    { time: "2026-11-01T04:00:00Z", precipitation_probability_pct: null, precipitation_mm: null, temperature_c: null },
  ],
  attribution: "Weather data by Open-Meteo.com (CC BY 4.0)",
  attribution_url: "https://open-meteo.com/",
};

it("shows a fresh forecast labelled as forecast, with missing hours as unknown", async () => {
  vi.mocked(fetchWeather).mockResolvedValue(base);
  render(<WeatherCard />);
  expect(await screen.findByText("Dự báo mới")).toBeInTheDocument();
  // Once in the 6-hour summary and once in the first hourly row.
  expect(screen.getAllByText("80 %")).toHaveLength(2);
  expect(screen.getAllByText("2,5 mm")).toHaveLength(2);
  expect(screen.getByText(/không phải số đo tại vườn/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Open-Meteo/ })).toHaveAttribute("href", "https://open-meteo.com/");
  const rows = within(screen.getByRole("table")).getAllByRole("row");
  // Second forecast hour has nulls: shown as "—", never as 0.
  expect(within(rows[2]).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["—", "—", "—"]);
  expect(screen.getByText(/Thiếu dữ liệu mưa ở 1 giờ/)).toBeInTheDocument();
});

it("warns that a stale forecast must not be used to delay watering", async () => {
  vi.mocked(fetchWeather).mockResolvedValue({ ...base, status: "stale", reason: "provider_timeout", message: "Máy chủ thời tiết phản hồi quá lâu." });
  render(<WeatherCard />);
  expect(await screen.findByText("Dự báo đã cũ")).toBeInTheDocument();
  expect(screen.getByText(/không được dùng để hoãn tưới/)).toBeInTheDocument();
  expect(screen.getByText(/phản hồi quá lâu/)).toBeInTheDocument();
});

it.each([
  ["disabled", "weather_disabled", /Chưa bật dự báo thời tiết/],
  ["unavailable", "weather_not_fetched", /Chưa có dự báo thời tiết/],
] as const)("shows %s without any forecast numbers", async (status, reason, text) => {
  vi.mocked(fetchWeather).mockResolvedValue({ ...base, status, reason, message: null, fetched_at: null, valid_until: null, summary: null, hours: [] });
  render(<WeatherCard />);
  expect(await screen.findByText(text)).toBeInTheDocument();
  expect(screen.queryByRole("table")).toBeNull();
  expect(screen.queryByText(/%/)).toBeNull();
});

it("reports a backend failure instead of showing an empty forecast", async () => {
  vi.mocked(fetchWeather).mockRejectedValue(new Error("offline"));
  render(<WeatherCard />);
  expect(await screen.findByText(/Không lấy được dự báo từ backend/)).toBeInTheDocument();
  expect(screen.queryByRole("table")).toBeNull();
});

it("rejects malformed weather payloads", () => {
  expect(() => parseWeather({ ...base, status: "sunny" })).toThrow();
  expect(() => parseWeather({ ...base, hours: [{ time: "x", precipitation_probability_pct: "80", precipitation_mm: 0, temperature_c: 1 }] })).toThrow();
  expect(() => parseWeather({ ...base, summary: { ...base.summary, total_precipitation_mm: Number.NaN } })).toThrow();
  expect(parseWeather(base).hours[1].precipitation_mm).toBeNull();
});
