import { useCallback, useEffect, useState } from "react";
import {
  fetchSystemStatus,
  type BackendStatus,
  type DatabaseStatus,
  type SystemStatus,
} from "./api";

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

const metricCards = [
  {
    title: "Nhiệt độ",
    source: "Cảm biến AHT20",
    icon: "thermometer",
  },
  {
    title: "Độ ẩm không khí",
    source: "Cảm biến AHT20",
    icon: "droplet",
  },
  {
    title: "Độ ẩm đất",
    source: "Cảm biến điện dung",
    icon: "soil",
  },
] as const;

function StatusDot({ state }: { state: BackendStatus | DatabaseStatus }) {
  return <span aria-hidden="true" className={`status-dot status-${state}`} />;
}

function SensorIcon({ type }: { type: (typeof metricCards)[number]["icon"] }) {
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

export default function App() {
  const [status, setStatus] = useState<SystemStatus>(emptyStatus);
  const [lastChecked, setLastChecked] = useState<string>("Chưa kiểm tra");
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => {
    setStatus(emptyStatus);
    setRefreshKey((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    fetchSystemStatus(controller.signal).then((nextStatus) => {
      if (!controller.signal.aborted) {
        setStatus(nextStatus);
        setLastChecked(
          new Intl.DateTimeFormat("vi-VN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }).format(new Date()),
        );
      }
    });

    return () => controller.abort();
  }, [refreshKey]);

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
            <small>Vườn thông minh</small>
          </span>
        </a>
        <span className="environment-badge">Môi trường phát triển</span>
      </header>

      <main id="tong-quan">
        <section className="hero" aria-labelledby="dashboard-heading">
          <div>
            <p className="eyebrow">Tổng quan hệ thống</p>
            <h1 id="dashboard-heading">Khu vườn của bạn</h1>
            <p className="hero-description">
              Theo dõi kết nối nền tảng và dữ liệu khu vực trồng tại một nơi.
            </p>
          </div>
          <button className="refresh-button" type="button" onClick={refresh}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18.4 7.6A8 8 0 1 0 20 14h-2a6 6 0 1 1-1.2-3.6L14 13.2h7V6l-2.6 1.6Z" />
            </svg>
            Kiểm tra lại
          </button>
        </section>

        <section className="status-panel" aria-labelledby="connection-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Kết nối</p>
              <h2 id="connection-heading">Trạng thái nền tảng</h2>
            </div>
            <p className="last-checked">Lần kiểm tra: {lastChecked}</p>
          </div>

          <div className="status-grid" aria-live="polite">
            <article className="service-status">
              <div className="service-icon api-icon" aria-hidden="true">API</div>
              <div>
                <p>Backend</p>
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

        <section className="garden-section" aria-labelledby="garden-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Khu vực trồng</p>
              <h2 id="garden-heading">Điều kiện hiện tại</h2>
            </div>
            <span className="data-badge">Chưa kết nối thiết bị</span>
          </div>

          <div className="metrics-grid">
            {metricCards.map((metric) => (
              <article className="metric-card" key={metric.title}>
                <div className={`metric-icon metric-${metric.icon}`}>
                  <SensorIcon type={metric.icon} />
                </div>
                <div>
                  <p>{metric.title}</p>
                  <strong>Chưa có dữ liệu</strong>
                  <small>{metric.source}</small>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="details-grid">
          <article className="detail-card pump-card">
            <div className="card-title-row">
              <div>
                <p className="eyebrow">Thiết bị chấp hành</p>
                <h2>Máy bơm</h2>
              </div>
              <span className="neutral-pill">Chưa có dữ liệu</span>
            </div>
            <div className="pump-illustration" aria-hidden="true">
              <svg viewBox="0 0 64 64">
                <path d="M16 24h33a7 7 0 0 1 7 7v11H16V24Zm5 6v6h28v-5a1 1 0 0 0-1-1H21ZM8 40h8v8H8v-8Zm48-5h5v17h-5V35ZM27 18h12v6H27v-6Zm3-8h6v8h-6v-8Z" />
              </svg>
            </div>
            <p className="helper-text">
              Điều khiển bơm sẽ khả dụng sau khi giao tiếp thiết bị được triển khai và kiểm tra an toàn.
            </p>
            <div className="control-row">
              <button type="button" disabled title="Chức năng chưa được triển khai">
                Bật bơm
              </button>
              <button type="button" disabled title="Chức năng chưa được triển khai">
                Tắt bơm
              </button>
            </div>
          </article>

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
              <span>Ảnh sẽ xuất hiện khi camera được kết nối.</span>
            </div>
          </article>
        </section>
      </main>

      <footer>
        <span>Smart Garden</span>
        <span>Dashboard giám sát · TASK-000C</span>
      </footer>
    </div>
  );
}

