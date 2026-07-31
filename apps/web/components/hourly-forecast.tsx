"use client";

import type { HourlyWeatherResponse } from "@prairie-signal/api-client";
import { Card, Button } from "@prairie-signal/ui";
import { ArrowLeft, ArrowRight, Droplets, Wind } from "lucide-react";
import { useRef } from "react";

import {
  formatPercent,
  formatSpeed,
  formatTemperature,
  formatWindDirection,
  type UnitSystem,
} from "@prairie-signal/weather-units";

import { formatHour, formatLocalTime, localDateKey } from "../lib/time";
import { cleanCondition } from "../lib/weather";
import { ConditionIcon } from "./condition-icon";
import { FreshnessBadge } from "./freshness-badge";
import type { ResourceState } from "./resource";
import {
  EmptyState,
  SectionLoading,
  SectionUnavailable,
} from "./section-state";

export function HourlyForecast({
  resource,
  timeZone,
  units,
}: {
  resource: ResourceState<HourlyWeatherResponse>;
  timeZone: string;
  units: UnitSystem;
}) {
  const scrollerRef = useRef<HTMLUListElement>(null);

  if (resource.status === "loading" && !resource.data) {
    return <SectionLoading label="48-hour forecast" />;
  }

  if (!resource.data) {
    return (
      <SectionUnavailable
        message="The official hourly forecast could not be loaded. Current observations may still be available."
        title="Hourly forecast unavailable"
      />
    );
  }

  const periods = resource.data.periods.slice(0, 48);

  function scroll(direction: -1 | 1) {
    const reduceMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    scrollerRef.current?.scrollBy({
      left: direction * 420,
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }

  return (
    <Card
      aria-labelledby="hourly-title"
      className="forecast-section hourly-section"
    >
      <div className="section-heading">
        <div>
          <span className="eyebrow">Next 48 hours</span>
          <h2 id="hourly-title">Hour by hour</h2>
          <p>Official NWS point forecast periods shown in local time.</p>
        </div>
        <div className="section-heading__actions">
          <FreshnessBadge freshness={resource.data.meta.freshness} />
          <div className="scroll-buttons" aria-label="Scroll hourly forecast">
            <Button
              aria-label="Earlier hours"
              onClick={() => scroll(-1)}
              variant="quiet"
            >
              <ArrowLeft aria-hidden="true" size={18} />
            </Button>
            <Button
              aria-label="Later hours"
              onClick={() => scroll(1)}
              variant="quiet"
            >
              <ArrowRight aria-hidden="true" size={18} />
            </Button>
          </div>
        </div>
      </div>

      {periods.length === 0 ? (
        <EmptyState
          message="The NWS response did not contain any hourly periods."
          title="No hourly periods returned"
        />
      ) : (
        <ul
          aria-label="48-hour weather forecast"
          className="hourly-list"
          ref={scrollerRef}
        >
          {periods.map((period, index) => {
            const condition = cleanCondition(period.short_forecast);
            const dateLabel = formatLocalTime(period.start_time, timeZone, {
              weekday: "short",
              month: "short",
              day: "numeric",
            });
            const showDate =
              index === 0 ||
              localDateKey(periods[index - 1]?.start_time ?? "", timeZone) !==
                localDateKey(period.start_time, timeZone);

            return (
              <li className="hourly-period" key={period.start_time}>
                <span className="hourly-period__date">
                  {showDate ? dateLabel : "\u00a0"}
                </span>
                <strong className="hourly-period__time">
                  {formatHour(period.start_time, timeZone)}
                </strong>
                <ConditionIcon
                  condition={condition}
                  isDaytime={period.is_daytime}
                  size="medium"
                />
                <span className="hourly-period__temperature">
                  {formatTemperature(period.temperature_c, units).combined}
                </span>
                <span className="hourly-period__condition" title={condition}>
                  {condition}
                </span>
                <span className="hourly-period__metric">
                  <Droplets aria-hidden="true" size={14} />
                  {
                    formatPercent(period.probability_of_precipitation_pct)
                      .combined
                  }
                </span>
                <span className="hourly-period__metric">
                  <Wind aria-hidden="true" size={14} />
                  {formatWindDirection(period.wind_direction_deg)}{" "}
                  {formatSpeed(period.wind_speed_kph, units).combined}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
