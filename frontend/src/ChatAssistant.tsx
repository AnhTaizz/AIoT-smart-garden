import { useEffect, useId, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendChat, type ChatReply, type ChatTurn, type GardenContext } from "./api";
import "./chat.css";

interface Message extends ChatTurn {
  result?: ChatReply;
}

const suggestions = [
  "Với số đo hiện tại, tôi nên chú ý điều gì?",
  "Cây bị vàng lá, tôi nên kiểm tra những gì?",
  "Làm sao biết cây đang thiếu hay thừa nước?",
];

// Keep complete, recent pairs within the server's history budget.
function recentHistory(messages: Message[], question: string): ChatTurn[] {
  const history: ChatTurn[] = [];
  let length = question.length;
  for (let index = messages.length - 2; index >= Math.max(0, messages.length - 12); index -= 2) {
    const pair = messages.slice(index, index + 2);
    const size = pair.reduce((sum, turn) => sum + turn.content.length, 0);
    if (length + size > 16000) break;
    history.unshift(...pair.map(({ role, content }) => ({ role, content })));
    length += size;
  }
  return history;
}

function timeLabel(value: string): string {
  return new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" });
}

function ContextDetails({ context }: { context: GardenContext }) {
  const telemetry = context.telemetry;
  const state = context.state;
  return (
    <details className="chat-context">
      <summary>
        Dữ liệu gửi kèm · {context.status === "disabled" ? "Đã tắt" : context.status === "unavailable" ? "Không khả dụng" : "Xem căn cứ"}
      </summary>
      <div>
        <p>Thiết bị: <strong>{context.device_id}</strong> · Lấy lúc {timeLabel(context.captured_at)} (UTC+7)</p>
        {telemetry && (
          <>
            <p className="chat-context-badges">
              <span>{telemetry.simulated ? "Mô phỏng" : "Số đo thiết bị"}</span>
              <span className={telemetry.stale ? "chat-warning" : ""}>{telemetry.stale ? "Dữ liệu cũ" : "Dữ liệu mới"}</span>
            </p>
            <dl>
              <div><dt>Nhiệt độ</dt><dd>{telemetry.temperature_c === null ? "Không khả dụng" : `${telemetry.temperature_c} °C`}</dd></div>
              <div><dt>Độ ẩm không khí</dt><dd>{telemetry.air_humidity_pct === null ? "Không khả dụng" : `${telemetry.air_humidity_pct} %`}</dd></div>
              <div><dt>Độ ẩm đất</dt><dd>{telemetry.soil_moisture_pct === null ? "Không khả dụng" : `${telemetry.soil_moisture_pct} %`}</dd></div>
            </dl>
            <p>Nhận số đo: {timeLabel(telemetry.received_at)} (UTC+7)</p>
            <p>Cảm biến AHT20: {telemetry.sensor_status.aht20 === "ok" ? "Bình thường" : "Lỗi / chưa rõ"} · Đất: {telemetry.sensor_status.soil === "ok" ? "Bình thường" : "Lỗi / chưa rõ"}</p>
          </>
        )}
        {state && <p>Bơm: {state.relay_state === "on" ? "Bật" : "Tắt"} · {state.mode} · {state.stale ? "Trạng thái cũ" : "Trạng thái mới"}<br />Nhận trạng thái: {timeLabel(state.received_at)} (UTC+7)</p>}
        {context.status === "disabled" && <p>Lượt này chỉ gửi nội dung hội thoại, không gửi số đo vườn.</p>}
        {context.warnings.map((warning) => <p className="chat-warning" key={warning}>{warning}</p>)}
      </div>
    </details>
  );
}

export default function ChatAssistant({ deviceId }: { deviceId: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [includeContext, setIncludeContext] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failed, setFailed] = useState<{ question: string; history: ChatTurn[]; includeContext: boolean } | null>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<AbortController | null>(null);
  const panelId = useId();
  const inputId = useId();

  useEffect(() => () => activeRef.current?.abort(), []);
  useEffect(() => {
    if (open && !pending && !failed) inputRef.current?.focus();
  }, [open, pending, failed]);
  useEffect(() => {
    if (open && scrollRef.current) scrollRef.current.scrollTop = messages.length ? scrollRef.current.scrollHeight : 0;
  }, [messages, pending, error, open]);

  const close = () => {
    setOpen(false);
    launcherRef.current?.focus();
  };

  const send = async (question: string, retry = false) => {
    question = question.trim();
    if (!question || question.length > 4000 || activeRef.current || (failed && !retry)) return;
    const history = retry && failed ? failed.history : recentHistory(messages, question);
    const useContext = retry && failed ? failed.includeContext : includeContext;
    if (!retry) setMessages((previous) => [...previous, { role: "user", content: question }]);
    setDraft("");
    setPending(true);
    setError(null);
    const controller = new AbortController();
    activeRef.current = controller;
    try {
      const result = await sendChat(question, history, deviceId, useContext, controller.signal);
      if (!controller.signal.aborted) {
        setMessages((previous) => [...previous, { role: "assistant", content: result.reply, result }]);
        setFailed(null);
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : "Chưa nhận được câu trả lời. Bạn thử lại nhé.");
        setFailed({ question, history, includeContext: useContext });
      }
    } finally {
      if (activeRef.current === controller) {
        activeRef.current = null;
        setPending(false);
      }
    }
  };

  const reset = () => {
    activeRef.current?.abort();
    activeRef.current = null;
    setMessages([]);
    setFailed(null);
    setDraft("");
    setPending(false);
    setError(null);
    inputRef.current?.focus();
  };

  return (
    <>
      <button className="chat-launcher" ref={launcherRef} aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 11.5a8 8 0 0 1-8 8H7l-5 3V11.5a9 9 0 0 1 18 0Z" stroke="currentColor" strokeWidth="1.7" /><path d="M8 12c0-3 2-5 6-5 0 4-2 6-6 5Zm0 0-2 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
        <span>Trợ lý nông nghiệp</span>
      </button>
      {open && (
        <section id={panelId} role="dialog" aria-label="Trợ lý nông nghiệp Smart-Garden" className="chat-panel" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); close(); } }}>
          <header className="chat-header">
            <div><span className="chat-eyebrow">SMART GARDEN · AI</span><h2>Cùng chăm vườn tốt hơn</h2><p>Tư vấn cây trồng, hiểu số đo vườn</p></div>
            <button type="button" className="chat-icon-button" aria-label="Đóng trò chuyện" onClick={close}>×</button>
          </header>
          <div className="chat-toolbar">
            <label><input type="checkbox" checked={includeContext} disabled={pending || Boolean(failed)} onChange={(event) => setIncludeContext(event.target.checked)} />Gửi kèm dữ liệu vườn</label>
            <button type="button" onClick={reset}>Cuộc trò chuyện mới</button>
          </div>
          <div className="chat-conversation" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="chat-welcome">
                <span className="chat-welcome-mark" aria-hidden="true">✿</span>
                <h3>Vườn của bạn hôm nay thế nào?</h3>
                <p>Mình có thể cùng bạn đọc số đo cảm biến, tìm nguyên nhân cây có triệu chứng và chọn cách chăm sóc phù hợp.</p>
                <p className="chat-hint">Hãy cho mình biết loại cây, giai đoạn phát triển và điều bạn đang quan sát nhé.</p>
                <div className="chat-suggestions">{suggestions.map((question) => <button type="button" key={question} onClick={() => void send(question)}>{question}<span aria-hidden="true">↗</span></button>)}</div>
              </div>
            )}
            <div role="log" aria-label="Nội dung trò chuyện" aria-live="polite" aria-relevant="additions">
              {messages.map((message, index) => (
                <article className={`chat-message chat-message-${message.role}`} key={index}>
                  <span className="chat-speaker">{message.role === "user" ? "Bạn" : "Trợ lý Smart-Garden"}</span>
                  {message.result?.reply_source === "garden_facts" && <p className="chat-facts-note">Lời tư vấn của model chưa khớp dữ liệu. Nội dung dưới đây được tổng hợp từ thông tin hệ thống.</p>}
                  <div className="chat-message-body">
                    {message.role === "assistant" ? <ReactMarkdown skipHtml disallowedElements={["img"]} components={{ a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>{message.content}</ReactMarkdown> : <p>{message.content}</p>}
                  </div>
                  {message.result && <ContextDetails context={message.result.context} />}
                </article>
              ))}
            </div>
            {pending && <div className="chat-thinking" role="status"><span aria-hidden="true" />Đang chuẩn bị lời tư vấn… <small>Model có thể cần đến 2 phút.</small></div>}
            {error && <div className="chat-error" role="alert"><p>{error}</p><button type="button" onClick={() => failed && void send(failed.question, true)}>Thử lại</button><button type="button" onClick={() => { setMessages((previous) => previous.slice(0, -1)); setDraft(failed?.question ?? ""); setFailed(null); setError(null); inputRef.current?.focus(); }}>Sửa câu hỏi</button></div>}
          </div>
          <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); void send(draft); }}>
            <label className="chat-input-label" htmlFor={inputId}>Câu hỏi của bạn</label>
            <div className="chat-input-row">
              <textarea id={inputId} ref={inputRef} rows={2} maxLength={4000} value={draft} placeholder="Hỏi về cây trồng hoặc số đo vườn…" disabled={pending || Boolean(failed)} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(draft); } }} />
              <button type="submit" className="chat-send" disabled={!draft.trim() || pending || Boolean(failed)} aria-label="Gửi câu hỏi"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 7-7 7 7M12 5v15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
            </div>
            <div className="chat-composer-meta"><span>AI hỗ trợ tư vấn · Bạn chủ động điều khiển bơm</span><span>{draft.length}/4000</span></div>
          </form>
        </section>
      )}
    </>
  );
}
