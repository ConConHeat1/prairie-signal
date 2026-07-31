import { expect, test, type Page, type Route } from "@playwright/test";

import {
  alertsResponse,
  currentResponse,
  dailyResponse,
  hourlyResponse,
  officialAlert,
  searchResponse,
} from "../tests/fixtures";

interface RouteOptions {
  alertsUnavailable?: boolean;
  currentUnavailable?: boolean;
  includeAlert?: boolean;
  expiredAlert?: boolean;
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    body: JSON.stringify(body),
    contentType: "application/json",
    status,
  });
}

async function mockWeatherApi(page: Page, options: RouteOptions = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());

    if (url.pathname.endsWith("/location/search")) {
      const query = url.searchParams.get("q") ?? "";
      await fulfillJson(
        route,
        query.includes(",")
          ? {
              ...searchResponse,
              query_kind: "coordinate",
              results: [
                {
                  ...searchResponse.results[0],
                  id: "coordinate:40.81:-96.70",
                  name: "Selected coordinates",
                  label: "40.8100, -96.7000",
                  latitude: 40.81,
                  longitude: -96.7,
                  kind: "coordinate",
                },
              ],
            }
          : searchResponse,
      );
    } else if (url.pathname.endsWith("/weather/current")) {
      if (options.currentUnavailable) {
        await fulfillJson(
          route,
          {
            error: {
              code: "nws_unavailable",
              message: "Current observations are temporarily unavailable.",
              retryable: true,
            },
          },
          503,
        );
      } else {
        await fulfillJson(route, currentResponse);
      }
    } else if (url.pathname.endsWith("/weather/hourly")) {
      await fulfillJson(route, hourlyResponse);
    } else if (url.pathname.endsWith("/weather/daily")) {
      await fulfillJson(route, dailyResponse);
    } else if (url.pathname.endsWith("/alerts/active")) {
      if (options.alertsUnavailable) {
        await fulfillJson(route, { ...alertsResponse, status: "unavailable" });
      } else if (options.expiredAlert) {
        await fulfillJson(route, {
          ...alertsResponse,
          alerts: [{ ...officialAlert, expires_at: "2020-01-01T00:00:00Z" }],
        });
      } else {
        await fulfillJson(route, {
          ...alertsResponse,
          alerts: options.includeAlert ? [officialAlert] : [],
        });
      }
    } else {
      await fulfillJson(
        route,
        {
          error: { code: "not_found", message: "Not found", retryable: false },
        },
        404,
      );
    }
  });
}

test("Lincoln forecast loads from live-data-shaped official fixtures", async ({
  page,
}) => {
  await mockWeatherApi(page, { includeAlert: true });
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Lincoln",
  );
  await expect(page.getByText("Partly Cloudy")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Severe Thunderstorm Warning" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Hour by hour" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Day & night outlook" }),
  ).toBeVisible();
  await expect(page.getByText("Lincoln Airport")).toBeVisible();
});

test("ZIP and coordinate-style search use the regional location endpoint", async ({
  page,
}) => {
  await mockWeatherApi(page);
  await page.goto("/");

  const search = page.getByRole("combobox", {
    name: "Search by city, five-digit ZIP approximation, or coordinates",
  });
  await search.fill("68102");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("option", { name: /68102 ZIP approximation/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("68102");

  await search.fill("40.81, -96.70");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("option", { name: /40.8100, -96.7000/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Selected coordinates",
  );
});

test("an NWS outage degrades sections independently and makes alert uncertainty explicit", async ({
  page,
}) => {
  await mockWeatherApi(page, {
    alertsUnavailable: true,
    currentUnavailable: true,
  });
  await page.goto("/");

  await expect(
    page.getByText("Current alert status cannot be confirmed"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Current conditions unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Hour by hour" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Day & night outlook" }),
  ).toBeVisible();
});

test("expired official alerts are never rendered as active", async ({
  page,
}) => {
  await mockWeatherApi(page, { expiredAlert: true });
  await page.goto("/");

  await expect(
    page.getByText("No active NWS alerts for this forecast point"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Severe Thunderstorm Warning" }),
  ).toHaveCount(0);
});
