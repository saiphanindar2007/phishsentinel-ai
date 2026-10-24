export default function Panel({ title, description, icon: Icon, right, children, className = "", bodyClassName = "" }) {
  return (
    <section className={`bg-white rounded-2xl border border-line shadow-card mb-5 overflow-hidden ${className}`}>
      {(title || right) && (
        <div className="px-5 py-3.5 border-b border-line flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            {Icon && (
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-navy/5 text-navy">
                <Icon size={14} />
              </span>
            )}
            <div className="min-w-0">
              {title && <div className="font-semibold text-sm text-ink truncate">{title}</div>}
              {description && <div className="text-xs text-slate truncate">{description}</div>}
            </div>
          </div>
          {right && <div className="shrink-0">{right}</div>}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
