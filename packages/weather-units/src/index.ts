export type UnitSystem = "us" | "metric";

export interface FormattedMeasurement {
  value: string;
  unit: string;
  combined: string;
}

const compactNumber = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const preciseNumber = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function missing(unit: string): FormattedMeasurement {
  return { value: "—", unit, combined: "—" };
}

function result(
  value: number | null | undefined,
  unit: string,
  precision: "compact" | "precise",
): FormattedMeasurement {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return missing(unit);
  }
  const formatted =
    precision === "compact"
      ? compactNumber.format(value)
      : preciseNumber.format(value);
  return { value: formatted, unit, combined: `${formatted}${unit}` };
}

export function formatTemperature(
  celsius: number | null | undefined,
  system: UnitSystem,
): FormattedMeasurement {
  if (celsius === null || celsius === undefined || !Number.isFinite(celsius)) {
    return missing("°");
  }
  const value = system === "us" ? (celsius * 9) / 5 + 32 : celsius;
  return result(value, "°", "compact");
}

export function formatSpeed(
  kph: number | null | undefined,
  system: UnitSystem,
): FormattedMeasurement {
  const value =
    system === "us" && kph !== null && kph !== undefined ? kph * 0.621371 : kph;
  return result(value, system === "us" ? " mph" : " km/h", "compact");
}

export function formatDistance(
  km: number | null | undefined,
  system: UnitSystem,
): FormattedMeasurement {
  const value =
    system === "us" && km !== null && km !== undefined ? km * 0.621371 : km;
  return result(value, system === "us" ? " mi" : " km", "precise");
}

export function formatVisibility(
  km: number | null | undefined,
  system: UnitSystem,
): FormattedMeasurement {
  return formatDistance(km, system);
}

export function formatPressure(
  hpa: number | null | undefined,
  system: UnitSystem,
): FormattedMeasurement {
  if (system === "us") {
    const value =
      hpa !== null && hpa !== undefined ? hpa * 0.0295299830714 : hpa;
    return result(value, " inHg", "precise");
  }
  return result(hpa, " hPa", "compact");
}

export function formatPercent(
  value: number | null | undefined,
): FormattedMeasurement {
  return result(value, "%", "compact");
}

const CARDINAL_DIRECTIONS = [
  "N",
  "NNE",
  "NE",
  "ENE",
  "E",
  "ESE",
  "SE",
  "SSE",
  "S",
  "SSW",
  "SW",
  "WSW",
  "W",
  "WNW",
  "NW",
  "NNW",
] as const;

export function formatWindDirection(
  degrees: number | null | undefined,
): string {
  if (degrees === null || degrees === undefined || !Number.isFinite(degrees)) {
    return "Variable";
  }
  const normalized = ((degrees % 360) + 360) % 360;
  return CARDINAL_DIRECTIONS[Math.round(normalized / 22.5) % 16] ?? "N";
}
