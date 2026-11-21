import { type ButtonHTMLAttributes, forwardRef, type ReactNode, useEffect, useRef } from "react";

/**
 * Small V2 UI kit built on the Berry/Lime tokens (docs/v2/design). Buttons default to the 48 px
 * touch size used on phones; only one primary button is shown per region.
 */

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "lg" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-berry-600 text-white hover:bg-berry-700 active:bg-berry-800 shadow-xs",
  secondary: "bg-lime-300 text-on-accent hover:bg-lime-400 active:bg-lime-500",
  outline: "border-[1.5px] border-berry-600 bg-surface text-berry-600 hover:bg-berry-50 active:bg-berry-100",
  ghost: "text-fg-2 hover:bg-sunken hover:text-fg active:bg-neutral-200",
  danger: "border-[1.5px] border-error-600 bg-surface text-error-600 hover:bg-error-50",
};

const SIZES: Record<Size, string> = {
  lg: "min-h-12 px-5 text-base",
  md: "min-h-11 px-4 text-sm",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  block?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "lg", icon, block = false, className = "", children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-md font-bold transition-colors duration-150 disabled:cursor-not-allowed disabled:border-transparent disabled:bg-neutral-100 disabled:text-neutral-400 disabled:shadow-none ${VARIANTS[variant]} ${SIZES[size]} ${block ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {icon && (
        <span aria-hidden="true" className="flex shrink-0">
          {icon}
        </span>
      )}
      {children}
    </button>
  );
});

type Tone = "neutral" | "brand" | "accent" | "success" | "warning" | "error" | "info";

const TONES: Record<Tone, string> = {
  neutral: "bg-neutral-100 text-neutral-800",
  brand: "bg-berry-100 text-berry-700",
  accent: "bg-lime-300 text-on-accent",
  success: "bg-success-50 text-success-700",
  warning: "bg-warning-50 text-warning-700",
  error: "bg-error-50 text-error-700",
  info: "bg-info-50 text-info-700",
};

export function Badge({
  tone = "neutral",
  icon,
  children,
  className = "",
  ...rest
}: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string } & Record<`data-${string}`, string>) {
  return (
    <span
      className={`inline-flex min-h-6 items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${TONES[tone]} ${className}`}
      {...rest}
    >
      {icon && (
        <span aria-hidden="true" className="flex shrink-0">
          {icon}
        </span>
      )}
      {children}
    </span>
  );
}

/** Two-line bilingual label: Kannada first, English underneath (or inline when compact). */
export function Bilingual({ kn, en, className = "" }: { kn: string; en: string; className?: string }) {
  return (
    <span className={`flex flex-col ${className}`}>
      <span lang="kn">{kn}</span>
      <span className="text-sm font-semibold text-fg-2">{en}</span>
    </span>
  );
}

/**
 * Thumb-zone sheet. On phones it is pinned to the bottom of the screen (non-modal: the map and
 * list stay usable behind it); from the lg breakpoint it sits in the detail column.
 */
export function Sheet({
  children,
  className = "",
  testId,
  labelledBy,
}: {
  children: ReactNode;
  className?: string;
  testId?: string;
  labelledBy?: string;
}) {
  return (
    <section
      aria-labelledby={labelledBy}
      data-testid={testId}
      className={`v2-rise fixed inset-x-0 bottom-0 z-30 max-h-[78vh] overflow-y-auto rounded-t-xl border-t border-line bg-surface px-4 pt-2 pb-[max(env(safe-area-inset-bottom),1rem)] shadow-xl lg:static lg:z-auto lg:max-h-none lg:rounded-lg lg:border lg:pb-5 lg:shadow-sm ${className}`}
    >
      <div aria-hidden="true" className="mx-auto mb-3 h-1 w-10 rounded-full bg-neutral-300 lg:hidden" />
      {children}
    </section>
  );
}

/** Accessible confirmation dialog on the native <dialog> element (focus trap, Esc to close). */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-body"
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
      className="v2 m-auto w-[min(92vw,26rem)] rounded-xl border-0 bg-surface p-0 shadow-xl backdrop:bg-[rgba(31,26,24,0.48)]"
    >
      <div className="flex flex-col gap-3 p-5">
        <h2 id="confirm-dialog-title" className="text-xl font-extrabold leading-tight">
          {title}
        </h2>
        <p id="confirm-dialog-body" className="text-fg-2">
          {body}
        </p>
        <div className="mt-2 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}

/** Calm inline notice (status colour always comes with an icon and words). */
export function Notice({
  tone,
  icon,
  title,
  children,
  role,
  className = "",
  testId,
}: {
  tone: "info" | "success" | "warning" | "error" | "brand";
  icon: ReactNode;
  title?: ReactNode;
  children?: ReactNode;
  role?: "alert" | "status";
  className?: string;
  testId?: string;
}) {
  const tones = {
    info: "border-info-200 bg-info-50 [--accent:var(--color-info-600)] [--title:var(--color-info-700)]",
    success: "border-success-200 bg-success-50 [--accent:var(--color-success-600)] [--title:var(--color-success-700)]",
    warning: "border-warning-200 bg-warning-50 [--accent:var(--color-warning-600)] [--title:var(--color-warning-700)]",
    error: "border-error-200 bg-error-50 [--accent:var(--color-error-600)] [--title:var(--color-error-700)]",
    brand: "border-berry-200 bg-berry-50 [--accent:var(--color-berry-600)] [--title:var(--color-berry-700)]",
  }[tone];
  return (
    <div
      role={role}
      data-testid={testId}
      className={`flex gap-3 rounded-lg border border-l-4 border-l-[var(--accent)] p-3.5 text-sm ${tones} ${className}`}
    >
      <span aria-hidden="true" className="mt-0.5 flex shrink-0 text-[var(--accent)]">
        {icon}
      </span>
      <div className="min-w-0 flex-1 text-fg">
        {title && <p className="font-bold text-[var(--title)]">{title}</p>}
        {children}
      </div>
    </div>
  );
}
