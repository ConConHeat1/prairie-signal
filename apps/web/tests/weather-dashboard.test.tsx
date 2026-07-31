import { WeatherApiClient } from "@prairie-signal/api-client";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { WeatherDashboard } from "../components/weather-dashboard";
import { createApiFetch, officialAlert } from "./fixtures";

function renderDashboard(options: Parameters<typeof createApiFetch>[0] = {}) {
  const client = new WeatherApiClient({ fetch: createApiFetch(options) });
  return render(<WeatherDashboard client={client} siteName="Prairie Signal" />);
}

describe("WeatherDashboard", () => {
  it("renders current, hourly, daily, source, and clear-alert states for Lincoln", async () => {
    renderDashboard();

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Lincoln",
    );
    expect(await screen.findByText("Partly Cloudy")).toBeVisible();
    expect(screen.getAllByText("72°").length).toBeGreaterThan(0);
    expect(screen.getByText("Lincoln Airport")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Hour by hour" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Day & night outlook" }),
    ).toBeVisible();
    expect(
      screen.getByText("No active NWS alerts for this forecast point"),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Sources & freshness" }),
    ).toBeVisible();
  });

  it("converts visible measurements and persists only the unit preference", async () => {
    const user = userEvent.setup();
    renderDashboard();

    expect((await screen.findAllByText("72°")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/10 mph/).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "°C" }));

    expect(screen.getAllByText("22°").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/16 km\/h/).length).toBeGreaterThan(0);
    expect(window.localStorage.getItem("prairie-signal:units")).toBe("metric");
    expect(window.localStorage.length).toBe(1);
  });

  it("keeps official alert language prominent and unchanged", async () => {
    renderDashboard({ alert: officialAlert });

    const alertHeading = await screen.findByRole("heading", {
      name: "Severe Thunderstorm Warning",
    });
    const currentHeading = screen.getByRole("heading", {
      name: "Current conditions",
    });
    expect(
      alertHeading.compareDocumentPosition(currentHeading) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByText(officialAlert.headline ?? "")).toBeVisible();
    expect(screen.getByText(officialAlert.description)).toBeInTheDocument();
    expect(
      screen.getByText("Official National Weather Service alert"),
    ).toBeVisible();
  });

  it("states when alert status cannot be confirmed while preserving other weather", async () => {
    renderDashboard({ alertUnavailable: true });

    expect(
      await screen.findByText("Current alert status cannot be confirmed"),
    ).toBeVisible();
    expect(screen.getByText("Partly Cloudy")).toBeVisible();
    expect(
      screen.getByText(/Missing now: official alert status/),
    ).toBeVisible();
  });

  it("labels stale last-known-good data instead of presenting it as current", async () => {
    renderDashboard({ freshness: "stale" });

    expect(
      await screen.findByText("Showing last-known-good weather data"),
    ).toBeVisible();
    expect(screen.getAllByText("Stale").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Last-known-good cached response").length,
    ).toBeGreaterThan(0);
  });

  it("searches by ZIP approximation and loads the selected point", async () => {
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText("Partly Cloudy");

    const input = screen.getByRole("combobox", {
      name: "Search by city, five-digit ZIP approximation, or coordinates",
    });
    await user.type(input, "68102");
    await user.click(screen.getByRole("button", { name: "Search" }));
    const option = await screen.findByRole("option", {
      name: /68102 ZIP approximation, Nebraska/,
    });
    await user.click(option);

    await waitFor(() => {
      expect(
        screen.getAllByText("68102 ZIP approximation, Nebraska").length,
      ).toBeGreaterThan(0);
    });
    expect(window.localStorage.getItem("prairie-signal:location")).toBeNull();
  });
});
