import { describe, expect, it } from "vitest";
import { resolveApiBaseUrl } from "./apiConfig";

describe("Web API configuration", () => {
  it("keeps the same-origin proxy for local and tunneled Web", () => {
    expect(resolveApiBaseUrl({}, "http:")).toBe("/api");
    expect(resolveApiBaseUrl({}, "https:")).toBe("/api");
  });
  it("accepts a public HTTPS API, preserving the existing env alias", () => {
    expect(resolveApiBaseUrl({VITE_API_URL: " https://api.example.com/ "}, "https:"))
      .toBe("https://api.example.com");
    expect(resolveApiBaseUrl({VITE_API_BASE_URL: "https://api.example.com/"}, "https:"))
      .toBe("https://api.example.com");
    expect(resolveApiBaseUrl({VITE_API_URL: "https://new.example.com", VITE_API_BASE_URL: "/api"}, "https:"))
      .toBe("https://new.example.com");
  });
  it("allows local HTTP development but rejects HTTPS mixed content", () => {
    expect(resolveApiBaseUrl({VITE_API_URL: "http://localhost:8000/"}, "http:"))
      .toBe("http://localhost:8000");
    expect(() => resolveApiBaseUrl({VITE_API_URL: "http://localhost:8000"}, "https:"))
      .toThrow("HTTPS API");
  });
  it("rejects unsafe or malformed base URLs", () => {
    for (const value of ["//other.example.com", "ftp://api.example.com", "https://user:pass@api.example.com", "https://api.example.com?q=x", "https://api.example.com#x"]) {
      expect(() => resolveApiBaseUrl({VITE_API_URL: value}, "https:")).toThrow();
    }
  });
});

describe("Native API configuration", () => {
  it("uses the public backend HTTPS origin directly", () => {
    expect(resolveApiBaseUrl({VITE_API_URL: "https://api.example.com/"}, "capacitor:", true))
      .toBe("https://api.example.com");
  });
  it("rejects a missing URL, local/LAN URLs, HTTP and the frontend /api proxy", () => {
    for (const value of ["", "/api", "http://api.example.com", "https://localhost", "https://127.0.0.1", "https://192.168.1.2", "https://10.0.0.2", "https://172.16.0.2", "https://[::1]", "https://api.example.com/api"]) {
      expect(() => resolveApiBaseUrl({VITE_API_URL: value}, "https:", true)).toThrow();
    }
  });
});
