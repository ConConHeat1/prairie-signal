import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "../app/api/v1/[...path]/route";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("same-origin API proxy", () => {
  it("resolves the internal API at request time and preserves the query string", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000/");
    const upstream = new Response('{"status":"ok"}', {
      status: 200,
      headers: {
        "cache-control": "max-age=30",
        "content-type": "application/json",
        "x-internal-detail": "do-not-forward",
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(upstream);
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("http://localhost/api/v1/health?probe=1"),
      { params: Promise.resolve({ path: ["health"] }) },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      new URL("http://api:8000/api/v1/health?probe=1"),
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("max-age=30");
    expect(response.headers.has("x-internal-detail")).toBe(false);
    await expect(response.json()).resolves.toEqual({ status: "ok" });
  });

  it("returns a safe typed error when the internal API cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("connection refused")),
    );

    const response = await GET(
      new NextRequest("http://localhost/api/v1/weather/current"),
      { params: Promise.resolve({ path: ["weather", "current"] }) },
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: {
        code: "api_unavailable",
        message: "The weather service is temporarily unavailable.",
        retryable: true,
      },
    });
  });
});
