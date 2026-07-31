import type { ResponseMetadata } from "@prairie-signal/api-client";
import { Card } from "@prairie-signal/ui";
import {
  CheckCircle2,
  ChevronDown,
  Database,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";

import { formatUpdatedTime } from "../lib/time";
import { FreshnessBadge } from "./freshness-badge";

interface SourceEntry {
  label: string;
  meta: ResponseMetadata | null | undefined;
  unavailable?: boolean;
}

export function SourceDetails({
  entries,
  timeZone,
}: {
  entries: SourceEntry[];
  timeZone: string;
}) {
  return (
    <Card aria-labelledby="source-details-title" className="source-details">
      <div className="source-details__intro">
        <span aria-hidden="true" className="source-details__icon">
          <Database />
        </span>
        <div>
          <span className="eyebrow">Traceable by design</span>
          <h2 id="source-details-title">Sources & freshness</h2>
          <p>
            Forecasts and observations remain labeled with their official source
            and retrieval time.
          </p>
        </div>
        <div className="source-details__principle">
          <ShieldCheck aria-hidden="true" size={18} />
          No generated weather claims
        </div>
      </div>

      <div className="source-details__grid">
        {entries.map(({ label, meta, unavailable }) => (
          <div className="source-entry" key={label}>
            <div className="source-entry__heading">
              <strong>{label}</strong>
              {meta ? <FreshnessBadge freshness={meta.freshness} /> : null}
            </div>
            {meta ? (
              <>
                <a
                  href={meta.attribution?.url ?? "https://www.weather.gov/"}
                  rel="noreferrer"
                  target="_blank"
                >
                  {meta.attribution?.name ?? "National Weather Service"}
                  <ExternalLink aria-hidden="true" size={13} />
                </a>
                <span>
                  Fetched {formatUpdatedTime(meta.fetched_at, timeZone)}
                </span>
                <span>
                  <CheckCircle2 aria-hidden="true" size={13} />
                  {meta.quality === "verified"
                    ? "Verified source response"
                    : `${meta.quality} response`}
                </span>
                {meta.stale_fallback ? (
                  <small>Last-known-good cached response</small>
                ) : null}
              </>
            ) : (
              <span>
                {unavailable
                  ? "Temporarily unavailable"
                  : "Waiting for source response"}
              </span>
            )}
          </div>
        ))}
      </div>

      <details className="source-details__method">
        <summary>
          How freshness is handled
          <ChevronDown aria-hidden="true" size={17} />
        </summary>
        <p>
          Observations become delayed after 30 minutes and stale after 90.
          Forecasts become delayed after six hours and stale after twelve. Alert
          status is treated more strictly: delayed after two minutes and stale
          after ten.
        </p>
        <p>
          Confidence is marked unavailable when the National Weather Service
          does not publish a confidence value.
        </p>
      </details>
    </Card>
  );
}
