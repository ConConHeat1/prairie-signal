import type { UnitSystem } from "@prairie-signal/weather-units";

export function UnitToggle({
  value,
  onChange,
}: {
  value: UnitSystem;
  onChange: (value: UnitSystem) => void;
}) {
  return (
    <fieldset
      aria-label="Temperature and measurement units"
      className="unit-toggle"
    >
      <legend className="ps-visually-hidden">Measurement units</legend>
      <button
        aria-pressed={value === "us"}
        className={value === "us" ? "is-active" : undefined}
        onClick={() => onChange("us")}
        type="button"
      >
        °F
      </button>
      <button
        aria-pressed={value === "metric"}
        className={value === "metric" ? "is-active" : undefined}
        onClick={() => onChange("metric")}
        type="button"
      >
        °C
      </button>
    </fieldset>
  );
}
