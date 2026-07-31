import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function cx(
  ...classes: Array<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "quiet";
}

export function Button({
  className,
  variant = "primary",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cx("ps-button", `ps-button--${variant}`, className)}
      type={type}
      {...props}
    />
  );
}

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "article" | "section" | "div";
  children: ReactNode;
}

export function Card({
  as: Element = "section",
  className,
  children,
  ...props
}: CardProps) {
  return (
    <Element className={cx("ps-card", className)} {...props}>
      {children}
    </Element>
  );
}

export interface StatusBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "neutral" | "positive" | "caution" | "critical";
}

export function StatusBadge({
  className,
  tone = "neutral",
  children,
  ...props
}: StatusBadgeProps) {
  return (
    <span
      className={cx("ps-status-badge", `ps-status-badge--${tone}`, className)}
      {...props}
    >
      <span aria-hidden="true" className="ps-status-badge__dot" />
      {children}
    </span>
  );
}

export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="ps-visually-hidden">{children}</span>;
}
