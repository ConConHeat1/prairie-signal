import type { Freshness, ResponseMetadata } from "@prairie-signal/api-client";

export const freshnessRank: Record<Freshness, number> = {
  fresh: 0,
  delayed: 1,
  stale: 2,
  unavailable: 3,
};

export function worstFreshness(
  metadata: Array<ResponseMetadata | null | undefined>,
): Freshness {
  return metadata.reduce<Freshness>((worst, item) => {
    if (!item) return worst;
    return freshnessRank[item.freshness] > freshnessRank[worst]
      ? item.freshness
      : worst;
  }, "fresh");
}

export function freshnessLabel(freshness: Freshness): string {
  switch (freshness) {
    case "fresh":
      return "Up to date";
    case "delayed":
      return "Delayed";
    case "stale":
      return "Stale";
    case "unavailable":
      return "Unavailable";
  }
}

export function cleanCondition(value: string | null | undefined): string {
  const condition = value?.trim();
  return condition || "Conditions unavailable";
}

export function isExpired(expiresAt: string, now = Date.now()): boolean {
  const expiration = Date.parse(expiresAt);
  return Number.isFinite(expiration) && expiration <= now;
}
