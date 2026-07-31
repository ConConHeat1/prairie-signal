import type { ResponseMetadata } from "@prairie-signal/api-client";
import { Card } from "@prairie-signal/ui";
import { AlertCircle, Clock3, Info } from "lucide-react";

import { worstFreshness } from "../lib/weather";

export function DataStatusNotice({
  metadata,
  unavailableSections,
}: {
  metadata: Array<ResponseMetadata | null | undefined>;
  unavailableSections: string[];
}) {
  const freshness = worstFreshness(metadata);

  if (unavailableSections.length > 0) {
    return (
      <Card
        className="data-status-notice data-status-notice--partial"
        role="status"
      >
        <AlertCircle aria-hidden="true" />
        <div>
          <strong>Some official data is unavailable</strong>
          <p>
            Available sections remain usable. Missing now:{" "}
            {new Intl.ListFormat("en-US").format(unavailableSections)}.
          </p>
        </div>
      </Card>
    );
  }

  if (freshness === "stale") {
    return (
      <Card
        className="data-status-notice data-status-notice--stale"
        role="status"
      >
        <Clock3 aria-hidden="true" />
        <div>
          <strong>Showing last-known-good weather data</strong>
          <p>
            At least one official source is stale. Timestamps remain visible so
            it is not mistaken for current data.
          </p>
        </div>
      </Card>
    );
  }

  if (freshness === "delayed") {
    return (
      <Card
        className="data-status-notice data-status-notice--delayed"
        role="status"
      >
        <Clock3 aria-hidden="true" />
        <div>
          <strong>Official data is delayed</strong>
          <p>
            The latest available values are shown with their source timestamps.
          </p>
        </div>
      </Card>
    );
  }

  const warnings = metadata.flatMap((item) => item?.warnings ?? []);
  if (warnings.length > 0) {
    return (
      <Card className="data-status-notice" role="status">
        <Info aria-hidden="true" />
        <div>
          <strong>Data quality note</strong>
          <p>{warnings[0]}</p>
        </div>
      </Card>
    );
  }

  return null;
}
