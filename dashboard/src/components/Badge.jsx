const STYLES = {
  safe: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20",
  suspicious: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20",
  phishing: "bg-red-50 text-danger ring-1 ring-inset ring-red-600/20",
};
const DOT = { safe: "bg-emerald-500", suspicious: "bg-amber-500", phishing: "bg-danger" };

export default function Badge({ verdict, compact = false }) {
  const style = STYLES[verdict] || "bg-gray-100 text-slate ring-1 ring-inset ring-gray-300";
  const dot = DOT[verdict] || "bg-slate";
  const size = compact ? "px-1.5 py-0.5 text-[10px] gap-1" : "px-2.5 py-1 text-[11px] gap-1.5";
  return (
    <span className={`inline-flex items-center rounded-full font-semibold capitalize ${style} ${size}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {verdict}
    </span>
  );
}
