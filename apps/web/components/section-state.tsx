import { AlertTriangle, CloudOff, RotateCw } from "lucide-react";
import { Button, Card } from "@prairie-signal/ui";

export function SectionLoading({ label }: { label: string }) {
  return (
    <Card
      aria-busy="true"
      aria-label={`Loading ${label}`}
      className="section-loading"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton skeleton--large" />
      <div className="skeleton skeleton--line" />
      <span className="ps-visually-hidden">Loading {label}…</span>
    </Card>
  );
}

export function SectionUnavailable({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="section-unavailable">
      <span aria-hidden="true" className="section-unavailable__icon">
        <CloudOff />
      </span>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
        {onRetry ? (
          <Button onClick={onRetry} variant="secondary">
            <RotateCw aria-hidden="true" size={16} />
            Try again
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

export function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="empty-state">
      <AlertTriangle aria-hidden="true" size={20} />
      <div>
        <h3>{title}</h3>
        <p>{message}</p>
      </div>
    </div>
  );
}
