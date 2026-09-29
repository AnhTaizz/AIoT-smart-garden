import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  fetchCommand,
  fetchDeviceState,
  fetchLatestTelemetry,
  fetchRecentCommands,
  fetchSystemStatus,
  fetchTelemetryHistory,
  sendCommand,
  type BackendStatus,
  type CommandAction,
  type CommandOut,
  type DatabaseStatus,
  type DeviceStateData,
  type SystemStatus,
  type TelemetryData,
} from "./api";

const DEFAULT_DEVICE_ID = "node_01";
const POLL_INTERVAL_MS = 5000;
const COMMAND_POLL_INTERVAL_MS = 1000;
const MAX_DURATION_SECONDS = 120;
const MIN_DURATION_SECONDS = 1;

const emptyStatus: SystemStatus = {
  backend: "checking",
  database: "checking",
};

const backendLabels: Record<BackendStatus, string> = {
  checking: "Đang kiểm tra",
  online: "Đang hoạt động",
  offline: "Mất kết nối",
};

const databaseLabels: Record<DatabaseStatus, string> = {
  checking: "Đang kiểm tra",
  ready: "Sẵn sàng",
  "not-ready": "Chưa sẵn sàng",
  unavailable: "Không thể kiểm tra",
};

const rejectReasonsVi: Record<string, string> = {
  busy: "Thiết bị đang bận chạy lệnh tưới khác.",
  clock_unsynced: "Thiết bị chưa đồng bộ giờ UTC.",
  expired: "Lệnh đã hết thời hạn hiệu lực.",
  superseded: "Lệnh bị hủy do có lệnh dừng mới hơn.",
  boot_mismatch: "Thiết bị vừa khởi động lại (lệch boot_id).",
  invalid_duration: "Thời gian bơm vượt quá giới hạn an toàn.",
  safety_lock: "Khóa an toàn phần cứng đang kích hoạt.",
  relay_error: "Lỗi phần cứng relay.",
  sensor_error: "Lỗi cảm biến.",
  invalid_payload: "Dữ liệu lệnh không hợp lệ.",
  unsupported_action: "Hành động không được hỗ trợ.",
  "backend:device_rebooted": "Thiết bị khởi động lại trong khi chờ.",
  device_boot_unknown: "Chờ thiết bị gửi trạng thái boot.",
  backend_publish_failed: "Không thể gửi lệnh qua MQTT broker.",
  mqtt_unavailable: "Mất kết nối MQTT broker.",
};

const durationPresets = [5, 10, 30, 60];

function StatusDot({ state }: { state: BackendStatus | DatabaseStatus }) {
  return <span aria-hidden="true" className={`status-dot status-${state}`} />;
}

function SensorIcon({ type }: { type: "thermometer" | "droplet" | "soil" }) {
  if (type === "thermometer") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M14 14.76V5a4 4 0 0 0-8 0v9.76a6 6 0 1 0 8 0ZM10 3a2 2 0 0 1 2 2v10.7l.5.3a4 4 0 1 1-5 0l.5-.3V5a2 2 0 0 1 2-2Zm-1 5h2v8.27a2.5 2.5 0 1 1-2 0V8Z" />
      </svg>
    );
  }

  if (type === "droplet") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2.3 5.6 9.4A7.5 7.5 0 0 0 4 14a8 8 0 0 0 16 0 7.5 7.5 0 0 0-1.6-4.6L12 2.3Zm0 18.2A6.5 6.5 0 0 1 5.5 14c0-1.35.5-2.57 1.22-3.58L12 4.57l5.28 5.85A5.95 5.95 0 0 1 18.5 14a6.5 6.5 0 0 1-6.5 6.5Zm-4-6.25h1.5A2.5 2.5 0 0 0 12 16.75v1.5a4 4 0 0 1-4-4Z" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.9 3.1C14.7 2.4 9.8 4 7 7.7A8.2 8.2 0 0 0 5.4 14L2 17.4 3.6 19l3.3-3.3a8.4 8.4 0 0 0 5.5 1.4c5.3-.7 8.8-5.8 8.5-14Zm-8.7 12A6.4 6.4 0 0 1 8.4 14l3.9-3.9-1.4-1.4-3.5 3.5c.1-1.2.5-2.3 1.2-3.3 2.1-2.8 5.6-4.2 10.3-4-.5 5.8-3 9.7-6.7 10.2Z" />
    </svg>
  );
}

function formatTime(isoString: string | null | undefined): string {
  if (!isoString) return "Chưa có";
  try {
    const date = new Date(isoString);
    return new Intl.DateTimeFormat("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  } catch {
    return isoString;
  }
}

// Mini Sparkline SVG for historical trend
function SparklineChart({
  data,
  label,
  color,
  unit,
}: {
  data: number[];
  label: string;
  color: string;
  unit: string;
}) {
  if (data.length < 2) {
    return (
      <div className="sparkline-empty">
        <small>Cần thêm dữ liệu để hiển thị biểu đồ</small>
      </div>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 280;
  const height = 60;
  const padding = 8;

  const points = data
    .map((val, idx) => {
      const x = padding + (idx / (data.length - 1)) * (width - 2 * padding);
      const y = height - padding - ((val - min) / range) * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const latestVal = data[data.length - 1];

  return (
    <div className="sparkline-container" aria-label={`Biểu đồ xu hướng ${label}`}>
      <div className="sparkline-header">
        <span>{label}</span>
        <strong>
          {latestVal.toFixed(1)} {unit}
        </strong>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="sparkline-svg"
        preserveAspectRatio="none"
      >
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
        {data.map((val, idx) => {
          const x = padding + (idx / (data.length - 1)) * (width - 2 * padding);
          const y = height - padding - ((val - min) / range) * (height - 2 * padding);
          return (
            <circle
              key={idx}
              cx={x}
              cy={y}
              r={idx === data.length - 1 ? 4 : 2}
              fill={color}
            />
          );
        })}
      </svg>
      <div className="sparkline-footer">
        <small>Thấp: {min.toFixed(1)}</small>
        <small>Cao: {max.toFixed(1)}</small>
      </div>
    </div>
  );
}

export default function App() {
  const durationInputId = useId();
  const [deviceId] = useState<string>(DEFAULT_DEVICE_ID);
  const [status, setStatus] = useState<SystemStatus>(emptyStatus);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [history, setHistory] = useState<TelemetryData[]>([]);
  const [deviceState, setDeviceState] = useState<DeviceStateData | null>(null);
  const [recentCommands, setRecentCommands] = useState<CommandOut[]>([]);
  const [lastChecked, setLastChecked] = useState<string>("Chưa kiểm tra");
  const [refreshKey, setRefreshKey] = useState(0);

  // Pump control state
  const [durationSeconds, setDurationSeconds] = useState<number>(10);
  const [activeCommand, setActiveCommand] = useState<CommandOut | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [isSending, setIsSending] = useState<boolean>(false);

  const commandPollRef = useRef<number | null>(null);

  const refresh = useCallback(() => {
    setStatus(emptyStatus);
    setRefreshKey((current) => current + 1);
  }, []);

  // Poll system status, latest telemetry, device state and history
  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;

    const loadData = async () => {
      try {
        const sysStatus = await fetchSystemStatus(signal);
        if (!signal.aborted) {
          setStatus(sysStatus);
          setLastChecked(
            new Intl.DateTimeFormat("vi-VN", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            }).format(new Date()),
          );
        }

        if (sysStatus.backend === "online") {
          const [latest, state, hist, commands] = await Promise.all([
            fetchLatestTelemetry(deviceId, signal).catch(() => null),
            fetchDeviceState(deviceId, signal).catch(() => null),
            fetchTelemetryHistory(deviceId, 20, "asc", signal).catch(() => []),
            fetchRecentCommands(deviceId, 5, signal).catch(() => []),
          ]);

          if (!signal.aborted) {
            setTelemetry(latest);
            setDeviceState(state);
            setHistory(hist);
            setRecentCommands(commands);
          }
        } else {
          if (!signal.aborted) {
            setTelemetry(null);
            setDeviceState(null);
            setHistory([]);
          }
        }
      } catch {
        if (!signal.aborted) {
          setStatus({ backend: "offline", database: "unavailable" });
          setTelemetry(null);
          setDeviceState(null);
          setHistory([]);
        }
      }
    };

    loadData();

    // Regular polling
    const timer = window.setInterval(loadData, POLL_INTERVAL_MS);

    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [deviceId, refreshKey]);

  // Command status polling when there is an active pending command
  useEffect(() => {
    if (!activeCommand || activeCommand.status !== "pending") {
      if (commandPollRef.current) {
        window.clearTimeout(commandPollRef.current);
        commandPollRef.current = null;
      }
      return;
    }

    const commandId = activeCommand.command_id;
    let cancelled = false;

    const poll = async () => {
      try {
        const updated = await fetchCommand(commandId);
        if (cancelled) return;

        setActiveCommand(updated);

        // Update in recent list
        setRecentCommands((prev) =>
          prev.map((cmd) => (cmd.command_id === updated.command_id ? updated : cmd)),
        );

        if (updated.status === "applied") {
          setActionSuccess(
            updated.action === "pump_on"
              ? `Thiết bị đã bật bơm thành công trong ${updated.params.duration_seconds ?? 10} giây!`
              : "Thiết bị đã xác nhận tắt bơm an toàn.",
          );
          setActionError(null);
          // Refresh state to update relay display immediately
          fetchDeviceState(deviceId)
            .then((st) => setDeviceState(st))
            .catch(() => {});
        } else if (updated.status === "rejected") {
          const reasonText =
            (updated.reason && rejectReasonsVi[updated.reason]) ||
            updated.reason ||
            "Lệnh bị thiết bị từ chối.";
          setActionError(`Thiết bị từ chối lệnh: ${reasonText}`);
          setActionSuccess(null);
        } else if (updated.status === "timeout") {
          setActionError("Quá thời hạn phản hồi (timeout). Thiết bị chưa xác nhận.");
          setActionSuccess(null);
        } else {
          // Still pending, schedule next check
          commandPollRef.current = window.setTimeout(poll, COMMAND_POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (!cancelled) {
          setActionError(
            err instanceof Error ? err.message : "Lỗi khi kiểm tra kết quả lệnh.",
          );
        }
      }
    };

    commandPollRef.current = window.setTimeout(poll, COMMAND_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (commandPollRef.current) {
        window.clearTimeout(commandPollRef.current);
      }
    };
  }, [activeCommand, deviceId]);

  // Handle send command
  const handleSendCommand = async (action: CommandAction) => {
    setActionError(null);
    setActionSuccess(null);
    setIsSending(true);

    try {
      const dur = action === "pump_on" ? durationSeconds : undefined;
      const cmd = await sendCommand(deviceId, action, dur);
      setActiveCommand(cmd);
      setRecentCommands((prev) => [cmd, ...prev.filter((c) => c.command_id !== cmd.command_id)].slice(0, 5));
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Không thể gửi lệnh điều khiển. Vui lòng thử lại.",
      );
    } finally {
      setIsSending(false);
    }
  };

  const isBackendOnline = status.backend === "online";
  const isPending = activeCommand?.status === "pending";
  const isPumpCurrentlyOn = deviceState?.relay_state === "on";

  // Data for sparkline
  const soilData = history
    .map((h) => h.soil_moisture_pct)
    .filter((v): v is number => typeof v === "number");
  const tempData = history
    .map((h) => h.temperature_c)
    .filter((v): v is number => typeof v === "number");

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#tong-quan" aria-label="Smart Garden - Tổng quan">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 36 36">
              <path d="M29.6 5.2C20.3 4 13 6.4 9.2 12c-2.4 3.5-2.2 7.7-.7 10.6L4 27.1 6.9 30l4.4-4.4c3.1 1.6 7.2 1.5 10.6-.8 5.4-3.7 7.8-10.5 7.7-19.6Zm-9.8 16.5a8.5 8.5 0 0 1-5.4 1.4l6.1-6.1-2.8-2.8-5.5 5.5c-.2-2 .3-3.9 1.5-5.6 2.4-3.4 6.7-5.2 11.8-5.2-.6 6-2.5 10.6-5.7 12.8Z" />
            </svg>
          </span>
          <span>
            <strong>Smart Garden</strong>
            <small>Vườn thông minh AIoT</small>
          </span>
        </a>
        <div className="header-meta">
          <span className="node-badge" title="Mã trạm đang kết nối">
            Trạm: <strong>{deviceId}</strong>
          </span>
          <span className="environment-badge">Môi trường phát triển</span>
        </div>
      </header>

      <main id="tong-quan">
        <section className="hero" aria-labelledby="dashboard-heading">
          <div>
            <p className="eyebrow">Giám sát & Điều khiển</p>
            <h1 id="dashboard-heading">Khu vườn của bạn</h1>
            <p className="hero-description">
              Theo dõi điều kiện đất, vi khí hậu và điều khiển tưới an toàn theo thời gian thực.
            </p>
          </div>
          <button
            className="refresh-button"
            type="button"
            onClick={refresh}
            aria-label="Kiểm tra và làm mới dữ liệu"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18.4 7.6A8 8 0 1 0 20 14h-2a6 6 0 1 1-1.2-3.6L14 13.2h7V6l-2.6 1.6Z" />
            </svg>
            Làm mới
          </button>
        </section>

        {/* Platform Connectivity Panel */}
        <section className="status-panel" aria-labelledby="connection-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Hạ tầng</p>
              <h2 id="connection-heading">Trạng thái nền tảng</h2>
            </div>
            <p className="last-checked">Lần kiểm tra: {lastChecked}</p>
          </div>

          <div className="status-grid" aria-live="polite">
            <article className="service-status">
              <div className="service-icon api-icon" aria-hidden="true">
                API
              </div>
              <div>
                <p>Backend (FastAPI)</p>
                <strong data-testid="backend-status">
                  <StatusDot state={status.backend} />
                  {backendLabels[status.backend]}
                </strong>
              </div>
            </article>

            <article className="service-status">
              <div className="service-icon database-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M12 2C7 2 3 3.8 3 6v12c0 2.2 4 4 9 4s9-1.8 9-4V6c0-2.2-4-4-9-4Zm0 2c4.3 0 7 1.4 7 2s-2.7 2-7 2-7-1.4-7-2 2.7-2 7-2Zm0 16c-4.3 0-7-1.4-7-2v-2.8c1.7 1.1 4.2 1.8 7 1.8s5.3-.7 7-1.8V18c0 .6-2.7 2-7 2Zm0-5c-4.3 0-7-1.4-7-2v-2.8c1.7 1.1 4.2 1.8 7 1.8s5.3-.7 7-1.8V13c0 .6-2.7 2-7 2Z" />
                </svg>
              </div>
              <div>
                <p>PostgreSQL</p>
                <strong data-testid="database-status">
                  <StatusDot state={status.database} />
                  {databaseLabels[status.database]}
                </strong>
              </div>
            </article>
          </div>
        </section>

        {/* Current Environmental Metrics */}
        <section className="garden-section" aria-labelledby="garden-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Cảm biến vi khí hậu & đất</p>
              <h2 id="garden-heading">Điều kiện hiện tại</h2>
            </div>
            <div className="badges-group">
              {telemetry ? (
                <>
                  <span
                    className={`badge-pill ${
                      telemetry.simulated ? "badge-simulated" : "badge-real"
                    }`}
                  >
                    {telemetry.simulated ? "Dữ liệu mô phỏng" : "Thiết bị thật"}
                  </span>
                  <span
                    className={`badge-pill ${
                      telemetry.stale ? "badge-stale" : "badge-live"
                    }`}
                  >
                    {telemetry.stale ? "Dữ liệu cũ (Stale)" : "Trực tuyến"}
                  </span>
                </>
              ) : (
                <span className="data-badge">Chưa kết nối thiết bị</span>
              )}
            </div>
          </div>

          <div className="metrics-grid">
            {/* Card 1: Nhiệt độ */}
            <article className="metric-card">
              <div className="metric-icon metric-thermometer">
                <SensorIcon type="thermometer" />
              </div>
              <div>
                <p>Nhiệt độ</p>
                {telemetry ? (
                  telemetry.sensor_status.aht20 === "error" ||
                  telemetry.temperature_c === null ? (
                    <strong className="text-warning">Lỗi cảm biến</strong>
                  ) : (
                    <strong className="metric-value">
                      {telemetry.temperature_c.toFixed(1)} <span className="unit">°C</span>
                    </strong>
                  )
                ) : (
                  <strong>Chưa có dữ liệu</strong>
                )}
                <small>Cảm biến AHT20</small>
              </div>
            </article>

            {/* Card 2: Độ ẩm không khí */}
            <article className="metric-card">
              <div className="metric-icon metric-droplet">
                <SensorIcon type="droplet" />
              </div>
              <div>
                <p>Độ ẩm không khí</p>
                {telemetry ? (
                  telemetry.sensor_status.aht20 === "error" ||
                  telemetry.air_humidity_pct === null ? (
                    <strong className="text-warning">Lỗi cảm biến</strong>
                  ) : (
                    <strong className="metric-value">
                      {telemetry.air_humidity_pct.toFixed(1)} <span className="unit">%</span>
                    </strong>
                  )
                ) : (
                  <strong>Chưa có dữ liệu</strong>
                )}
                <small>Cảm biến AHT20</small>
              </div>
            </article>

            {/* Card 3: Độ ẩm đất */}
            <article className="metric-card">
              <div className="metric-icon metric-soil">
                <SensorIcon type="soil" />
              </div>
              <div>
                <p>Độ ẩm đất</p>
                {telemetry ? (
                  telemetry.sensor_status.soil === "error" ||
                  telemetry.soil_moisture_pct === null ? (
                    <strong className="text-warning">Lỗi cảm biến</strong>
                  ) : (
                    <strong className="metric-value">
                      {telemetry.soil_moisture_pct.toFixed(1)} <span className="unit">%</span>
                    </strong>
                  )
                ) : (
                  <strong>Chưa có dữ liệu</strong>
                )}
                <small>Cảm biến điện dung</small>
              </div>
            </article>
          </div>

          {telemetry && (
            <div className="telemetry-meta-row">
              <span>
                Cập nhật lúc: <strong>{formatTime(telemetry.received_at)}</strong>
              </span>
              <span>
                Đồng bộ giờ:{" "}
                <strong>{telemetry.clock_synced ? "Đã đồng bộ UTC" : "Chưa đồng bộ"}</strong>
              </span>
              <span>
                Số bản tin: <strong>#{telemetry.sequence}</strong>
              </span>
            </div>
          )}

          {/* Sparkline Charts */}
          {history.length > 1 && (
            <div className="sparklines-grid">
              <SparklineChart
                data={soilData}
                label="Độ ẩm đất gần đây"
                color="#457b3b"
                unit="%"
              />
              <SparklineChart
                data={tempData}
                label="Nhiệt độ gần đây"
                color="#b85243"
                unit="°C"
              />
            </div>
          )}
        </section>

        {/* Details & Controls */}
        <section className="details-grid">
          {/* Pump Control Card */}
          <article className="detail-card pump-card">
            <div className="card-title-row">
              <div>
                <p className="eyebrow">Thiết bị chấp hành</p>
                <h2>Máy bơm</h2>
              </div>
              {deviceState ? (
                <span
                  className={`relay-pill ${
                    isPumpCurrentlyOn ? "relay-on" : "relay-off"
                  }`}
                >
                  <span className="pulse-indicator" />
                  {isPumpCurrentlyOn ? "ĐANG BẬT" : "ĐANG TẮT"}
                </span>
              ) : (
                <span className="neutral-pill">Chưa có dữ liệu</span>
              )}
            </div>

            <div
              className={`pump-illustration ${isPumpCurrentlyOn ? "pump-active" : ""}`}
              aria-hidden="true"
            >
              <svg viewBox="0 0 64 64">
                <path d="M16 24h33a7 7 0 0 1 7 7v11H16V24Zm5 6v6h28v-5a1 1 0 0 0-1-1H21ZM8 40h8v8H8v-8Zm48-5h5v17h-5V35ZM27 18h12v6H27v-6Zm3-8h6v8h-6v-8Z" />
              </svg>
            </div>

            {/* Device State Details */}
            {deviceState && (
              <div className="device-status-details">
                <div className="detail-item">
                  <small>Chế độ</small>
                  <strong>{deviceState.mode}</strong>
                </div>
                <div className="detail-item">
                  <small>Phiên khởi động (Boot)</small>
                  <strong className="mono-text">{deviceState.boot_id.slice(0, 12)}</strong>
                </div>
                <div className="detail-item">
                  <small>Báo cáo lúc</small>
                  <strong>{formatTime(deviceState.received_at)}</strong>
                </div>
              </div>
            )}

            {/* Duration Selector */}
            <div className="duration-selector">
              <label htmlFor={durationInputId} className="duration-label">
                Thời lượng tưới (giây):
              </label>
              <div className="preset-buttons">
                {durationPresets.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className={`preset-btn ${durationSeconds === preset ? "active" : ""}`}
                    onClick={() => setDurationSeconds(preset)}
                    disabled={!isBackendOnline || isPending}
                  >
                    {preset}s
                  </button>
                ))}
              </div>
              <div className="input-row">
                <input
                  id={durationInputId}
                  type="number"
                  min={MIN_DURATION_SECONDS}
                  max={MAX_DURATION_SECONDS}
                  value={durationSeconds}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val)) {
                      setDurationSeconds(
                        Math.max(
                          MIN_DURATION_SECONDS,
                          Math.min(MAX_DURATION_SECONDS, val),
                        ),
                      );
                    }
                  }}
                  disabled={!isBackendOnline || isPending}
                  aria-label="Số giây tưới"
                />
                <span className="input-unit">giây (1 – 120s)</span>
              </div>
            </div>

            {/* Action Feedback Banners */}
            {actionSuccess && (
              <div className="feedback-banner success-banner" role="status">
                <span className="feedback-icon">✓</span>
                <span>{actionSuccess}</span>
              </div>
            )}

            {actionError && (
              <div className="feedback-banner error-banner" role="alert">
                <span className="feedback-icon">!</span>
                <span>{actionError}</span>
              </div>
            )}

            {/* Active Command Pending Tracker */}
            {isPending && activeCommand && (
              <div className="command-tracker" aria-live="assertive">
                <div className="spinner" />
                <div className="tracker-text">
                  <strong>
                    {activeCommand.action === "pump_on"
                      ? "Đang gửi lệnh bật bơm..."
                      : "Đang gửi lệnh dừng khẩn cấp..."}
                  </strong>
                  <small>Đang đợi ACK và xác nhận từ thiết bị (Status: pending)</small>
                </div>
              </div>
            )}

            {/* Control Buttons */}
            <div className="control-row">
              <button
                type="button"
                className="btn-pump-on"
                onClick={() => handleSendCommand("pump_on")}
                disabled={!isBackendOnline || isPending || isSending}
                title={
                  !isBackendOnline
                    ? "Mất kết nối backend"
                    : isPending
                      ? "Đang có lệnh chờ xử lý"
                      : "Gửi lệnh bật máy bơm"
                }
              >
                Bật bơm
              </button>
              <button
                type="button"
                className="btn-pump-off"
                onClick={() => handleSendCommand("pump_off")}
                disabled={!isBackendOnline || isSending}
                title={
                  !isBackendOnline
                    ? "Mất kết nối backend"
                    : "Gửi lệnh dừng bơm khẩn cấp"
                }
              >
                Tắt bơm
              </button>
            </div>

            {/* Recent Commands Mini List */}
            {recentCommands.length > 0 && (
              <div className="recent-commands">
                <p className="recent-title">Lịch sử lệnh gần đây</p>
                <ul className="command-list">
                  {recentCommands.slice(0, 3).map((cmd) => (
                    <li key={cmd.command_id} className="command-item">
                      <span className="command-action">
                        {cmd.action === "pump_on"
                          ? `Bật ${cmd.params.duration_seconds ?? ""}s`
                          : "Tắt bơm"}
                      </span>
                      <span className="command-time">{formatTime(cmd.created_at)}</span>
                      <span className={`command-status-badge status-${cmd.status}`}>
                        {cmd.status === "applied"
                          ? "Thành công"
                          : cmd.status === "pending"
                            ? "Đang chờ"
                            : cmd.status === "rejected"
                              ? "Từ chối"
                              : "Hết hạn"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>

          {/* Camera Card */}
          <article className="detail-card camera-card">
            <div className="card-title-row">
              <div>
                <p className="eyebrow">Camera khu vườn</p>
                <h2>Ảnh cây gần nhất</h2>
              </div>
              <span className="neutral-pill">Chưa triển khai</span>
            </div>
            <div className="image-placeholder">
              <svg viewBox="0 0 64 64" aria-hidden="true">
                <path d="M52 10H12a6 6 0 0 0-6 6v32a6 6 0 0 0 6 6h40a6 6 0 0 0 6-6V16a6 6 0 0 0-6-6ZM12 16h40v22l-9-9-11 11-6-6-14 14V16Zm0 32 14-14 12 12 5-5 7 7H12Zm8-17a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z" />
              </svg>
              <strong>Chưa có dữ liệu</strong>
              <span>Ảnh sẽ xuất hiện khi ESP32-CAM và module AI được kết nối ở phase sau.</span>
            </div>
          </article>
        </section>
      </main>

      <footer>
        <span>Smart Garden — AIoT Dashboard</span>
        <span>Milestone M1 · Giám sát & Điều khiển an toàn</span>
      </footer>
    </div>
  );
}
