import { WeatherApiClient, WeatherApiError } from "@prairie-signal/api-client";
import { describe, expect, it, vi } from "vitest";

describe("WeatherApiClient", () => {
  it("uses same-origin versioned URLs and bounded hourly requests", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ periods: [] }), { status: 200 }),
    );
    const client = new WeatherApiClient({ fetch: fetchMock as typeof fetch });

    await client.getHourly({ latitude: 40.8136, longitude: -96.7026 }, 48);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/weather/hourly?latitude=40.8136&longitude=-96.7026&hours=48",
      expect.objectContaining({ cache: "no-store", method: "GET" }),
    );
  });

  it("surfaces the backend error envelope without losing its code", async () => {
    const client = new WeatherApiClient({
      fetch: async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "nws_unavailable",
              message: "Official source temporarily unavailable.",
              retryable: true,
            },
          }),
          { status: 503 },
        ),
    });

    await expect(
      client.getCurrent({ latitude: 40, longitude: -96 }),
    ).rejects.toMatchObject({
      message: "Official source temporarily unavailable.",
      status: 503,
      code: "nws_unavailable",
    } satisfies Partial<WeatherApiError>);
  });
});
