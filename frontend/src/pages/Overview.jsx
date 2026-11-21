import { TimeSeries } from "../components/charts.jsx";
import { Badge, Card, Disclaimer, ErrorNote, LeaningBadge, ScoreMeter, Spinner, Stat } from "../components/ui.jsx";
import { useFetch, useMonitoring } from "../hooks/useMonitoring.jsx";
import { api } from "../lib/api.js";
import { dateTime, minutesText, num } from "../lib/format.js";

export default function Overview({ go }) {
  const { running, estimate, tick, liveSeries } = useMonitoring();
  const overview = useFetch(() => api.overview(), [tick, running]);
  const latestId = overview.data && overview.data.latest ? overview.data.latest.id : null;
  const latest = useFetch(() => (latestId ? api.analytics(latestId) : Promise.resolve(null)), [latestId, tick]);

  if (overview.loading && !overview.data) return <Spinner />;
  if (overview.error) return <ErrorNote>{overview.error}</ErrorNote>;
  const data = overview.data;

  const trend = data.trend.map((t, index) => ({
    label: "#" + (index + 1),
    keystrokes: t.avg_keystrokes_per_min,
    mouse: t.avg_mouse_distance_per_min,
    switches: t.total_switches,
    stress: t.stress_session_score,
  }));
  const stress = estimate && estimate.stress ? estimate.stress : null;
  const summary = latest.data ? latest.data.summary : null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Session status" value={running ? "Monitoring" : "Idle"} tone={running ? "text-emerald-300" : "text-slate-300"}
          hint={running ? liveSeries.length + " min recorded" : "No active monitoring"} />
        <Stat label="Sessions" value={num(data.session_count)} hint="last 30 shown" />
        <Stat label="Minutes recorded" value={num(data.total_minutes)} />
        <Stat label="Latest session" value={data.latest ? minutesText(data.latest.minutes_recorded) : "-"}
          hint={data.latest ? dateTime(data.latest.started_at) : "Nothing recorded yet"} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Estimated stress indicator" subtitle="Relative to your own baseline, experimental" className="lg:col-span-1"
          right={stress ? <LeaningBadge leaning={stress.leaning} /> : null}>
          {stress ? (
            <div className="space-y-4">
              <ScoreMeter score={stress.score} reliable={stress.reliable} />
              <p className="text-xs text-slate-400">{stress.score_note}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400">
              {running ? (estimate && estimate.message) || "Collecting your first minutes..." : "Start monitoring to get an estimate. The first one needs a few minutes of activity plus a personal baseline."}
            </p>
          )}
          <button className="mt-4 text-xs text-indigo-300 hover:underline" onClick={() => go("prediction")}>Open full AI prediction</button>
        </Card>

        <Card title="Behavioural activity summary" subtitle="Most recent session" className="lg:col-span-2">
          {summary && summary.minutes > 0 ? (
            <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div><dt className="text-xs text-slate-500">Typing speed</dt><dd className="text-lg font-semibold">{num(summary.avg_typing_speed_cpm)}<span className="text-xs text-slate-500"> chars/min</span></dd></div>
              <div><dt className="text-xs text-slate-500">Backspace ratio</dt><dd className="text-lg font-semibold">{num(summary.avg_backspace_ratio * 100, 1)}<span className="text-xs text-slate-500"> %</span></dd></div>
              <div><dt className="text-xs text-slate-500">Clicks</dt><dd className="text-lg font-semibold">{num(summary.total_clicks)}</dd></div>
              <div><dt className="text-xs text-slate-500">Focus changes</dt><dd className="text-lg font-semibold">{num(summary.total_switches)}</dd></div>
            </dl>
          ) : (
            <p className="text-sm text-slate-400">No behavioural data recorded yet.</p>
          )}
          <div className="mt-4 flex items-center gap-2">
            <Badge tone="indigo">Counters only</Badge>
            <span className="text-xs text-slate-500">Typed text is never recorded.</span>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Historical trend: typing volume" subtitle="Average keystrokes per minute, per session">
          <TimeSeries data={trend} xKey="label" series={[{ key: "keystrokes", name: "Keystrokes/min", color: "#7c8cff" }]} kind="area" />
        </Card>
        <Card title="Historical trend: stress indicator" subtitle="Mean model score per session (0-1, grey band = unclear)">
          <TimeSeries data={trend.filter((t) => t.stress !== null && t.stress !== undefined)} xKey="label"
            series={[{ key: "stress", name: "Score", color: "#f6ad55" }]} yDomain={[0, 1]} band={[0.4, 0.6]} />
        </Card>
      </div>
      <Disclaimer />
    </div>
  );
}
