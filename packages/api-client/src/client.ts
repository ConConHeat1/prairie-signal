import type {
  ActiveAlertsResponse,
  CurrentWeatherResponse,
  DailyWeatherResponse,
  HourlyWeatherResponse,
  Location,
  LocationSearchResponse,
  SourcesResponse,
} from "./types";

export interface WeatherApiClientOptions {
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
}

export interface Coordinates {
  latitude: number;
  longitude: number;
}

export class WeatherApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "WeatherApiError";
    this.status = status;
    this.code = code;
  }
}

const DEFAULT_BASE_URL = "/api/v1";

function endpoint(
  baseUrl: string,
  path: string,
  params?: URLSearchParams,
): string {
  const normalizedBase = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const query = params?.toString();
  return `${normalizedBase}${path}${query ? `?${query}` : ""}`;
}

function coordinateParams(location: Coordinates): URLSearchParams {
  return new URLSearchParams({
    latitude: String(location.latitude),
    longitude: String(location.longitude),
  });
}

async function responseMessage(
  response: Response,
): Promise<{ message: string; code: string | null }> {
  try {
    const body = (await response.json()) as {
      error?: { message?: string; code?: string; retryable?: boolean };
      detail?: string | { message?: string; code?: string };
      message?: string;
      code?: string;
    };
    if (body.error) {
      return {
        message:
          body.error.message ?? `Weather service returned ${response.status}.`,
        code: body.error.code ?? null,
      };
    }
    if (typeof body.detail === "string") {
      return { message: body.detail, code: body.code ?? null };
    }
    if (body.detail && typeof body.detail === "object") {
      return {
        message:
          body.detail.message ?? `Weather service returned ${response.status}.`,
        code: body.detail.code ?? null,
      };
    }
    return {
      message: body.message ?? `Weather service returned ${response.status}.`,
      code: body.code ?? null,
    };
  } catch {
    return {
      message: `Weather service returned ${response.status}.`,
      code: null,
    };
  }
}

export class WeatherApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(options: WeatherApiClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  private async get<T>(
    path: string,
    params?: URLSearchParams,
    signal?: AbortSignal,
  ): Promise<T> {
    let response: Response;
    try {
      response = await this.fetchImpl(endpoint(this.baseUrl, path, params), {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw error;
      }
      throw new WeatherApiError(
        "The weather service could not be reached.",
        0,
        "network_error",
      );
    }

    if (!response.ok) {
      const { message, code } = await responseMessage(response);
      throw new WeatherApiError(message, response.status, code);
    }

    try {
      return (await response.json()) as T;
    } catch {
      throw new WeatherApiError(
        "The weather service returned an unreadable response.",
        response.status,
        "invalid_json",
      );
    }
  }

  searchLocations(
    query: string,
    limit = 8,
    signal?: AbortSignal,
  ): Promise<LocationSearchResponse> {
    const normalized = query.trim();
    if (!normalized) {
      return Promise.resolve({
        results: [],
        query_kind: "city",
        region_limit_km: 256,
      });
    }
    return this.get<LocationSearchResponse>(
      "/location/search",
      new URLSearchParams({ q: normalized, limit: String(limit) }),
      signal,
    );
  }

  getCurrent(
    location: Coordinates,
    signal?: AbortSignal,
  ): Promise<CurrentWeatherResponse> {
    return this.get<CurrentWeatherResponse>(
      "/weather/current",
      coordinateParams(location),
      signal,
    );
  }

  getHourly(
    location: Coordinates,
    hours = 48,
    signal?: AbortSignal,
  ): Promise<HourlyWeatherResponse> {
    const params = coordinateParams(location);
    params.set("hours", String(hours));
    return this.get<HourlyWeatherResponse>("/weather/hourly", params, signal);
  }

  getDaily(
    location: Coordinates,
    signal?: AbortSignal,
  ): Promise<DailyWeatherResponse> {
    return this.get<DailyWeatherResponse>(
      "/weather/daily",
      coordinateParams(location),
      signal,
    );
  }

  getActiveAlerts(
    location: Coordinates,
    signal?: AbortSignal,
  ): Promise<ActiveAlertsResponse> {
    return this.get<ActiveAlertsResponse>(
      "/alerts/active",
      coordinateParams(location),
      signal,
    );
  }

  getSources(signal?: AbortSignal): Promise<SourcesResponse> {
    return this.get<SourcesResponse>("/sources", undefined, signal);
  }
}

export const weatherApi = new WeatherApiClient();

export function locationCoordinates(location: Location): Coordinates {
  return { latitude: location.latitude, longitude: location.longitude };
}
