import type { Freshness } from "@prairie-signal/api-client";
import { StatusBadge } from "@prairie-signal/ui";

import { freshnessLabel } from "../lib/weather";

export function FreshnessBadge({ freshness }: { freshness: Freshness }) {
  const tone =
    freshness === "fresh"
      ? "positive"
      : freshness === "delayed"
        ? "caution"
        : freshness === "stale" || freshness === "unavailable"
          ? "critical"
          : "neutral";

  return <StatusBadge tone={tone}>{freshnessLabel(freshness)}</StatusBadge>;
}
