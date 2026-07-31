"use client";

import type { Location } from "@prairie-signal/api-client";
import { WeatherApiClient } from "@prairie-signal/api-client";
import { LocateFixed, MapPin, Search, X } from "lucide-react";
import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

type SearchState = "idle" | "loading" | "ready" | "empty" | "error";

export function LocationSearch({
  client,
  location,
  onSelect,
}: {
  client: WeatherApiClient;
  location: Location;
  onSelect: (location: Location) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Location[]>([]);
  const [state, setState] = useState<SearchState>("idle");
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const requestRef = useRef<AbortController | null>(null);
  const inputId = useId();
  const listId = useId();

  useEffect(() => () => requestRef.current?.abort(), []);

  async function searchLocations(value: string) {
    const normalized = value.trim();
    if (normalized.length < 2) {
      requestRef.current?.abort();
      setResults([]);
      setState("idle");
      setOpen(false);
      return;
    }

    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setState("loading");
    setOpen(true);
    setMessage("");

    try {
      const response = await client.searchLocations(
        normalized,
        8,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setResults(response.results);
      setActiveIndex(response.results.length > 0 ? 0 : -1);
      setState(response.results.length > 0 ? "ready" : "empty");
    } catch (error) {
      if (controller.signal.aborted) return;
      setResults([]);
      setState("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Location search is temporarily unavailable.",
      );
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state === "ready" && activeIndex >= 0) {
      const result = results[activeIndex];
      if (result) selectLocation(result);
      return;
    }
    void searchLocations(query);
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const value = event.target.value;
    requestRef.current?.abort();
    requestRef.current = null;
    setQuery(value);
    setResults([]);
    setState("idle");
    setMessage("");
    setOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && results.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === "ArrowUp" && results.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  function selectLocation(result: Location) {
    setQuery("");
    setOpen(false);
    setResults([]);
    setState("idle");
    setActiveIndex(-1);
    onSelect(result);
  }

  const activeDescendant =
    open && activeIndex >= 0 && results[activeIndex]
      ? `${listId}-${results[activeIndex].id}`
      : undefined;

  return (
    <div className="location-search">
      <div className="location-search__heading">
        <div>
          <span className="location-search__kicker">
            Selected forecast point
          </span>
          <strong>
            <MapPin aria-hidden="true" size={16} />
            {location.label}
          </strong>
        </div>
        <span className="location-search__scope">
          Central Great Plains coverage
        </span>
      </div>

      <form
        className="location-search__form"
        onSubmit={handleSubmit}
        role="search"
      >
        <label className="ps-visually-hidden" htmlFor={inputId}>
          Search by city, five-digit ZIP approximation, or coordinates
        </label>
        <Search
          aria-hidden="true"
          className="location-search__search-icon"
          size={20}
        />
        <input
          aria-activedescendant={activeDescendant}
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded={open}
          autoComplete="off"
          id={inputId}
          onChange={handleChange}
          onFocus={() => results.length > 0 && setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="City, ZIP approximation, or 40.81, -96.70"
          role="combobox"
          spellCheck={false}
          type="search"
          value={query}
        />
        {query ? (
          <button
            aria-label="Clear search"
            className="location-search__clear"
            onClick={() => {
              setQuery("");
              setResults([]);
              setOpen(false);
              setState("idle");
            }}
            type="button"
          >
            <X aria-hidden="true" size={17} />
          </button>
        ) : null}
        <button
          className="location-search__submit"
          disabled={state === "loading"}
          type="submit"
        >
          {state === "loading" ? "Searching…" : "Search"}
        </button>
      </form>

      <div aria-live="polite" className="ps-visually-hidden">
        {state === "loading"
          ? "Searching locations."
          : state === "ready"
            ? `${results.length} locations found.`
            : state === "empty"
              ? "No locations found."
              : state === "error"
                ? message
                : ""}
      </div>

      {open ? (
        <div className="location-search__results" id={listId} role="listbox">
          {state === "loading" ? (
            <p className="location-search__message">
              Searching the regional location index…
            </p>
          ) : null}
          {state === "empty" ? (
            <div className="location-search__message">
              <strong>No matching location</strong>
              <span>
                Try a nearby city, five-digit ZIP, or latitude and longitude.
              </span>
            </div>
          ) : null}
          {state === "error" ? (
            <div className="location-search__message location-search__message--error">
              <strong>Search is temporarily unavailable</strong>
              <span>{message}</span>
            </div>
          ) : null}
          {state === "ready"
            ? results.map((result, index) => (
                <button
                  aria-selected={index === activeIndex}
                  className={index === activeIndex ? "is-active" : undefined}
                  id={`${listId}-${result.id}`}
                  key={result.id}
                  onClick={() => selectLocation(result)}
                  onMouseEnter={() => setActiveIndex(index)}
                  role="option"
                  type="button"
                >
                  <span
                    className="location-search__result-icon"
                    aria-hidden="true"
                  >
                    {result.kind === "coordinate" ? (
                      <LocateFixed size={18} />
                    ) : (
                      <MapPin size={18} />
                    )}
                  </span>
                  <span>
                    <strong>{result.label}</strong>
                    <small>
                      {result.kind === "zcta"
                        ? "ZIP Code Tabulation Area · approximate location"
                        : result.kind === "coordinate"
                          ? "Forecast coordinates"
                          : "City"}
                    </small>
                  </span>
                </button>
              ))
            : null}
        </div>
      ) : null}
      <p className="location-search__privacy">
        Search stays temporary. Exact locations are not saved or associated with
        an account.
      </p>
    </div>
  );
}
