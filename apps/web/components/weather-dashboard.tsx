"use client";

import {
  type ActiveAlertsResponse,
  type CurrentWeatherResponse,
  type DailyWeatherResponse,
  type HourlyWeatherResponse,
  type Location,
  WeatherApiClient,
  weatherApi,
} from "@prairie-signal/api-client";
import { Button, StatusBadge } from "@prairie-signal/ui";
import type { UnitSystem } from "@prairie-signal/weather-units";
import { CloudSun, RefreshCw, ShieldCheck, Signal, Sprout } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { formatLocalTime, formatUpdatedTime } from "../lib/time";
import { CurrentConditions } from "./current-conditions";
import { DailyForecast } from "./daily-forecast";
import { DataStatusNotice } from "./data-status";
import { HourlyForecast } from "./hourly-forecast";
import { LocationSearch } from "./location-search";
import { OfficialAlerts } from "./official-alerts";
import { loadingResource, type ResourceState } from "./resource";
import { SourceDetails } from "./source-details";
import { UnitToggle } from "./unit-toggle";

export const LINCOLN_LOCATION: Location = {
  id: "place:lincoln-ne",
  name: "Lincoln",
  region: "Nebraska",
  country: "US",
  latitude: 40.8136,
  longitude: -96.7026,
  timezone: "America/Chicago",
  kind: "city",
  label: "Lincoln, Nebraska",
};

const UNIT_STORAGE_KEY = "prairie-signal:units";

function readableError(error: unknown, fallback: string): string {
  if (error instanceof DOMException && error.name === "AbortError") return "";
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function WeatherDashboard({
  siteName,
  client = weatherApi,
}: {
  siteName: string;
  client?: WeatherApiClient;
}) {
  const [location, setLocation] = useState<Location>(LINCOLN_LOCATION);
  const [units, setUnits] = useState<UnitSystem>("us");
  const [refreshKey, setRefreshKey] = useState(0);
  const [current, setCurrent] =
    useState<ResourceState<CurrentWeatherResponse>>(loadingResource);
  const [hourly, setHourly] =
    useState<ResourceState<HourlyWeatherResponse>>(loadingResource);
  const [daily, setDaily] =
    useState<ResourceState<DailyWeatherResponse>>(loadingResource);
  const [alerts, setAlerts] =
    useState<ResourceState<ActiveAlertsResponse>>(loadingResource);

  useEffect(() => {
    const saved = window.localStorage.getItem(UNIT_STORAGE_KEY);
    if (saved !== "us" && saved !== "metric") return;
    const frame = window.requestAnimationFrame(() => setUnits(saved));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const coordinates = {
      latitude: location.latitude,
      longitude: location.longitude,
    };

    void client
      .getCurrent(coordinates, controller.signal)
      .then(
        (data) =>
          !controller.signal.aborted &&
          setCurrent({ status: "ready", data, error: null }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setCurrent({
          status: "error",
          data: null,
          error: readableError(
            error,
            "Current observations are temporarily unavailable.",
          ),
        });
      });

    void client
      .getHourly(coordinates, 48, controller.signal)
      .then(
        (data) =>
          !controller.signal.aborted &&
          setHourly({ status: "ready", data, error: null }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setHourly({
          status: "error",
          data: null,
          error: readableError(
            error,
            "The hourly forecast is temporarily unavailable.",
          ),
        });
      });

    void client
      .getDaily(coordinates, controller.signal)
      .then(
        (data) =>
          !controller.signal.aborted &&
          setDaily({ status: "ready", data, error: null }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setDaily({
          status: "error",
          data: null,
          error: readableError(
            error,
            "The daily forecast is temporarily unavailable.",
          ),
        });
      });

    void client
      .getActiveAlerts(coordinates, controller.signal)
      .then(
        (data) =>
          !controller.signal.aborted &&
          setAlerts({ status: "ready", data, error: null }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setAlerts({
          status: "error",
          data: null,
          error: readableError(
            error,
            "The official alert feed is temporarily unavailable.",
          ),
        });
      });

    return () => controller.abort();
  }, [client, location, refreshKey]);

  function changeUnits(nextUnits: UnitSystem) {
    setUnits(nextUnits);
    window.localStorage.setItem(UNIT_STORAGE_KEY, nextUnits);
  }

  function showLoadingStates() {
    setCurrent(loadingResource());
    setHourly(loadingResource());
    setDaily(loadingResource());
    setAlerts(loadingResource());
  }

  function selectLocation(nextLocation: Location) {
    showLoadingStates();
    setLocation(nextLocation);
  }

  function refreshWeather() {
    showLoadingStates();
    setRefreshKey((value) => value + 1);
  }

  const unavailableSections = useMemo(() => {
    const unavailable: string[] = [];
    if (current.status === "error") unavailable.push("current conditions");
    if (hourly.status === "error") unavailable.push("hourly forecast");
    if (daily.status === "error") unavailable.push("day and night forecast");
    if (alerts.status === "error" || alerts.data?.status === "unavailable")
      unavailable.push("official alert status");
    return unavailable;
  }, [alerts, current.status, daily.status, hourly.status]);

  const metadata = [
    current.data?.meta,
    hourly.data?.meta,
    daily.data?.meta,
    alerts.data?.meta,
  ];
  const latestFetch = metadata
    .map((meta) => meta?.fetched_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);
  const isLoading = [current, hourly, daily, alerts].some(
    (resource) => resource.status === "loading",
  );

  return (
    <div className="weather-app">
      <a className="skip-link" href="#forecast-content">
        Skip to forecast
      </a>
      <div className="sky-wash" aria-hidden="true">
        <div className="sky-wash__line sky-wash__line--one" />
        <div className="sky-wash__line sky-wash__line--two" />
        <div className="sky-wash__line sky-wash__line--three" />
      </div>

      <header className="site-header">
        <div className="site-header__inner">
          <Link aria-label={`${siteName} home`} className="brand" href="/">
            <span aria-hidden="true" className="brand__mark">
              <Signal />
            </span>
            <span>
              <strong>{siteName}</strong>
              <small>Great Plains weather</small>
            </span>
          </Link>
          <div className="site-header__tools">
            <StatusBadge className="official-source-pill" tone="positive">
              Official NWS data
            </StatusBadge>
            <UnitToggle onChange={changeUnits} value={units} />
          </div>
        </div>
      </header>

      <main id="forecast-content">
        <section className="forecast-intro">
          <div className="forecast-intro__copy">
            <span className="eyebrow">
              <Sprout aria-hidden="true" size={15} />
              Grounded in public data
            </span>
            <h1>
              A clearer view of <span>{location.name}.</span>
            </h1>
            <p>
              Current observations, official alerts, and the NWS
              forecast—without ads, tracking, or invented certainty.
            </p>
            <div className="forecast-intro__meta">
              <span>
                {formatLocalTime(new Date().toISOString(), location.timezone, {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                })}
              </span>
              <span aria-hidden="true">·</span>
              <span>
                {latestFetch
                  ? `Updated ${formatUpdatedTime(latestFetch, location.timezone)}`
                  : "Connecting to sources"}
              </span>
              <Button
                aria-label="Refresh weather data"
                className={isLoading ? "is-spinning" : undefined}
                disabled={isLoading}
                onClick={refreshWeather}
                variant="quiet"
              >
                <RefreshCw aria-hidden="true" size={16} />
                Refresh
              </Button>
            </div>
          </div>
          <div className="forecast-intro__emblem" aria-hidden="true">
            <CloudSun />
            <span>40.8° N</span>
          </div>
        </section>

        <LocationSearch
          client={client}
          location={location}
          onSelect={selectLocation}
        />

        <OfficialAlerts resource={alerts} timeZone={location.timezone} />

        <DataStatusNotice
          metadata={metadata}
          unavailableSections={unavailableSections}
        />

        <section aria-label="Weather overview" className="weather-overview">
          <CurrentConditions
            onRetry={refreshWeather}
            resource={current}
            timeZone={location.timezone}
            units={units}
          />
          <div className="weather-overview__aside">
            <div className="trust-card">
              <ShieldCheck aria-hidden="true" />
              <div>
                <span className="eyebrow">What you’re seeing</span>
                <h2>Observed means observed.</h2>
                <p>
                  Current values come from a nearby reporting station. Forecast
                  values are never used to fill a missing observation.
                </p>
              </div>
            </div>
            <div className="scope-card">
              <span>Forecast location</span>
              <strong>{location.label}</strong>
              <small>
                {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}{" "}
                · {location.timezone}
              </small>
            </div>
          </div>
        </section>

        <HourlyForecast
          resource={hourly}
          timeZone={location.timezone}
          units={units}
        />
        <DailyForecast
          resource={daily}
          timeZone={location.timezone}
          units={units}
        />

        <SourceDetails
          entries={[
            {
              label: "Current observation",
              meta: current.data?.meta,
              unavailable: current.status === "error",
            },
            {
              label: "Hourly forecast",
              meta: hourly.data?.meta,
              unavailable: hourly.status === "error",
            },
            {
              label: "Day & night forecast",
              meta: daily.data?.meta,
              unavailable: daily.status === "error",
            },
            {
              label: "Official alerts",
              meta: alerts.data?.meta,
              unavailable: alerts.status === "error",
            },
          ]}
          timeZone={location.timezone}
        />
      </main>

      <footer className="site-footer">
        <div>
          <Link
            aria-label={`${siteName} home`}
            className="brand brand--footer"
            href="/"
          >
            <span aria-hidden="true" className="brand__mark">
              <Signal />
            </span>
            <strong>{siteName}</strong>
          </Link>
          <p>
            An ad-free, privacy-minded view of public weather data for the
            central Great Plains.
          </p>
        </div>
        <div>
          <a
            href="https://www.weather.gov/documentation/services-web-api"
            rel="noreferrer"
            target="_blank"
          >
            NWS API documentation
          </a>
          <span>Working name · availability review required before launch</span>
        </div>
      </footer>
    </div>
  );
}
