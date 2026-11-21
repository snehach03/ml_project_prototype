import { TimeSeries } from "../components/charts.jsx";
import { Card, Empty, ErrorNote, Spinner, Stat } from "../components/ui.jsx";
import { useFetch, useMonitoring } from "../hooks/useMonitoring.jsx";
import { api } from "../lib/api.js";
import { num, percent } from "../lib/format.js";

const LABELS = {
  keystrokes: "Typing volume (keys/min)", typing_speed_cpm: "Typing speed (chars/min)", backspace_ratio: "Backspace ratio",
  mouse_activity: "Mouse activity", mouse_distance: "Mouse distance (px/min)", clicks: "Clicks/min",
  scroll_events: "Scroll bursts/min", switches: "Focus changes/min",
};

export default function Analytics() {
  const { selectedSessionId, tick, running } = useMonitoring();
  const sessions = useFetch(() => api.listSessions(), [tick]);
  const id = selectedSessionId || (sessions.data && sessions.data[0] ? sessions.data[0].id : null);
  const analytics = useFetch(() => (id ? api.analytics(id) : Promise.resolve(null)), [id, tick]);
  const { setSelectedSessionId } = useMonitoring();

  if (sessions.loading && !sessions.data) return <Spinner />;
  if (!id) return <Empty>No sessions yet. Start monitoring first.</Empty>;
  if (analytics.error) return <ErrorNote>{analytics.error}</ErrorNote>;
  const data = analytics.data;
  if (!data) return <Spinner />;
  const series = data.series;
  const changes = data.pattern_changes;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-slate-400" htmlFor="session-select">Session</label>
        <select id="session-select" value={id} onChange={(e) => setSelectedSessionId(e.target.value)}
          className="rounded-xl border border-slate-700 bg-ink-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
          {(sessions.data || []).map((s) => (
            <option key={s.id} value={s.id}>{new Date(s.started_at).toLocaleString()} ({s.minutes_recorded} min{s.status === "active" ? ", live" : ""})</option>
          ))}
        </select>
        {running && <span className="text-xs text-emerald-300">updating live</span>}
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Avg typing speed" value={num(data.summary.avg_typing_speed_cpm) + " cpm"} />
        <Stat label="Avg backspace ratio" value={num((data.summary.avg_backspace_ratio || 0) * 100, 1) + " %"} />
        <Stat label="Typing variability (CV)" value={num(data.variability.typing_cv, 2)} hint="std / mean across minutes" />
        <Stat label="Mouse variability (CV)" value={num(data.variability.mouse_distance_cv, 2)} hint="std / mean across minutes" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Typing speed timeline" subtitle="Characters and keystrokes per minute">
          <TimeSeries data={series} kind="line" series={[{ key: "typing_speed_cpm", name: "chars/min", color: "#7c8cff" }, { key: "keystrokes", name: "keystrokes/min", color: "#a5b0ff" }]} />
        </Card>
        <Card title="Correction behaviour" subtitle="Share of keystrokes that were backspace/delete">
          <TimeSeries data={series} kind="line" series={[{ key: "backspace_ratio", name: "backspace ratio", color: "#f68098" }]} />
        </Card>
        <Card title="Mouse movement timeline" subtitle="Cursor distance (px) and activity bursts per minute">
          <TimeSeries data={series} kind="area" series={[{ key: "mouse_distance", name: "distance px", color: "#4fd1c5" }]} />
        </Card>
        <Card title="Scroll frequency" subtitle="Scroll bursts per minute">
          <TimeSeries data={series} kind="bar" series={[{ key: "scroll_events", name: "scroll bursts", color: "#f6ad55" }]} />
        </Card>
        <Card title="Idle time" subtitle="Seconds per minute without any input (display only, not a model input)">
          <TimeSeries data={series} kind="bar" yDomain={[0, 60]} series={[{ key: "idle_seconds", name: "idle seconds", color: "#64748b" }]} />
        </Card>
        <Card title="Focus changes" subtitle="Page blur / hidden events per minute">
          <TimeSeries data={series} kind="bar" series={[{ key: "switches", name: "focus changes", color: "#7c8cff" }]} />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Interaction pattern changes" subtitle="First half of the session vs second half">
          {changes ? (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-slate-500"><th className="pb-2">Metric</th><th>First half</th><th>Second half</th><th>Change</th></tr></thead>
              <tbody>
                {Object.entries(changes).map(([key, v]) => (
                  <tr key={key} className="border-t border-slate-800">
                    <td className="py-2 text-slate-300">{LABELS[key] || key}</td><td>{num(v.first_half, 2)}</td><td>{num(v.second_half, 2)}</td>
                    <td className={v.percent_change > 0 ? "text-amber-300" : "text-teal-300"}>{percent(v.percent_change)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty>Needs at least 6 minutes of data.</Empty>}
        </Card>
        <Card title="Comparison with your earlier sessions" subtitle="This session vs your own history per minute">
          {data.versus_baseline ? (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-slate-500"><th className="pb-2">Metric</th><th>This session</th><th>Usually</th><th>Diff</th></tr></thead>
              <tbody>
                {Object.entries(data.versus_baseline).map(([key, v]) => (
                  <tr key={key} className="border-t border-slate-800">
                    <td className="py-2 text-slate-300">{LABELS[key] || key}</td><td>{num(v.session_mean, 2)}</td><td>{num(v.history_mean, 2)}</td>
                    <td className={v.percent_difference > 0 ? "text-amber-300" : "text-teal-300"}>{percent(v.percent_difference)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty>Complete at least one earlier session to see a personal comparison.</Empty>}
        </Card>
      </div>
    </div>
  );
}
