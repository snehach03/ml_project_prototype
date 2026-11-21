import { useRef } from "react";
import { TimeSeries } from "../components/charts.jsx";
import { Badge, Card, Disclaimer, LeaningBadge, ScoreMeter, Stat } from "../components/ui.jsx";
import { useMonitoring } from "../hooks/useMonitoring.jsx";
import { num } from "../lib/format.js";

export default function Live({ onRequestStart }) {
  const { running, stop, liveSeries, preview, estimate, wsState, info } = useMonitoring();
  const practice = useRef(null);
  const seconds = preview ? preview.seconds : 0;
  const stress = estimate && estimate.stress ? estimate.stress : null;

  return (
    <div className="space-y-6">
      <Card
        title="Live interaction monitoring"
        subtitle="Aggregates your interaction into one-minute windows. Nothing you type is recorded."
        right={
          <div className="flex items-center gap-2">
            <Badge tone={wsState === "open" ? "green" : wsState === "connecting" ? "amber" : "slate"}>
              <span className={"h-1.5 w-1.5 rounded-full bg-current " + (wsState === "open" ? "pulse-dot" : "")} />
              {wsState === "open" ? "live link" : wsState}
            </Badge>
          </div>
        }
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex-1">
            <div className="h-2 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-teal-300 transition-all duration-1000" style={{ width: (running ? (seconds / 60) * 100 : 0) + "%" }} />
            </div>
            <p className="mt-2 text-xs text-slate-400">
              {running ? "Current minute: " + seconds + "s / 60s. " + liveSeries.length + " full minutes sent." : "Monitoring is off."}
              {" "}A first estimate needs {info ? info.window_minutes : 5} minutes, and {info ? info.min_baseline_windows + info.window_minutes - 1 : 14} minutes if you have no earlier sessions.
            </p>
          </div>
          {running ? (
            <button onClick={stop} className="rounded-xl bg-rose-500/90 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-rose-400">Stop monitoring</button>
          ) : (
            <button onClick={onRequestStart} disabled={!info} className="rounded-xl bg-indigo-500 px-5 py-2.5 text-sm font-medium text-white shadow-glow transition enabled:hover:bg-indigo-400 disabled:opacity-40">
              Start monitoring
            </button>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Keystrokes (this min)" value={preview ? num(preview.keystrokes) : "-"} hint={preview ? "backspace/delete: " + num(preview.error_keys) : ""} />
        <Stat label="Mouse distance" value={preview ? num(preview.mouse_distance) + " px" : "-"} hint={preview ? "clicks: " + num(preview.left_clicks + preview.right_clicks + preview.double_clicks) : ""} />
        <Stat label="Scroll bursts" value={preview ? num(preview.wheel) : "-"} hint={preview ? "drags: " + num(preview.drags) : ""} />
        <Stat label="Idle seconds" value={preview ? num(preview.idle_seconds) : "-"} hint={preview ? "focus changes: " + num(preview.app_changes + preview.tab_changes) : ""} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Practice area" subtitle="Type or scroll here to generate activity. This box is not read, stored or sent.">
          <textarea ref={practice} rows={6} placeholder="Type anything here while monitoring is on..."
            className="w-full resize-none rounded-xl border border-slate-700 bg-ink-950 p-3 text-sm text-slate-200 outline-none transition focus:border-indigo-400" />
        </Card>
        <Card title="Current estimate" subtitle="Updates every minute" right={stress ? <LeaningBadge leaning={stress.leaning} /> : null}>
          {stress ? (
            <div className="space-y-3">
              <ScoreMeter score={stress.score} reliable={stress.reliable} />
              <p className="text-xs text-slate-400">Baseline: {estimate.baseline_source === "previous_sessions" ? "your earlier sessions" : "this session so far (provisional)"}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400">{(estimate && estimate.message) || "Waiting for enough activity..."}</p>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Typing speed (live)" subtitle="Characters per minute">
          <TimeSeries data={liveSeries} series={[{ key: "typing_speed_cpm", name: "chars/min", color: "#7c8cff" }]} kind="area" />
        </Card>
        <Card title="Mouse movement (live)" subtitle="Cursor distance per minute (px)">
          <TimeSeries data={liveSeries} series={[{ key: "mouse_distance", name: "px/min", color: "#4fd1c5" }]} kind="area" />
        </Card>
      </div>
      <Disclaimer />
    </div>
  );
}
