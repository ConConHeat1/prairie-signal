import { WeatherApiClient } from "@prairie-signal/api-client";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LocationSearch } from "../components/location-search";
import { createApiFetch, lincoln } from "./fixtures";

describe("LocationSearch", () => {
  it("does not reopen stale results after the query changes", async () => {
    const user = userEvent.setup();
    const client = new WeatherApiClient({ fetch: createApiFetch() });

    render(
      <LocationSearch client={client} location={lincoln} onSelect={vi.fn()} />,
    );

    const input = screen.getByRole("combobox", {
      name: "Search by city, five-digit ZIP approximation, or coordinates",
    });
    await user.type(input, "68102");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(
      await screen.findByRole("option", {
        name: /68102 ZIP approximation, Nebraska/,
      }),
    ).toBeVisible();

    await user.type(input, "1");
    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    await user.tab();
    await user.click(input);
    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
