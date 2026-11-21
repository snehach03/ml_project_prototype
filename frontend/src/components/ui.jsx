import { LEANING } from "../lib/format.js";

const TONES = {
  amber: "bg-amber-400/10 text-amber-300 ring-amber-400/30",
  cyan: "bg-teal-400/10 text-teal-300 ring-teal-400/30",
  slate: "bg-slate-500/10 text-slate-300 ring-slate-400/30",
  rose: "bg-rose-400/10 text-rose-300 ring-rose-400/30",
  indigo: "bg-indigo-400/10 text-indigo-300 ring-indigo-400/30",
  green: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/30",
};

export function Badge({ tone = "slate", children }) {
  return (
    <span className={"inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset " + TONES[tone]}>
      {children}
    </span>
  );
}

export function Card({ title, subtitle, right, children, className = "" }) {
  return (
    <section className={"fade-in rounded-2xl border border-slate-800 bg-ink-900/70 p-5 backdrop-blur " + className}>
      {(title || right) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h3 className="text-sm font-semibold tracking-wide text-slate-100">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, tone }) {
  return (
    <div className="fade-in rounded-2xl border border-slate-800 bg-ink-900/70 p-4 transition hover:border-indigo-400/40">
      <p className="text-xs uppercase tracking-wider text-slate-400">{label}</p>
      <p className={"mt-2 text-2xl font-semibold " + (tone || "text-slate-50")}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function Empty({ children }) {
  return <div className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-400">{children}</div>;
}

export function Spinner() {
  return <div className="p-6 text-center text-sm text-slate-500 pulse-dot">Loading...</div>;
}

export function ErrorNote({ children }) {
  return <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{children}</div>;
}

export function Disclaimer() {
  return (
    <div className="rounded-xl border border-indigo-400/20 bg-indigo-400/5 p-3 text-xs leading-relaxed text-slate-300">
      <strong className="text-indigo-200">Research prototype, not a diagnosis.</strong> Estimates compare your current
      behaviour with <em>your own</em> usual behaviour and are based on a small study (25 people). They cannot tell
      whether you are stressed and must not be used for medical, employment or disciplinary decisions.
    </div>
  );
}

export function LeaningBadge({ leaning }) {
  const entry = LEANING[leaning] || LEANING.unclear;
  return <Badge tone={entry.tone}>{entry.label}</Badge>;
}

/** 0..1 model score with the 0.40-0.60 'unclear' band shaded. NOT a probability. */
export function ScoreMeter({ score, reliable }) {
  const position = Math.max(0, Math.min(1, score)) * 100;
  return (
    <div>
      <div className="relative h-3 rounded-full bg-slate-800">
        <div className="absolute inset-y-0 rounded-full bg-slate-600/60" style={{ left: "40%", width: "20%" }} />
        <div
          className={"absolute -top-1 h-5 w-1.5 rounded-full shadow-glow transition-all duration-700 " + (reliable ? "bg-indigo-300" : "bg-slate-400")}
          style={{ left: "calc(" + position + "% - 3px)" }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] uppercase tracking-wider text-slate-500">
        <span>lower than usual</span><span>unclear</span><span>higher than usual</span>
      </div>
    </div>
  );
}

export function Contributions({ items }) {
  if (!items || items.length === 0) return null;
  const maxValue = Math.max(...items.map((i) => Math.abs(i.shap)), 1e-9);
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.feature}>
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="text-slate-200">{item.description}</span>
            <span className={item.direction === "up" ? "text-amber-300" : "text-teal-300"}>
              {item.direction === "up" ? "pushes up" : "pushes down"}
            </span>
          </div>
          <div className="mt-1 flex h-2 items-center">
            <div className="flex h-full w-1/2 justify-end">
              {item.direction === "down" && (
                <div className="h-full rounded-l-full bg-teal-400/80 transition-all duration-700" style={{ width: (Math.abs(item.shap) / maxValue) * 100 + "%" }} />
              )}
            </div>
            <div className="h-4 w-px bg-slate-600" />
            <div className="flex h-full w-1/2">
              {item.direction === "up" && (
                <div className="h-full rounded-r-full bg-amber-400/80 transition-all duration-700" style={{ width: (Math.abs(item.shap) / maxValue) * 100 + "%" }} />
              )}
            </div>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">{item.explanation}</p>
        </li>
      ))}
    </ul>
  );
}
