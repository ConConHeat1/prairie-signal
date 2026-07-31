import type {
  ActiveAlertsResponse,
  CurrentWeatherResponse,
  DailyWeatherResponse,
  HourlyWeatherResponse,
  Location,
  LocationSearchResponse,
  OfficialAlert,
  ResponseMetadata,
} from "@prairie-signal/api-client";

export const lincoln: Location = {
  id: "place:ne:lincoln",
  name: "Lincoln",
  region: "Nebraska",
  country: "US",
  latitude: 40.8136,
  longitude: -96.7026,
  timezone: "America/Chicago",
  kind: "city",
  label: "Lincoln, Nebraska",
};

export const omaha: Location = {
  id: "zcta:68102",
  name: "68102",
  region: "Nebraska",
  country: "US",
  latitude: 41.2647,
  longitude: -95.9345,
  timezone: "America/Chicago",
  kind: "zcta",
  label: "68102 ZIP approximation, Nebraska",
};

export function metadata(
  freshness: ResponseMetadata["freshness"] = "fresh",
  overrides: Partial<ResponseMetadata> = {},
): ResponseMetadata {
  return {
    source_time: "2026-07-30T20:00:00Z",
    fetched_at: "2026-07-30T20:03:00Z",
    processed_at: "2026-07-30T20:03:01Z",
    valid_from: "2026-07-30T20:00:00Z",
    valid_to: "2026-08-06T20:00:00Z",
    units: {
      temperature: "degC",
      wind_speed: "km/h",
    },
    attribution: {
      name: "National Weather Service",
      url: "https://www.weather.gov/",
    },
    freshness,
    quality: "verified",
    confidence: null,
    pipeline_version: "phase1-test",
    warnings: [],
    from_cache: freshness !== "fresh",
    stale_fallback: freshness === "stale",
    ...overrides,
  };
}

export const currentResponse: CurrentWeatherResponse = {
  location: lincoln,
  current: {
    temperature_c: 22,
    apparent_temperature_c: 22.5,
    dewpoint_c: 13,
    relative_humidity_pct: 55,
    wind_speed_kph: 16,
    wind_gust_kph: 25,
    wind_direction_deg: 180,
    pressure_hpa: 1013.2,
    visibility_km: 16.1,
    text_description: "Partly Cloudy",
    icon_url: null,
    observed_at: "2026-07-30T20:00:00Z",
  },
  station: {
    id: "KLNK",
    name: "Lincoln Airport",
    latitude: 40.8509,
    longitude: -96.7591,
    distance_km: 6.7,
    observed_at: "2026-07-30T20:00:00Z",
  },
  meta: metadata(),
};

export const hourlyResponse: HourlyWeatherResponse = {
  location: lincoln,
  periods: [
    {
      start_time: "2026-07-30T20:00:00Z",
      end_time: "2026-07-30T21:00:00Z",
      is_daytime: true,
      temperature_c: 22,
      dewpoint_c: 13,
      relative_humidity_pct: 55,
      probability_of_precipitation_pct: 10,
      wind_speed_kph: 16,
      wind_gust_kph: 25,
      wind_direction: "S",
      wind_direction_deg: 180,
      short_forecast: "Partly Sunny",
      icon_url: null,
    },
    {
      start_time: "2026-07-30T21:00:00Z",
      end_time: "2026-07-30T22:00:00Z",
      is_daytime: true,
      temperature_c: 23,
      dewpoint_c: 13,
      relative_humidity_pct: 52,
      probability_of_precipitation_pct: 15,
      wind_speed_kph: 18,
      wind_gust_kph: 27,
      wind_direction: "S",
      wind_direction_deg: 180,
      short_forecast: "Mostly Sunny",
      icon_url: null,
    },
  ],
  meta: metadata(),
};

export const dailyResponse: DailyWeatherResponse = {
  location: lincoln,
  periods: [
    {
      number: 1,
      name: "Thursday",
      start_time: "2026-07-30T12:00:00-05:00",
      end_time: "2026-07-30T18:00:00-05:00",
      is_daytime: true,
      temperature_c: 26,
      probability_of_precipitation_pct: 20,
      wind_speed_min_kph: 13,
      wind_speed_max_kph: 21,
      wind_direction: "S",
      short_forecast: "Mostly Sunny",
      detailed_forecast:
        "Mostly sunny, with a south wind and a slight chance of an afternoon shower.",
      icon_url: null,
    },
    {
      number: 2,
      name: "Thursday Night",
      start_time: "2026-07-30T18:00:00-05:00",
      end_time: "2026-07-31T06:00:00-05:00",
      is_daytime: false,
      temperature_c: 17,
      probability_of_precipitation_pct: 30,
      wind_speed_min_kph: 8,
      wind_speed_max_kph: 14,
      wind_direction: "SE",
      short_forecast: "Chance Showers",
      detailed_forecast:
        "A chance of showers after midnight. Mostly cloudy, with a southeast wind.",
      icon_url: null,
    },
  ],
  meta: metadata(),
};

export const officialAlert: OfficialAlert = {
  id: "urn:oid:test-alert",
  revision_id: "urn:oid:test-alert:20260730T190000Z",
  event: "Severe Thunderstorm Warning",
  headline: "Severe Thunderstorm Warning issued for Lancaster County",
  description: "At 3:00 PM, a severe thunderstorm was located west of Lincoln.",
  instruction:
    "Move to an interior room on the lowest floor of a sturdy building.",
  area_description: "Lancaster County",
  issuing_office: "NWS Omaha/Valley NE",
  sent_at: "2026-07-30T19:00:00Z",
  effective_at: "2026-07-30T19:00:00Z",
  onset_at: "2026-07-30T19:00:00Z",
  expires_at: "2099-07-30T22:00:00Z",
  ends_at: "2099-07-30T22:00:00Z",
  severity: "Severe",
  certainty: "Observed",
  urgency: "Immediate",
  status: "Actual",
  message_type: "Alert",
  response: "Shelter",
  geometry: null,
};

export const alertsResponse: ActiveAlertsResponse = {
  location: lincoln,
  alerts: [],
  status: "available",
  meta: metadata(),
};

export const searchResponse: LocationSearchResponse = {
  results: [omaha],
  query_kind: "zip",
  region_limit_km: 512,
};

export interface MockApiOptions {
  alert?: OfficialAlert | null;
  alertUnavailable?: boolean;
  currentFailure?: boolean;
  freshness?: ResponseMetadata["freshness"];
  search?: LocationSearchResponse;
}

export function createApiFetch(options: MockApiOptions = {}): typeof fetch {
  return (async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    const meta = metadata(options.freshness ?? "fresh");
    let status = 200;
    let body: unknown;

    if (url.pathname.endsWith("/location/search")) {
      body = options.search ?? searchResponse;
    } else if (url.pathname.endsWith("/weather/current")) {
      if (options.currentFailure) {
        status = 503;
        body = {
          error: {
            code: "source_unavailable",
            message: "Current observations are temporarily unavailable.",
            retryable: true,
          },
        };
      } else {
        body = { ...currentResponse, meta };
      }
    } else if (url.pathname.endsWith("/weather/hourly")) {
      body = { ...hourlyResponse, meta };
    } else if (url.pathname.endsWith("/weather/daily")) {
      body = { ...dailyResponse, meta };
    } else if (url.pathname.endsWith("/alerts/active")) {
      body = options.alertUnavailable
        ? {
            ...alertsResponse,
            status: "unavailable",
            meta: metadata("unavailable"),
          }
        : {
            ...alertsResponse,
            alerts: options.alert ? [options.alert] : [],
            meta,
          };
    } else {
      status = 404;
      body = {
        error: { code: "not_found", message: "Not found", retryable: false },
      };
    }

    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
}
