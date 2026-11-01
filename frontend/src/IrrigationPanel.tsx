import { useEffect, useRef, useState } from "react";
import { irrigationRequest } from "./api";

interface Policy {
  crop: string; stage: string; substrate: string; moisture_stop_pct: number;
  max_pulse_seconds: number; cooldown_seconds: number; daily_budget_seconds: number; evaluation_seconds: number;
}
interface Data {
  profile: { enabled: boolean; policy: Policy; last_status: string } | null;
  decisions: { id: string; created_at: string; status: string; reason: string; proposal: { water: boolean; duration_seconds: number; reason: string } | null; command_status: string | null; command_id: string | null; confirmed_relay_state: string | null }[];
}

export default function IrrigationPanel({ deviceId }: { deviceId: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState<boolean | null>(null);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try { const value = await irrigationRequest<Data>(deviceId, undefined, controller.signal); if (!controller.signal.aborted) { setData(value); setConnected(true); } }
      catch { if (!controller.signal.aborted) setConnected(false); }
    };
    void load();
    const timer = window.setInterval(load, 5000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [deviceId]);
  const submit = async (enabled: boolean) => {
    if (!form.current?.reportValidity()) return;
    const values = new FormData(form.current);
    const policy = Object.fromEntries([...values.entries()].map(([key, value]) => [key, ["crop", "stage", "substrate"].includes(key) ? value : Number(value)]));
    setBusy(true); setError("");
    try { setData(await irrigationRequest<Data>(deviceId, { enabled, policy })); }
    catch (err) { setError(err instanceof Error ? err.message : "Không đổi được chế độ."); }
    finally { setBusy(false); }
  };
  return <section className="detail-card" style={{ marginTop: 24 }} aria-label="Điều phối tưới AI">
    <p className="eyebrow">ĐIỀU PHỐI TƯỚI AI · THỬ NGHIỆM SIMULATOR</p>
    <h2>{connected !== true ? "Chưa xác nhận trạng thái AUTO" : data?.profile?.enabled ? "AUTO đang bật" : "MANUAL — AUTO đang tắt"}</h2>
    {connected === false && <p role="status">Không lấy được trạng thái điều phối. Thông tin bên dưới có thể đã cũ; hãy kiểm tra kết nối backend.</p>}
    <p>AI đánh giá theo chu kỳ; backend kiểm tra giới hạn rồi mới gửi lệnh. Phiên bản này chưa cho phép điều khiển bơm thật. Chế độ thiết bị ở phía trên vẫn là trạng thái thiết bị tự báo.</p>
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
      <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
        <button type="submit" disabled={busy || Boolean(data?.profile?.enabled)}>Bật AUTO (simulator)</button>
        <button type="button" disabled={busy || !data?.profile?.enabled} onClick={async () => {
          setBusy(true); setError("");
          try { setData(await irrigationRequest<Data>(deviceId, { enabled: false, policy: data?.profile?.policy })); }
          catch (err) { setError(err instanceof Error ? err.message : "Không đổi được chế độ."); }
          finally { setBusy(false); }
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
