import { useState } from "react";
import { Badge, Card, Empty, ErrorNote, LeaningBadge, Spinner } from "../components/ui.jsx";
import { useFetch, useMonitoring } from "../hooks/useMonitoring.jsx";
import { api } from "../lib/api.js";
import { dateTime, minutesText, num } from "../lib/format.js";

export default function History({ go }) {
  const { tick, setSelectedSessionId } = useMonitoring();
  const [version, setVersion] = useState(0);
  const [message, setMessage] = useState(null);
  const sessions = useFetch(() => api.listSessions(), [tick, version]);

  async function remove(id) {
    if (!window.confirm("Delete this session and its data permanently?")) return;
    await api.deleteSession(id);
    setVersion((v) => v + 1);
  }

  async function removeAll() {
    if (!window.confirm("Delete ALL your stored sessions permanently? This cannot be undone.")) return;
    await api.deleteAllData();
    setMessage("All your data has been deleted.");
    setVersion((v) => v + 1);
  }

  function open(id, page) {
    setSelectedSessionId(id);
    go(page);
  }

  if (sessions.loading && !sessions.data) return <Spinner />;
  if (sessions.error) return <ErrorNote>{sessions.error}</ErrorNote>;

  return (
    <div className="space-y-6">
      {message && <div className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-3 text-sm text-emerald-200">{message}</div>}
      <Card title="Session history" subtitle="Stored per browser. Only counters are saved, never typed text."
        right={<button onClick={removeAll} className="rounded-lg border border-rose-400/30 px-3 py-1.5 text-xs text-rose-300 transition hover:bg-rose-400/10">Delete all my data</button>}>
        {sessions.data.length === 0 ? <Empty>No sessions yet.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead><tr className="text-left text-xs text-slate-500"><th className="pb-2">Started</th><th>Length</th><th>Status</th><th>Stress indicator</th><th /></tr></thead>
              <tbody>
                {sessions.data.map((s) => (
                  <tr key={s.id} className="border-t border-slate-800 transition hover:bg-slate-800/30">
                    <td className="py-3 text-slate-200">{dateTime(s.started_at)}</td>
                    <td>{minutesText(s.minutes_recorded)}</td>
                    <td><Badge tone={s.status === "active" ? "green" : "slate"}>{s.status}</Badge></td>
                    <td>
                      {s.stress_leaning ? (<span className="flex items-center gap-2"><LeaningBadge leaning={s.stress_leaning} /><span className="text-xs text-slate-500">{num(s.stress_session_score, 2)}</span></span>) : <span className="text-xs text-slate-500">not enough data</span>}
                    </td>
                    <td className="space-x-3 text-right text-xs">
                      <button className="text-indigo-300 hover:underline" onClick={() => open(s.id, "analytics")}>Analytics</button>
                      <button className="text-indigo-300 hover:underline" onClick={() => open(s.id, "prediction")}>Prediction</button>
                      <button className="text-rose-300 hover:underline" onClick={() => remove(s.id)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
