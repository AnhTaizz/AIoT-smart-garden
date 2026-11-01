import { useEffect, useRef, useState } from "react";
import { irrigationRequest } from "./api";

interface Policy {
  crop: string; stage: string; substrate: string; moisture_stop_pct: number;
  max_pulse_seconds: number; cooldown_seconds: number; daily_budget_seconds: number; evaluation_seconds: number;
}
interface Data {
  execution_scope: "simulator_only" | "real_device";
  profile: { enabled: boolean; policy: Policy; last_status: string } | null;
  decisions: { id: string; created_at: string; status: string; reason: string; proposal: { water: boolean; duration_seconds: number; reason: string } | null; command_status: string | null; command_id: string | null; confirmed_relay_state: string | null }[];
}

export default function IrrigationPanel({ deviceId }: { deviceId: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [realConfirmed, setRealConfirmed] = useState(false);
  const generation = useRef(0);
  const actionPending = useRef(false);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    generation.current += 1;
    actionPending.current = false;
    setData(null); setConnected(null); setRealConfirmed(false); setError(""); setBusy(false);
    const load = async () => {
      if (actionPending.current) return;
      const current = generation.current;
      try { const value = await irrigationRequest<Data>(deviceId, undefined, controller.signal); if (!controller.signal.aborted && current === generation.current) { setData(value); setConnected(true); } }
      catch { if (!controller.signal.aborted && current === generation.current) setConnected(false); }
    };
    void load();
    const timer = window.setInterval(load, 5000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [deviceId]);
  const realDevice = data?.execution_scope === "real_device";
  const knownScope = realDevice || data?.execution_scope === "simulator_only";
  const submit = async (enabled: boolean) => {
    if (enabled && (connected !== true || !knownScope || (realDevice && !realConfirmed))) return;
    if (!form.current?.reportValidity()) return;
    const values = new FormData(form.current);
    const policy = Object.fromEntries([...values.entries()].map(([key, value]) => [key, ["crop", "stage", "substrate"].includes(key) ? value : Number(value)]));
    setBusy(true); setError("");
    actionPending.current = true;
    const current = ++generation.current;
    try { const value = await irrigationRequest<Data>(deviceId, { enabled, policy }); if (current === generation.current) { setData(value); setRealConfirmed(false); } }
    catch (err) { if (current === generation.current) setError(err instanceof Error ? err.message : "Không đổi được chế độ."); }
    finally { if (current === generation.current) { setBusy(false); actionPending.current = false; } }
  };
  return <section className="detail-card" style={{ marginTop: 24 }} aria-label="Điều phối tưới AI">
    <p className="eyebrow">ĐIỀU PHỐI TƯỚI AI · {realDevice ? "ESP32 THẬT" : knownScope ? "SIMULATOR" : "CHƯA XÁC NHẬN THIẾT BỊ"}</p>
    <h2>{connected !== true ? "Chưa xác nhận trạng thái AUTO" : data?.profile?.enabled ? "AUTO đang bật" : "MANUAL — AUTO đang tắt"}</h2>
    {connected === false && <p role="status">Không lấy được trạng thái điều phối. Thông tin bên dưới có thể đã cũ; hãy kiểm tra kết nối backend.</p>}
    <p>AI quyết định tưới trên server; ESP32 đọc cảm biến, thực thi lệnh và tự giới hạn thời gian bơm. {realDevice ? "AUTO có thể bật bơm thật khi bạn chủ động cho phép; cần giám sát trong phiên thử nghiệm." : "AUTO cho ESP32 thật cần được cấp quyền riêng trên server; không dùng simulator cùng ID với board."} Chế độ thiết bị vẫn là trạng thái thiết bị tự báo.</p>
    <form ref={form} onSubmit={event => { event.preventDefault(); void submit(true); }} key={deviceId + Boolean(data?.profile)}>
      <fieldset disabled={busy || data?.profile?.enabled} style={{ border: "1px solid #dbe4df", borderRadius: 12, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 14, padding: 16 }}>
        <legend>Cấu hình cho cây/giá thể đang thử nghiệm</legend>
        {([['crop', 'Cây trồng'], ['stage', 'Giai đoạn'], ['substrate', 'Giá thể']] as const).map(([key, title]) => <label key={key}>{title}<input name={key} required maxLength={120} defaultValue={data?.profile?.policy[key] ?? ""} style={{ width: "100%" }} /></label>)}
        {([
          ['moisture_stop_pct', 'Ngừng tưới từ độ ẩm đất (%)', 0, 100],
          ['max_pulse_seconds', 'Tối đa mỗi lần (giây)', 1, 60],
          ['cooldown_seconds', 'Nghỉ giữa hai lần (giây)', 300, 86400],
          ['daily_budget_seconds', 'Ngân sách AUTO / 24h (giây)', 1, 600],
          ['evaluation_seconds', 'Chu kỳ đánh giá (giây)', 30, 3600],
        ] as const).map(([key, title, min, max]) => <label key={key}>{title}<input name={key} type="number" required min={min} max={max} step={key === 'moisture_stop_pct' ? 'any' : 1} defaultValue={data?.profile?.policy[key] ?? ""} style={{ width: "100%" }} /></label>)}
      </fieldset>
      {realDevice && !data?.profile?.enabled && <label style={{ display: "block", marginTop: 16 }}>
        <input type="checkbox" checked={realConfirmed} disabled={busy} onChange={event => setRealConfirmed(event.target.checked)} />
        Đã hiệu chuẩn cảm biến, kiểm tra OFF với adapter bơm rút và sẵn sàng giám sát ESP32 thật.
      </label>}
      <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
        <button type="submit" disabled={busy || connected !== true || !knownScope || Boolean(data?.profile?.enabled) || (realDevice && !realConfirmed)}>{realDevice ? "Bật AUTO (ESP32 thật)" : knownScope ? "Bật AUTO (simulator)" : "Bật AUTO"}</button>
        <button type="button" disabled={busy || !data?.profile?.enabled} onClick={async () => {
          setBusy(true); setError("");
          actionPending.current = true;
          const current = ++generation.current;
          try { const value = await irrigationRequest<Data>(deviceId, { enabled: false, policy: data?.profile?.policy }); if (current === generation.current) { setData(value); setRealConfirmed(false); } }
          catch (err) { if (current === generation.current) setError(err instanceof Error ? err.message : "Không đổi được chế độ."); }
          finally { if (current === generation.current) { setBusy(false); actionPending.current = false; } }
        }}>Chuyển MANUAL và gửi STOP</button>
      </div>
    </form>
    {error && <p role="alert">{error}</p>}
    <p>Trạng thái điều phối: {data?.profile?.last_status ?? "Chưa cấu hình"}. Mỗi quyết định hợp lệ vẫn có thể bị chặn bởi thời gian nghỉ hoặc ngân sách tưới.</p>
    <h3>Quyết định và kết quả thực hiện gần đây</h3>
    {!data?.decisions?.length && <p>Chưa có quyết định AI.</p>}
    <ul>{data?.decisions?.slice(0, 5).map(item => <li key={item.id} style={{ marginBottom: 12 }}>
      <strong>{item.status}</strong> · {new Date(item.created_at).toLocaleString("vi-VN")}<br />
      {item.reason}<br />
      {item.proposal && <>AI: {item.proposal.water ? `Đề xuất tưới ${item.proposal.duration_seconds}s` : "Không tưới"} — {item.proposal.reason}<br /></>}
      {item.command_id && <>Lệnh: {item.command_id} · {item.command_status ?? "Chưa xác nhận"} · Relay xác nhận: {item.confirmed_relay_state ?? "Chưa có"}</>}
    </li>)}</ul>
  </section>;
}
