import {
  Cloud,
  CloudFog,
  CloudLightning,
  CloudMoon,
  CloudRain,
  CloudSnow,
  CloudSun,
  Moon,
  Sun,
} from "lucide-react";
import type { ReactNode } from "react";

interface ConditionIconProps {
  condition: string;
  isDaytime?: boolean;
  size?: "small" | "medium" | "large";
}

function renderIcon(condition: string, isDaytime = true): ReactNode {
  const value = condition.toLowerCase();
  if (/(thunder|t-storm|lightning)/.test(value))
    return <CloudLightning strokeWidth={1.65} />;
  if (/(snow|sleet|blizzard|flurr)/.test(value))
    return <CloudSnow strokeWidth={1.65} />;
  if (/(rain|shower|drizzle)/.test(value))
    return <CloudRain strokeWidth={1.65} />;
  if (/(fog|mist|haze|smoke)/.test(value))
    return <CloudFog strokeWidth={1.65} />;
  if (/(partly|mostly|few|scattered)/.test(value)) {
    return isDaytime ? (
      <CloudSun strokeWidth={1.65} />
    ) : (
      <CloudMoon strokeWidth={1.65} />
    );
  }
  if (/(cloud|overcast)/.test(value)) return <Cloud strokeWidth={1.65} />;
  if (/(clear|sunny|fair)/.test(value)) {
    return isDaytime ? <Sun strokeWidth={1.65} /> : <Moon strokeWidth={1.65} />;
  }
  return isDaytime ? (
    <CloudSun strokeWidth={1.65} />
  ) : (
    <CloudMoon strokeWidth={1.65} />
  );
}

export function ConditionIcon({
  condition,
  isDaytime = true,
  size = "medium",
}: ConditionIconProps) {
  return (
    <span
      aria-hidden="true"
      className={`condition-icon condition-icon--${size}`}
    >
      {renderIcon(condition, isDaytime)}
    </span>
  );
}
