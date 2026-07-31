export function formatLocalTime(
  isoTime: string | null | undefined,
  timeZone: string,
  options: Intl.DateTimeFormatOptions = {},
): string {
  if (!isoTime) return "Time unavailable";
  const date = new Date(isoTime);
  if (Number.isNaN(date.getTime())) return "Time unavailable";

  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    ...options,
  }).format(date);
}

export function formatHour(isoTime: string, timeZone: string): string {
  return formatLocalTime(isoTime, timeZone, { hour: "numeric" });
}

export function localDateKey(isoTime: string, timeZone: string): string {
  const date = new Date(isoTime);
  if (Number.isNaN(date.getTime())) return "invalid";
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  return `${value.year}-${value.month}-${value.day}`;
}

export function formatAlertTime(isoTime: string, timeZone: string): string {
  return formatLocalTime(isoTime, timeZone, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function formatObservationTime(
  isoTime: string,
  timeZone: string,
): string {
  return formatLocalTime(isoTime, timeZone, {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function formatUpdatedTime(isoTime: string, timeZone: string): string {
  return formatLocalTime(isoTime, timeZone, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}
