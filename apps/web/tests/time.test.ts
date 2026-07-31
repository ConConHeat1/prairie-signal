import { describe, expect, it } from "vitest";

import { formatHour, localDateKey } from "../lib/time";

describe("browser time-zone conversion", () => {
  it("uses the selected IANA zone rather than the UTC calendar date", () => {
    expect(localDateKey("2026-07-31T04:30:00Z", "America/Chicago")).toBe(
      "2026-07-30",
    );
    expect(localDateKey("2026-07-31T04:30:00Z", "UTC")).toBe("2026-07-31");
  });

  it("honors the daylight-saving spring transition", () => {
    expect(formatHour("2026-03-08T07:30:00Z", "America/Chicago")).toBe("1 AM");
    expect(formatHour("2026-03-08T08:30:00Z", "America/Chicago")).toBe("3 AM");
  });
});
