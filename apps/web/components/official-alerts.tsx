import type {
  ActiveAlertsResponse,
  OfficialAlert,
} from "@prairie-signal/api-client";
import { Card, StatusBadge } from "@prairie-signal/ui";
import {
  AlertTriangle,
  BadgeCheck,
  ChevronDown,
  ShieldAlert,
} from "lucide-react";

import { formatAlertTime } from "../lib/time";
import { isExpired } from "../lib/weather";
import { FreshnessBadge } from "./freshness-badge";
import type { ResourceState } from "./resource";

function rankSeverity(severity: string): number {
  return ["Extreme", "Severe", "Moderate", "Minor", "Unknown"].indexOf(
    severity,
  ) === -1
    ? 4
    : ["Extreme", "Severe", "Moderate", "Minor", "Unknown"].indexOf(severity);
}

function AlertCard({
  alert,
  timeZone,
}: {
  alert: OfficialAlert;
  timeZone: string;
}) {
  const critical = alert.severity === "Extreme" || alert.severity === "Severe";
  return (
    <article
      className={`official-alert ${critical ? "official-alert--critical" : ""}`}
    >
      <div className="official-alert__rail" aria-hidden="true" />
      <div className="official-alert__content">
        <div className="official-alert__header">
          <span aria-hidden="true" className="official-alert__icon">
            <ShieldAlert />
          </span>
          <div>
            <span className="official-alert__authority">
              Official National Weather Service alert
            </span>
            <h3>{alert.event}</h3>
          </div>
          <StatusBadge tone={critical ? "critical" : "caution"}>
            {alert.severity}
          </StatusBadge>
        </div>
        {alert.headline ? (
          <p className="official-alert__headline">{alert.headline}</p>
        ) : null}
        <dl className="official-alert__facts">
          <div>
            <dt>Area</dt>
            <dd>{alert.area_description}</dd>
          </div>
          <div>
            <dt>Expires</dt>
            <dd>{formatAlertTime(alert.expires_at, timeZone)}</dd>
          </div>
          <div>
            <dt>Urgency</dt>
            <dd>{alert.urgency}</dd>
          </div>
          <div>
            <dt>Certainty</dt>
            <dd>{alert.certainty}</dd>
          </div>
        </dl>
        <details className="official-alert__details">
          <summary>
            Read the complete official alert
            <ChevronDown aria-hidden="true" size={18} />
          </summary>
          <div>
            <h4>Official description</h4>
            <p>{alert.description}</p>
            {alert.instruction ? (
              <>
                <h4>Instructions</h4>
                <p>{alert.instruction}</p>
              </>
            ) : null}
            <p className="official-alert__issuer">
              Issued by {alert.issuing_office || "the National Weather Service"}{" "}
              at {formatAlertTime(alert.sent_at, timeZone)}.
            </p>
          </div>
        </details>
      </div>
    </article>
  );
}

export function OfficialAlerts({
  resource,
  timeZone,
}: {
  resource: ResourceState<ActiveAlertsResponse>;
  timeZone: string;
}) {
  const activeAlerts = (resource.data?.alerts ?? [])
    .filter((alert) => !isExpired(alert.expires_at))
    .sort(
      (left, right) =>
        rankSeverity(left.severity) - rankSeverity(right.severity),
    );
  const unavailable =
    resource.status === "error" || resource.data?.status === "unavailable";

  return (
    <section aria-labelledby="official-alerts-title" className="alerts-region">
      <div className="section-heading section-heading--compact">
        <div>
          <span className="eyebrow">Safety first</span>
          <h2 id="official-alerts-title">Official alerts</h2>
        </div>
        {resource.data?.meta ? (
          <FreshnessBadge freshness={resource.data.meta.freshness} />
        ) : null}
      </div>

      {resource.status === "loading" ? (
        <Card
          aria-busy="true"
          className="alert-feed-state alert-feed-state--loading"
        >
          <span className="alert-feed-state__pulse" aria-hidden="true" />
          <span>Checking the official NWS alert feed…</span>
        </Card>
      ) : unavailable ? (
        <Card
          className="alert-feed-state alert-feed-state--unavailable"
          role="alert"
        >
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>Current alert status cannot be confirmed</strong>
            <p>
              The National Weather Service alert feed is temporarily
              unavailable. Check{" "}
              <a
                href="https://www.weather.gov/"
                rel="noreferrer"
                target="_blank"
              >
                weather.gov
              </a>{" "}
              or local emergency information if conditions may be dangerous.
            </p>
          </div>
        </Card>
      ) : activeAlerts.length === 0 ? (
        <Card className="alert-feed-state alert-feed-state--clear">
          <BadgeCheck aria-hidden="true" />
          <div>
            <strong>No active NWS alerts for this forecast point</strong>
            <p>
              The official feed was checked, but conditions can change quickly.
            </p>
          </div>
        </Card>
      ) : (
        <div className="official-alerts-list">
          {activeAlerts.map((alert) => (
            <AlertCard
              alert={alert}
              key={`${alert.id}:${alert.revision_id}`}
              timeZone={timeZone}
            />
          ))}
        </div>
      )}
    </section>
  );
}
