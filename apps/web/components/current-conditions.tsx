import type { CurrentWeatherResponse } from "@prairie-signal/api-client";
import { Card } from "@prairie-signal/ui";
import {
  Compass,
  Droplets,
  Eye,
  Gauge,
  Navigation,
  ThermometerSun,
  Wind,
} from "lucide-react";

import {
  formatDistance,
  formatPercent,
  formatPressure,
  formatSpeed,
  formatTemperature,
  formatVisibility,
  formatWindDirection,
  type UnitSystem,
} from "@prairie-signal/weather-units";

import { formatObservationTime } from "../lib/time";
import { cleanCondition } from "../lib/weather";
import { ConditionIcon } from "./condition-icon";
import { FreshnessBadge } from "./freshness-badge";
import type { ResourceState } from "./resource";
import { SectionLoading, SectionUnavailable } from "./section-state";

interface DetailProps {
  icon: typeof Droplets;
  label: string;
  value: string;
}

function Detail({ icon: Icon, label, value }: DetailProps) {
  return (
    <div className="condition-detail">
      <span aria-hidden="true" className="condition-detail__icon">
        <Icon size={18} />
      </span>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function CurrentConditions({
  resource,
  timeZone,
  units,
  onRetry,
}: {
  resource: ResourceState<CurrentWeatherResponse>;
  timeZone: string;
  units: UnitSystem;
  onRetry: () => void;
}) {
  if (resource.status === "loading" && !resource.data) {
    return <SectionLoading label="current conditions" />;
  }

  if (!resource.data) {
    return (
      <SectionUnavailable
        message="No forecast value is being substituted for the missing observation."
        onRetry={onRetry}
        title="Current conditions unavailable"
      />
    );
  }

  const { current, station, meta } = resource.data;
  const condition = cleanCondition(current.text_description);
  const temperature = formatTemperature(current.temperature_c, units);
  const feelsLike = formatTemperature(current.apparent_temperature_c, units);
  const wind = formatSpeed(current.wind_speed_kph, units);
  const gust = formatSpeed(current.wind_gust_kph, units);
  const stationDistance = formatDistance(station.distance_km, units);

  return (
    <Card aria-labelledby="current-conditions-title" className="current-card">
      <div className="current-card__topline">
        <div>
          <span className="eyebrow">Nearest valid observation</span>
          <h2 id="current-conditions-title">Current conditions</h2>
        </div>
        <FreshnessBadge freshness={meta.freshness} />
      </div>

      <div className="current-card__hero">
        <ConditionIcon condition={condition} size="large" />
        <div className="current-card__reading">
          <span
            aria-label={`${temperature.value} degrees`}
            className="current-card__temperature"
          >
            {temperature.combined}
          </span>
          <div>
            <strong>{condition}</strong>
            <span>
              {current.apparent_temperature_c === null
                ? "Feels-like value unavailable"
                : `Feels like ${feelsLike.combined}`}
            </span>
          </div>
        </div>
      </div>

      <div className="condition-details" aria-label="Observation details">
        <Detail
          icon={Droplets}
          label="Humidity"
          value={formatPercent(current.relative_humidity_pct).combined}
        />
        <Detail
          icon={ThermometerSun}
          label="Dew point"
          value={formatTemperature(current.dewpoint_c, units).combined}
        />
        <Detail
          icon={Wind}
          label="Wind"
          value={`${formatWindDirection(current.wind_direction_deg)} ${wind.combined}`}
        />
        <Detail icon={Navigation} label="Gusts" value={gust.combined} />
        <Detail
          icon={Gauge}
          label="Pressure"
          value={formatPressure(current.pressure_hpa, units).combined}
        />
        <Detail
          icon={Eye}
          label="Visibility"
          value={formatVisibility(current.visibility_km, units).combined}
        />
      </div>

      <div className="current-card__station">
        <Compass aria-hidden="true" size={18} />
        <div>
          <strong>{station.name}</strong>
          <span>
            {stationDistance.combined} away · observed{" "}
            {formatObservationTime(station.observed_at, timeZone)}
          </span>
        </div>
      </div>
      {(meta.warnings?.length ?? 0) > 0 ? (
        <ul className="data-warnings" aria-label="Current condition data notes">
          {meta.warnings?.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
