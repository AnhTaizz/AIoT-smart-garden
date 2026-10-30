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

/** Why the session ended; shown on the login screen. */
export type EndReason = "logout" | "expired" | "unauthorized";

type Listener = (session: AuthSession | null, reason: EndReason | null) => void;

let current: AuthSession | null = null;
const listeners = new Set<Listener>();

export function getSession(): AuthSession | null {
  return current;
}

export function setSession(session: AuthSession): void {
  current = session;
  listeners.forEach((listener) => listener(current, null));
}

export function clearSession(reason: EndReason): void {
  if (current === null) return;
  current = null;
  listeners.forEach((listener) => listener(null, reason));
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Authorization header for the current session, if any. */
export function authHeader(): Record<string, string> {
  return current ? { Authorization: `Bearer ${current.token}` } : {};
}
