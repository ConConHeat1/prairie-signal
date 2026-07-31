import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HourlyForecast } from "../components/hourly-forecast";
import { hourlyResponse } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HourlyForecast", () => {
  it("uses immediate scrolling when reduced motion is preferred", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    render(
      <HourlyForecast
        resource={{ status: "ready", data: hourlyResponse, error: null }}
        timeZone="America/Chicago"
        units="us"
      />,
    );

    const scroller = screen.getByRole("list", {
      name: "48-hour weather forecast",
    });
    const scrollBy = vi.fn();
    Object.defineProperty(scroller, "scrollBy", {
      configurable: true,
      value: scrollBy,
    });

    await user.click(screen.getByRole("button", { name: "Later hours" }));

    expect(window.matchMedia).toHaveBeenCalledWith(
      "(prefers-reduced-motion: reduce)",
    );
    expect(scrollBy).toHaveBeenCalledWith({
      behavior: "auto",
      left: 420,
    });
  });
});
