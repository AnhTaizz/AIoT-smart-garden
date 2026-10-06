export interface ApiEnvironment {
  VITE_API_URL?: string;
  VITE_API_BASE_URL?: string;
}

export function resolveApiBaseUrl(
  environment: ApiEnvironment,
  pageProtocol: string,
  native = false,
): string {
  const configured = environment.VITE_API_URL?.trim()
    || environment.VITE_API_BASE_URL?.trim()
    || "/api";
  if (configured.startsWith("/") && !configured.startsWith("//")) {
    if (native) throw new Error("Capacitor requires a configured backend HTTPS URL.");
    return configured.replace(/\/+$/, "");
  }
  const url = new URL(configured);
  if (native) {
    const host = url.hostname.toLowerCase();
    const privateHost = host === "localhost" || host.endsWith(".localhost")
      || host.endsWith(".local") || host === "[::1]" || host.startsWith("[fc")
      || host.startsWith("[fd") || host.startsWith("[fe80:")
      || /^(0\.|127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host);
    if (url.protocol !== "https:" || privateHost || url.pathname !== "/") {
      throw new Error("Capacitor must call the public backend HTTPS origin directly.");
    }
  }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password
      || url.search || url.hash) {
    throw new Error("API URL must be an HTTP(S) base URL without credentials, query or fragment.");
  }
  if (pageProtocol === "https:" && url.protocol !== "https:") {
    throw new Error("An HTTPS dashboard requires an HTTPS API URL.");
  }
  return url.toString().replace(/\/+$/, "");
}
