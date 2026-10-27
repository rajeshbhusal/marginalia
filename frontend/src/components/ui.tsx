import clsx from "clsx";
import { CircleAlert } from "lucide-react";
import {
  type ButtonHTMLAttributes,
  forwardRef,
  type ReactNode,
  type TextareaHTMLAttributes,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
} from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

// One primary per view; secondary and ghost for everything else
const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-brand text-on-brand shadow-(--elevation-xs) hover:bg-brand-hover",
  secondary:
    "border border-line-strong bg-surface text-ink hover:border-line-control hover:bg-surface-hover",
  ghost: "text-ink-muted hover:bg-surface-hover hover:text-ink",
  danger: "text-negative-ink hover:bg-negative-soft",
};

// 32, 36 and 40px tall; 44px on touch screens
const SIZES: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 px-3 text-sm",
  md: "h-9 gap-2 px-4 text-sm",
  lg: "h-10 gap-2 px-5 text-base",
};

/** Button styles, also for links that look like buttons. */
export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md") {
  return clsx(
    "inline-flex shrink-0 items-center justify-center rounded-lg font-medium transition-colors",
    "pointer-coarse:h-11 disabled:cursor-not-allowed disabled:opacity-50",
    VARIANTS[variant],
    SIZES[size],
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, className, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={clsx(buttonClasses(variant, size), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner className="size-4" />}
      {children}
    </button>
  );
});

export function IconButton({
  label,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={clsx(
        "inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-ink-subtle transition-colors pointer-coarse:size-11",
        "hover:bg-surface-hover hover:text-ink disabled:pointer-events-none disabled:text-ink-faint",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={clsx("animate-spin", className ?? "size-5")} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx("rounded-xl border border-line bg-surface shadow-(--elevation-xs)", className)}>
      {children}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "brand" | "positive" | "warning" | "negative";
  children: ReactNode;
}) {
  const tones = {
    neutral: "bg-sunken text-ink-muted",
    brand: "bg-brand-soft text-brand-ink",
    positive: "bg-positive-soft text-positive-ink",
    warning: "bg-warning-soft text-warning-ink",
    negative: "bg-negative-soft text-negative-ink",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

/** What went wrong and what to do about it, with an optional action such as Try again. */
export function ErrorNotice({
  title = "Something went wrong",
  message,
  action,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border border-negative/25 bg-negative-soft p-4 sm:flex-row sm:items-center"
    >
      <CircleAlert className="size-5 shrink-0 text-negative" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-semibold text-ink">{title}</p>
        <p className="mt-1 text-ink-muted">{message}</p>
      </div>
      {action && <div className="flex shrink-0 flex-wrap gap-2">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("rounded-md bg-line motion-safe:animate-pulse", className)} />;
}

/** A placeholder shaped like a page: a title, a few lines of text and a block. */
export function PageSkeleton({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={clsx("appear-delayed mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14", className)}
    >
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-4 h-9 w-4/5" />
      <Skeleton className="mt-3 h-9 w-3/5" />
      <div className="mt-6 space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-2/3" />
      </div>
      <Skeleton className="mt-10 h-40 w-full rounded-xl" />
    </div>
  );
}

/**
 * A textarea that grows with its content. With `singleLine` the value stays on one line (Enter
 * does nothing and pasted line breaks become spaces), but long text still wraps on screen.
 */
export function AutoTextArea({
  className,
  value,
  singleLine = false,
  onChange,
  onKeyDown,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { value: string; singleLine?: boolean }) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const fit = useCallback(() => {
    const element = ref.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${element.scrollHeight}px`;
  }, []);

  useLayoutEffect(fit, [value, fit]);

  // Wrapping changes with the width and once web fonts have loaded, so measure again then
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    let width = element.clientWidth;
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => {
            if (element.clientWidth === width) return;
            width = element.clientWidth;
            fit();
          });
    observer?.observe(element);
    document.fonts?.addEventListener("loadingdone", fit);
    return () => {
      observer?.disconnect();
      document.fonts?.removeEventListener("loadingdone", fit);
    };
  }, [fit]);

  return (
    <textarea
      ref={ref}
      value={value}
      rows={1}
      className={clsx("resize-none", singleLine && "overflow-hidden", className)}
      onChange={(event) => {
        if (singleLine && /[\r\n]/.test(event.target.value)) {
          event.target.value = event.target.value.replace(/\s*[\r\n]+\s*/g, " ");
        }
        onChange?.(event);
      }}
      onKeyDown={(event) => {
        if (singleLine && event.key === "Enter" && !event.nativeEvent.isComposing) {
          event.preventDefault();
        }
        onKeyDown?.(event);
      }}
      {...props}
    />
  );
}

export function TypingDots({ label = "Thinking" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-ink-subtle" role="status" aria-label={label}>
      <span className="typing-dot size-1.5 rounded-full bg-current" />
      <span className="typing-dot size-1.5 rounded-full bg-current" />
      <span className="typing-dot size-1.5 rounded-full bg-current" />
    </span>
  );
}
