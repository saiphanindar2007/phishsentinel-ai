// PhishSentinel AI — shared UI primitives
// --------------------------------------------
// One place for button, input, select and empty-state styling so every
// tab looks like the same product instead of nine slightly different ones.
import { Loader2 } from "lucide-react";

const VARIANTS = {
  primary: "bg-navy text-white hover:bg-navy-4 focus-visible:ring-navy disabled:bg-navy/50",
  teal: "bg-teal text-white hover:bg-teal/90 focus-visible:ring-teal disabled:bg-teal/50",
  secondary: "bg-white text-ink border border-line hover:bg-gray-50 focus-visible:ring-navy",
  danger: "bg-white text-danger border border-red-200 hover:bg-red-50 focus-visible:ring-danger",
  ghost: "bg-transparent text-slate hover:text-ink hover:bg-gray-100 focus-visible:ring-navy",
};

const SIZES = {
  sm: "text-xs px-2.5 py-1.5 gap-1.5",
  md: "text-sm px-3.5 py-2 gap-2",
};

export function Button({ variant = "secondary", size = "md", loading = false, disabled, className = "", children, ...rest }) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors
        disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1
        ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {loading && <Loader2 size={size === "sm" ? 12 : 14} className="animate-spin" />}
      {children}
    </button>
  );
}

export function IconButton({ className = "", children, ...rest }) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg p-2 text-slate hover:text-ink hover:bg-gray-100
        transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

const fieldBase =
  "w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-slate/70 " +
  "transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal disabled:bg-gray-50 disabled:text-slate";

export function Input({ className = "", ...rest }) {
  return <input className={`${fieldBase} ${className}`} {...rest} />;
}

export function Textarea({ className = "", ...rest }) {
  return <textarea className={`${fieldBase} resize-none ${className}`} {...rest} />;
}

export function Select({ className = "", children, ...rest }) {
  return (
    <select className={`${fieldBase} pr-8 ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function Label({ children, hint }) {
  return (
    <label className="block text-xs font-semibold text-ink mb-1.5">
      {children} {hint && <span className="font-normal text-slate">{hint}</span>}
    </label>
  );
}

export function SectionLabel({ children }) {
  return <div className="text-[11px] font-semibold uppercase tracking-wide text-slate mb-2">{children}</div>;
}

export function EmptyState({ icon: Icon, title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      {Icon && (
        <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 text-slate">
          <Icon size={18} />
        </div>
      )}
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && <p className="max-w-xs text-xs text-slate">{hint}</p>}
    </div>
  );
}

export function FieldError({ children }) {
  if (!children) return null;
  return <p className="mt-2 text-xs font-medium text-danger">{children}</p>;
}

export function Divider({ className = "" }) {
  return <div className={`h-px bg-line ${className}`} />;
}

export function Kbd({ children }) {
  return (
    <kbd className="inline-flex items-center rounded border border-line bg-gray-50 px-1.5 py-0.5 font-mono-ui text-[10px] text-slate">
      {children}
    </kbd>
  );
}
