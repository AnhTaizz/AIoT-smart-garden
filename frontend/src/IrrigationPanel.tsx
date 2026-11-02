import { useEffect, useRef, useState } from "react";
import { irrigationRequest } from "./api";

interface Policy { crop: string; stage: string; substrate: string; moisture_stop_pct: number; max_pulse_seconds: number; cooldown_seconds: number; daily_budget_seconds: number; evaluation_seconds: number; force_water_below_pct?: number | null; }
interface Data { execution_scope: "simulator_only" | "real_device"; profile: { enabled: boolean; policy: Policy; last_status: string } | null; decisions: { id: string; created_at: string; status: string; reason: string; proposal: { water: boolean; duration_seconds: number; reason: string } | null; decision_source?: "rule" | "ai" | null; command_status: string | null; command_id: string | null; confirmed_relay_state: string | null }[]; }

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
    const controller = new AbortController(); generation.current += 1; actionPending.current = false;
    setData(null); setConnected(null); setRealConfirmed(false); setError(""); setBusy(false);
    const load = async () => { if (actionPending.current) return; const current = generation.current; try { const value = await irrigationRequest<Data>(deviceId, undefined, controller.signal); if (!controller.signal.aborted && current === generation.current) { setData(value); setConnected(true); } } catch { if (!controller.signal.aborted && current === generation.current) setConnected(false); } };
    void load(); const timer = window.setInterval(load, 5000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [deviceId]);

  const realDevice = data?.execution_scope === "real_device";
  const knownScope = realDevice || data?.execution_scope === "simulator_only";
  const autoEnabled = Boolean(data?.profile?.enabled);
  const scopeLabel = realDevice ? "ESP32 THẬT" : knownScope ? "SIMULATOR" : "CHƯA XÁC NHẬN THIẾT BỊ";
  const statusLabel = connected !== true ? "Chưa xác nhận trạng thái AUTO" : autoEnabled ? "AUTO đang bật" : "MANUAL — AUTO đang tắt";
  const saveProfile = async (enabled: boolean) => {
    if (enabled && (connected !== true || !knownScope || (realDevice && !realConfirmed))) return;
    if (enabled && !form.current?.reportValidity()) return;
    const values = new FormData(form.current ?? undefined);
    const policy = enabled ? Object.fromEntries([...values.entries()].map(([key, value]) => [key, ["crop", "stage", "substrate"].includes(key) ? value : key === "force_water_below_pct" && value === "" ? null : Number(value)])) : data?.profile?.policy;
    setBusy(true); setError(""); actionPending.current = true; const current = ++generation.current;
    try { const value = await irrigationRequest<Data>(deviceId, { enabled, policy }); if (current === generation.current) { setData(value); setRealConfirmed(false); } }
    catch (err) { if (current === generation.current) setError(err instanceof Error ? err.message : "Không thể đổi chế độ."); }
    finally { if (current === generation.current) { setBusy(false); actionPending.current = false; } }
  };

  return <section className="detail-card irrigation-card" aria-label="Điều phối tưới AI">
    <div className="irrigation-header"><div className="irrigation-heading"><span className="irrigation-icon" aria-hidden="true">⌁</span><div><p className="eyebrow">ĐIỀU PHỐI TƯỚI AI · {scopeLabel}</p><h2>{statusLabel}</h2></div></div><span className={`irrigation-state ${autoEnabled ? "is-auto" : "is-manual"}`}><i />{autoEnabled ? "AUTO" : "MANUAL"}</span></div>
    <p className="irrigation-summary">AI đọc tín hiệu cảm biến, đề xuất lịch tưới an toàn; ESP32 là nơi xác nhận và thực thi lệnh.</p>
    {connected === false && <p className="irrigation-warning" role="status">Chưa kết nối được backend. Bảng cấu hình vẫn hiển thị nhưng chưa thể áp dụng.</p>}
    <form ref={form} className="irrigation-form" onSubmit={(event) => { event.preventDefault(); void saveProfile(true); }} key={deviceId + Boolean(data?.profile)}>
      <fieldset className="irrigation-settings" disabled={busy || autoEnabled}><legend>Cấu hình chu trình tưới</legend><p className="irrigation-settings-note">Thiết lập phù hợp với cây và giá thể đang theo dõi.</p>
        {([['crop', 'Cây trồng'], ['stage', 'Giai đoạn'], ['substrate', 'Giá thể']] as const).map(([key, title]) => <label key={key}>{title}<input name={key} required maxLength={120} defaultValue={data?.profile?.policy[key] ?? ""} /></label>)}
        {([['moisture_stop_pct', 'Ngừng tưới khi ẩm đất (%)', 0, 100], ['max_pulse_seconds', 'Tối đa mỗi lượt (giây)', 1, 60], ['cooldown_seconds', 'Nghỉ giữa hai lượt (giây)', 300, 86400], ['daily_budget_seconds', 'Ngân sách AUTO / 24 giờ', 1, 600], ['evaluation_seconds', 'Chu kỳ đánh giá (giây)', 30, 3600]] as const).map(([key, title, min, max]) => <label key={key}>{title}<input name={key} type="number" required min={min} max={max} step={key === "moisture_stop_pct" ? "any" : 1} defaultValue={data?.profile?.policy[key] ?? ""} /></label>)}
        <label className="irrigation-threshold">Luật ngưỡng: tưới 10 giây khi ẩm đất dưới (%)<input name="force_water_below_pct" type="number" min={0} max={100} step="any" defaultValue={data?.profile?.policy.force_water_below_pct ?? ""} /><small>Để trống để tắt luật ngưỡng.</small></label>
      </fieldset>
      {realDevice && !autoEnabled && <label className="irrigation-confirm"><input type="checkbox" checked={realConfirmed} disabled={busy} onChange={(event) => setRealConfirmed(event.target.checked)} />Đã hiệu chuẩn cảm biến và sẵn sàng giám sát ESP32 thật.</label>}
      <div className="irrigation-actions"><button className="irrigation-enable" type="submit" disabled={busy || connected !== true || !knownScope || autoEnabled || (realDevice && !realConfirmed)}>{realDevice ? "Bật AUTO (ESP32 thật)" : knownScope ? "Bật AUTO (simulator)" : "Bật AUTO"}</button><button className="irrigation-disable" type="button" disabled={busy || !autoEnabled} onClick={() => void saveProfile(false)}>Chuyển MANUAL và gửi STOP</button></div>
    </form>
    {error && <p className="irrigation-warning" role="alert">{error}</p>}
    <div className="irrigation-status"><span>Trạng thái điều phối</span><strong>{data?.profile?.last_status ?? "Chưa cấu hình"}</strong></div>
    <div className="irrigation-history"><div><p className="eyebrow">Nhật ký gần đây</p><h3>Quyết định tưới</h3></div>{!data?.decisions?.length && <p className="irrigation-empty">Chưa có quyết định AI hoặc luật ngưỡng.</p>}<ul>{data?.decisions?.slice(0, 5).map((item) => <li key={item.id}><span className={`decision-badge decision-${item.status}`}>{item.status}</span><div><strong>{item.proposal ? `${item.decision_source === "rule" ? "Luật ngưỡng" : "AI"}: ${item.proposal.water ? `Đề xuất tưới ${item.proposal.duration_seconds}s` : "Không tưới"} — ${item.proposal.reason}` : "Đang đánh giá"}</strong><p>{item.reason}</p><small>{new Date(item.created_at).toLocaleString("vi-VN")}{item.command_status ? ` · ${item.command_status}` : ""}{item.command_id ? ` · Relay xác nhận: ${item.confirmed_relay_state ?? "Chưa có"}` : ""}</small></div></li>)}</ul></div>
  </section>;
}
