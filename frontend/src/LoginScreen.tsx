import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ApiError, login } from "./api";
import { setSession, type EndReason } from "./auth";

const endNotices: Record<EndReason, string> = {
  logout: "Bạn đã đăng xuất.",
  expired: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
  unauthorized: "Phiên đăng nhập không còn hợp lệ (hết hạn hoặc đã bị thu hồi). Vui lòng đăng nhập lại.",
};

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      const wait = error.retryAfterSeconds;
      return `${error.message}${wait ? ` (khoảng ${wait} giây)` : ""}`;
    }
    if (error.status === 422) return "Vui lòng nhập tên đăng nhập và mật khẩu.";
    return error.message;
  }
  if (error instanceof TypeError || (error instanceof DOMException && error.name === "AbortError")) {
    return "Không kết nối được backend. Kiểm tra mạng rồi thử lại.";
  }
  return error instanceof Error ? error.message : "Đăng nhập thất bại.";
}

export default function LoginScreen({ endReason }: { endReason: EndReason | null }) {
  const usernameId = useId();
  const passwordId = useId();
  const errorId = useId();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const session = await login(username.trim(), password);
      // The password leaves component state as soon as it has been used.
      if (mounted.current) setPassword("");
      setSession(session);
    } catch (err) {
      if (mounted.current) {
        setError(loginErrorMessage(err));
        setPassword("");
      }
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  };

  return (
    <div className="app-shell login-shell">
      <main className="login-main">
        <section className="detail-card login-card" aria-labelledby="login-heading">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 36 36">
                <path d="M29.6 5.2C20.3 4 13 6.4 9.2 12c-2.4 3.5-2.2 7.7-.7 10.6L4 27.1 6.9 30l4.4-4.4c3.1 1.6 7.2 1.5 10.6-.8 5.4-3.7 7.8-10.5 7.7-19.6Zm-9.8 16.5a8.5 8.5 0 0 1-5.4 1.4l6.1-6.1-2.8-2.8-5.5 5.5c-.2-2 .3-3.9 1.5-5.6 2.4-3.4 6.7-5.2 11.8-5.2-.6 6-2.5 10.6-5.7 12.8Z" />
              </svg>
            </span>
            <span>
              <strong>Smart Garden</strong>
              <small>Vườn thông minh AIoT</small>
            </span>
          </div>
          <h1 id="login-heading">Đăng nhập vận hành</h1>
          <p className="login-hint">
            Cần đăng nhập để xem dữ liệu vườn, dùng trợ lý và điều khiển bơm.
          </p>

          {endReason && (
            <p className="feedback-banner login-notice" role="status">
              {endNotices[endReason]}
            </p>
          )}

          <form className="login-form" onSubmit={submit} noValidate>
            <label htmlFor={usernameId}>Tên đăng nhập</label>
            <input
              id={usernameId}
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={submitting}
              required
              aria-describedby={error ? errorId : undefined}
            />
            <label htmlFor={passwordId}>Mật khẩu</label>
            <input
              id={passwordId}
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={submitting}
              required
              aria-describedby={error ? errorId : undefined}
            />
            {error && (
              <p id={errorId} className="feedback-banner error-banner" role="alert">
                <span className="feedback-icon">!</span>
                <span>{error}</span>
              </p>
            )}
            <button
              type="submit"
              className="btn-pump-on login-submit"
              disabled={submitting || !username.trim() || !password}
            >
              {submitting ? "Đang đăng nhập…" : "Đăng nhập"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
