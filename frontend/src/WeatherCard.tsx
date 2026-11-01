import { useEffect, useState } from "react";
import { fetchWeather, type WeatherData } from "./api";

const WEATHER_POLL_INTERVAL_MS = 60000;

function formatHour(isoString: string): string {
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(new Date(isoString));
}

function formatUpdated(isoString: string | null): string {
  if (!isoString) return "Chưa có";
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit",
  }).format(new Date(isoString));
}

function formatValue(value: number | null, unit: string): string {
  return value === null ? "—" : `${value.toLocaleString("vi-VN", { maximumFractionDigits: 1 })} ${unit}`;
}

const statusLabels: Record<WeatherData["status"], string> = {
  fresh: "Dự báo mới",
  stale: "Dự báo đã cũ",
  unavailable: "Chưa có dự báo",
  disabled: "Đang tắt",
};

/** Open-Meteo forecast from the backend cache; advisory only, not a garden measurement. */
export default function WeatherCard() {
  const [data, setData] = useState<WeatherData | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const value = await fetchWeather(controller.signal);
        if (!controller.signal.aborted) { setData(value); setConnected(true); }
      } catch {
        if (!controller.signal.aborted) setConnected(false);
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), WEATHER_POLL_INTERVAL_MS);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, []);

  const summary = data?.summary ?? null;
  const showForecast = data !== null && (data.status === "fresh" || data.status === "stale") && summary !== null;

  return (
    <section className="detail-card" style={{ marginTop: 24 }} aria-labelledby="weather-heading">
      <div className="card-title-row">
        <div>
          <p className="eyebrow">DỰ BÁO THỜI TIẾT · OPEN-METEO</p>
          <h2 id="weather-heading">Khả năng mưa 6 giờ tới</h2>
        </div>
        {data && (
          <span className={`badge-pill ${data.status === "fresh" ? "badge-live" : "badge-stale"}`}>
            {statusLabels[data.status]}
          </span>
        )}
      </div>

      {connected === null && <p role="status">Đang tải dự báo thời tiết…</p>}
      {connected === false && (
        <p role="status">
          Không lấy được dự báo từ backend.{data ? " Thông tin bên dưới có thể đã cũ." : ""}
        </p>
      )}
      {data?.status === "disabled" && (
        <p>Chưa bật dự báo thời tiết trên server{data.message ? ` (${data.message})` : ""}.</p>
      )}
      {data?.status === "unavailable" && (
        <p role="status">Chưa có dự báo thời tiết. {data.message ?? ""}</p>
      )}
      {data?.status === "stale" && (
        <p role="status">
          Dự báo đã cũ (cập nhật lúc {formatUpdated(data.fetched_at)}), chỉ để tham khảo và không được dùng để hoãn tưới.
          {data.message ? ` ${data.message}` : ""}
        </p>
      )}

      {showForecast && summary && (
        <>
          <dl style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12, margin: "16px 0" }}>
            <div>
              <dt>Xác suất mưa cao nhất trong một giờ</dt>
              <dd><strong>{formatValue(summary.max_precipitation_probability_pct, "%")}</strong></dd>
            </div>
            <div>
              <dt>Tổng lượng mưa dự báo</dt>
              <dd><strong>{formatValue(summary.total_precipitation_mm, "mm")}</strong></dd>
            </div>
            <div>
              <dt>Khung giờ</dt>
              <dd>{formatHour(summary.window_start)} – {formatHour(summary.window_end)}</dd>
            </div>
          </dl>
          {summary.hours_with_data < summary.hours_in_window && (
            <p>Thiếu dữ liệu mưa ở {summary.hours_in_window - summary.hours_with_data} giờ; tổng ở trên chỉ tính các giờ có dữ liệu.</p>
          )}
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
              <caption style={{ textAlign: "left", marginBottom: 8 }}>Dự báo theo giờ (12 giờ)</caption>
              <thead>
                <tr>
                  <th scope="col" style={{ textAlign: "left" }}>Giờ</th>
                  <th scope="col" style={{ textAlign: "right" }}>Khả năng mưa</th>
                  <th scope="col" style={{ textAlign: "right" }}>Lượng mưa</th>
                  <th scope="col" style={{ textAlign: "right" }}>Nhiệt độ dự báo</th>
                </tr>
              </thead>
              <tbody>
                {data.hours.map((hour) => (
                  <tr key={hour.time}>
                    <th scope="row" style={{ textAlign: "left", fontWeight: 500 }}>{formatHour(hour.time)}</th>
                    <td style={{ textAlign: "right" }}>{formatValue(hour.precipitation_probability_pct, "%")}</td>
                    <td style={{ textAlign: "right" }}>{formatValue(hour.precipitation_mm, "mm")}</td>
                    <td style={{ textAlign: "right" }}>{formatValue(hour.temperature_c, "°C")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ color: "var(--muted)", marginTop: 12 }}>
            Đây là dự báo cho khu vực vườn, không phải số đo tại vườn. Cập nhật lúc {formatUpdated(data.fetched_at)}.
            Dự báo chỉ để tham khảo khi cân nhắc hoãn tưới, không bao giờ tự bật bơm.{" "}
            <a href={data.attribution_url} target="_blank" rel="noopener noreferrer">{data.attribution}</a>
          </p>
        </>
      )}
    </section>
  );
}
