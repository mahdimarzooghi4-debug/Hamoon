import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: BadgeTone;
}) {
  return <span className={`hm-badge hm-badge--${tone}`}>{children}</span>;
}

type ButtonVariant = "primary" | "secondary" | "quiet";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
}) {
  return (
    <button
      className={`hm-button hm-button--${variant} ${className}`.trim()}
      {...props}
    />
  );
}

export function Panel({
  children,
  className = "",
  ...props
}: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return (
    <section className={`hm-panel ${className}`.trim()} {...props}>
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <article className="hm-metric">
      <div className="hm-metric__label">{label}</div>
      <strong className="hm-metric__value">{value}</strong>
      {hint ? <div className="hm-metric__hint">{hint}</div> : null}
    </article>
  );
}

export function LoadingState({ label = "در حال دریافت اطلاعات…" }: { label?: string }) {
  return (
    <div className="hm-state" role="status" aria-live="polite">
      <span className="hm-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="hm-state hm-state--stacked">
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

export function ErrorState({
  title = "دریافت اطلاعات انجام نشد",
  description,
  action,
}: {
  title?: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="hm-state hm-state--error hm-state--stacked" role="alert">
      <strong>{title}</strong>
      <span>{description}</span>
      {action}
    </div>
  );
}
