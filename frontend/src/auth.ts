/**
 * In-memory operator session, shared by Web and Capacitor Android.
 *
 * The bearer token lives only in this module's memory: it is never written to
 * localStorage, sessionStorage, cookies or Capacitor Preferences, and no token
 * is built into the app. Reloading the page or restarting the app means
 * logging in again. The password is never stored anywhere.
 */

export type Role = "operator" | "viewer";

export interface AuthSession {
  token: string;
  username: string;
  role: Role;
  /** Epoch milliseconds from the server's expires_at. */
  expiresAt: number;
}

/**
 * Why the session ended; shown on the login screen.
 * - logout: the server confirmed the token is revoked (or already invalid).
 * - logout_unconfirmed: removed on this device only; the revoke request
 *   failed, so the token may still be valid on the server until it expires.
 */
export type EndReason = "logout" | "logout_unconfirmed" | "expired" | "unauthorized";

export interface SessionEnd {
  reason: EndReason;
  /** Server expiry of the ended token (epoch ms), for logout_unconfirmed. */
  serverExpiresAt?: number;
}

type Listener = (session: AuthSession | null, end: SessionEnd | null) => void;

let current: AuthSession | null = null;
const listeners = new Set<Listener>();

export function getSession(): AuthSession | null {
  return current;
}

export function setSession(session: AuthSession): void {
  current = session;
  listeners.forEach((listener) => listener(current, null));
}

export function clearSession(reason: EndReason, serverExpiresAt?: number): void {
  if (current === null) return;
  current = null;
  const end: SessionEnd = { reason, serverExpiresAt };
  listeners.forEach((listener) => listener(null, end));
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Authorization header for the current session, if any. */
export function authHeader(): Record<string, string> {
  return current ? { Authorization: `Bearer ${current.token}` } : {};
}
