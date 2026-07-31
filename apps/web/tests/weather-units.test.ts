import {
  formatDistance,
  formatPressure,
  formatSpeed,
  formatTemperature,
  formatWindDirection,
} from "@prairie-signal/weather-units";
import { describe, expect, it } from "vitest";

describe("weather unit formatting", () => {
  it("converts canonical metric API values for US display", () => {
    expect(formatTemperature(0, "us").combined).toBe("32°");
    expect(formatSpeed(16.0934, "us").combined).toBe("10 mph");
    expect(formatDistance(1.60934, "us").combined).toBe("1.0 mi");
    expect(formatPressure(1013.25, "us").combined).toBe("29.9 inHg");
  });

  it("formats cardinal wind direction and keeps missing data explicit", () => {
    expect(formatWindDirection(225)).toBe("SW");
    expect(formatWindDirection(null)).toBe("Variable");
    expect(formatTemperature(null, "metric").combined).toBe("—");
  });
});
