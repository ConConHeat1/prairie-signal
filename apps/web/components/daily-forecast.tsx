import type { DailyWeatherResponse } from "@prairie-signal/api-client";
import { Card } from "@prairie-signal/ui";
import { Droplets, Wind } from "lucide-react";

import {
  formatPercent,
  formatSpeed,
  formatTemperature,
  type UnitSystem,
} from "@prairie-signal/weather-units";

import { formatLocalTime } from "../lib/time";
import { cleanCondition } from "../lib/weather";
import { ConditionIcon } from "./condition-icon";
import { FreshnessBadge } from "./freshness-badge";
import type { ResourceState } from "./resource";
import {
  EmptyState,
  SectionLoading,
  SectionUnavailable,
} from "./section-state";

export function DailyForecast({
  resource,
  timeZone,
  units,
}: {
  resource: ResourceState<DailyWeatherResponse>;
  timeZone: string;
  units: UnitSystem;
}) {
  if (resource.status === "loading" && !resource.data) {
    return <SectionLoading label="daily forecast" />;
  }

  if (!resource.data) {
    return (
      <SectionUnavailable
        message="The official NWS day and night forecast is temporarily unavailable."
        title="Daily forecast unavailable"
      />
    );
  }

  const periods = resource.data.periods;
  return (
    <Card
      aria-labelledby="daily-title"
      className="forecast-section daily-section"
    >
      <div className="section-heading">
        <div>
          <span className="eyebrow">Official point forecast</span>
          <h2 id="daily-title">Day & night outlook</h2>
          <p>
            Showing only the forecast periods supplied by the National Weather
            Service.
          </p>
        </div>
        <FreshnessBadge freshness={resource.data.meta.freshness} />
      </div>

      {periods.length === 0 ? (
        <EmptyState
          message="The NWS response did not contain any daily forecast periods."
          title="No periods returned"
        />
      ) : (
        <ol className="daily-list">
          {periods.map((period) => {
            const condition = cleanCondition(period.short_forecast);
            const temperature = formatTemperature(period.temperature_c, units);
            return (
              <li
                className="daily-period"
                key={`${period.start_time}:${period.number}`}
              >
                <div className="daily-period__when">
                  <span>
                    {formatLocalTime(period.start_time, timeZone, {
                      weekday: "short",
                    })}
                  </span>
                  <strong>{period.name}</strong>
                  <small>{period.is_daytime ? "Day" : "Night"}</small>
                </div>
                <ConditionIcon
                  condition={condition}
                  isDaytime={period.is_daytime}
                  size="medium"
                />
                <div className="daily-period__forecast">
                  <strong>{condition}</strong>
                  <p>{period.detailed_forecast}</p>
                </div>
                <div className="daily-period__temperature">
                  <strong aria-label={`${temperature.value} degrees`}>
                    {temperature.combined}
                  </strong>
                  <span>{period.is_daytime ? "High" : "Low"}</span>
                </div>
                <div className="daily-period__metrics">
                  <span>
                    <Droplets aria-hidden="true" size={15} />
                    {
                      formatPercent(period.probability_of_precipitation_pct)
                        .combined
                    }
                  </span>
                  <span>
                    <Wind aria-hidden="true" size={15} />
                    {period.wind_direction ?? "Variable"}{" "}
                    {formatSpeed(period.wind_speed_max_kph, units).combined}
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
