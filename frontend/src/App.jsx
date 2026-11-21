import { useEffect, useState } from "react";
import ConsentModal from "./components/ConsentModal.jsx";
import { Badge } from "./components/ui.jsx";
import { MonitoringProvider, useMonitoring } from "./hooks/useMonitoring.jsx";
import Analytics from "./pages/Analytics.jsx";
import History from "./pages/History.jsx";
import Live from "./pages/Live.jsx";
import Overview from "./pages/Overview.jsx";
import Prediction from "./pages/Prediction.jsx";

const PAGES = [
  { id: "overview", label: "Overview", icon: "M3 12l9-9 9 9M5 10v10h14V10" },
  { id: "live", label: "Live monitor", icon: "M3 12h4l3-8 4 16 3-8h4" },
  { id: "analytics", label: "Analytics", icon: "M4 20V10M10 20V4M16 20v-7M22 20H2" },
  { id: "prediction", label: "AI prediction", icon: "M12 2a7 7 0 00-4 12.7V18h8v-3.3A7 7 0 0012 2zM9 21h6" },
  { id: "history", label: "History", icon: "M12 8v5l3 2M3 12a9 9 0 109-9 9 9 0 00-7 3.5M3 4v4h4" },
];

function Icon({ d }) {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

function readPage() {
  const hash = window.location.hash.replace("#", "");
  return PAGES.some((p) => p.id === hash) ? hash : "overview";
}

function Shell() {
  const [page, setPage] = useState(readPage());
  const [consentOpen, setConsentOpen] = useState(false);
  const { running, start, error, clearError, backendError, wsState } = useMonitoring();

  useEffect(() => {
    const onHash = () => setPage(readPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function go(id) {
    window.location.hash = id;
    setPage(id);
  }

  async function accept() {
    setConsentOpen(false);
    await start();
    go("live");
  }

  let content = null;
  if (page === "overview") content = <Overview go={go} />;
  if (page === "live") content = <Live onRequestStart={() => setConsentOpen(true)} />;
  if (page === "analytics") content = <Analytics />;
  if (page === "prediction") content = <Prediction />;
  if (page === "history") content = <History go={go} />;

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden w-64 shrink-0 border-r border-slate-800 bg-ink-900/60 p-5 backdrop-blur md:block">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-400 to-teal-300 text-ink-950 font-bold">B</div>
          <div>
            <p className="text-sm font-semibold text-slate-50">BehaviorSense</p>
            <p className="text-[11px] text-slate-500">HCI stress &amp; workload estimates</p>
          </div>
        </div>
        <nav className="space-y-1">
          {PAGES.map((p) => (
            <button key={p.id} onClick={() => go(p.id)}
              className={"flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition " + (page === p.id ? "bg-indigo-400/10 text-indigo-200 ring-1 ring-inset ring-indigo-400/30" : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100")}>
              <Icon d={p.icon} />{p.label}
            </button>
          ))}
        </nav>
        <div className="mt-8 rounded-xl border border-slate-800 p-3 text-[11px] leading-relaxed text-slate-500">
          Research prototype. Not a medical device. Counters only: typed text is never recorded.
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-800 bg-ink-950/80 px-4 py-3 backdrop-blur md:px-8">
          <h1 className="text-base font-semibold text-slate-50 md:text-lg">{PAGES.find((p) => p.id === page).label}</h1>
          <div className="flex items-center gap-3">
            {running ? (
              <Badge tone="green"><span className="h-1.5 w-1.5 rounded-full bg-current pulse-dot" />Monitoring {wsState === "open" ? "" : "(reconnecting)"}</Badge>
            ) : (
              <Badge tone="slate">Not monitoring</Badge>
            )}
          </div>
        </header>

        <main className="flex-1 space-y-4 px-4 py-6 pb-24 md:px-8 md:pb-10">
          {backendError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
              Cannot reach the backend ({backendError}). Start it with <code>uvicorn backend.app.main:app --port 8000</code> from the project root.
            </div>
          )}
          {error && (
            <div className="flex items-start justify-between gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-100">
              <span>{error}</span><button onClick={clearError} className="text-xs underline">dismiss</button>
            </div>
          )}
          {content}
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-slate-800 bg-ink-950/95 backdrop-blur md:hidden">
        {PAGES.map((p) => (
          <button key={p.id} onClick={() => go(p.id)} className={"flex flex-col items-center gap-1 py-2 text-[10px] " + (page === p.id ? "text-indigo-300" : "text-slate-500")}>
            <Icon d={p.icon} />{p.label.split(" ")[0]}
          </button>
        ))}
      </nav>

      <ConsentModal open={consentOpen} onAccept={accept} onCancel={() => setConsentOpen(false)} />
    </div>
  );
}

export default function App() {
  return (
    <MonitoringProvider>
      <Shell />
    </MonitoringProvider>
  );
}
