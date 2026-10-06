import { loadEnv } from "vite";
import { spawnSync } from "node:child_process";

async function main() {
  const configured = { ...loadEnv("mobile", process.cwd(), "VITE_"), ...process.env };
  const value = configured.VITE_API_URL?.trim() || configured.VITE_API_BASE_URL?.trim();
  if (!value) {
    throw new Error("Set VITE_API_URL to the backend HTTPS tunnel in .env.mobile.local before building Capacitor.");
  }
  const url = new URL(value);
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("Capacitor requires the direct backend HTTPS origin, without /api, credentials, query or fragment.");
  }
  // A frontend tunnel returns HTML for /health. Verify the destination is FastAPI,
  // so a copied frontend URL cannot silently produce a broken mobile app.
  try {
    const response = await fetch(new URL("/health", url), { signal: AbortSignal.timeout(15000) });
    if (!response.ok || (await response.json()).status !== "ok") throw new Error("Invalid health response");
    const schemaResponse = await fetch(new URL("/openapi.json", url), { signal: AbortSignal.timeout(15000) });
    const schema = await schemaResponse.json();
    if (!schemaResponse.ok || !schema.paths?.["/devices/{device_id}/commands"]?.post) {
      throw new Error("Missing FastAPI command endpoint");
    }
  } catch (error) {
    throw new Error("Backend HTTPS verification failed. Keep the backend tunnel running and use its URL, not the frontend URL.", { cause: error });
  }
  const environment = { ...process.env, VITE_API_URL: url.origin };
  for (const args of [
    ["node_modules/typescript/bin/tsc", "--noEmit"],
    ["node_modules/vite/bin/vite.js", "build", "--mode", "mobile", "--outDir", "dist-mobile"],
  ]) {
    const result = spawnSync(process.execPath, args, { stdio: "inherit", env: environment });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exit(result.status ?? 1);
  }
}

try {
  await main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  if (error instanceof Error && error.cause instanceof Error) console.error(error.cause.message);
  process.exitCode = 1;
}
