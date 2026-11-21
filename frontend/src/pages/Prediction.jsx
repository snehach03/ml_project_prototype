import { TimeSeries } from "../components/charts.jsx";
import { Badge, Card, Contributions, Disclaimer, Empty, LeaningBadge, ScoreMeter, Spinner } from "../components/ui.jsx";
import { useFetch, useMonitoring } from "../hooks/useMonitoring.jsx";
import { api } from "../lib/api.js";
import { CONFIDENCE, num } from "../lib/format.js";

function Evidence({ stress }) {
  const ci = stress.loso_block_roc_auc_ci95;
  return (
    <div className="rounded-xl border border-slate-800 bg-ink-950/60 p-3 text-xs leading-relaxed text-slate-400">
      <p>
        <strong className="text-slate-200">How well does this model work?</strong> On participants it had never seen,
        the block-level ROC-AUC was <strong className="text-slate-200">{num(stress.loso_block_roc_auc, 2)}</strong>
        {" "}(95% CI {num(ci[0], 2)} to {num(ci[1], 2)}; 0.5 = coin flip). {stress.evidence}
      </p>
    </div>
  );
}

export default function Prediction() {
  const { selectedSessionId, estimate, running, tick, info } = useMonitoring();
  const sessions = useFetch(() => api.listSessions(), [tick]);
  const id = selectedSessionId || (sessions.data && sessions.data[0] ? sessions.data[0].id : null);
  const stored = useFetch(() => (id ? api.prediction(id) : Promise.resolve(null)), [id, tick]);
  const analytics = useFetch(() => (id ? api.analytics(id) : Promise.resolve(null)), [id, tick]);

  if (!id) return <Empty>No sessions yet. Start monitoring on the Live tab.</Empty>;
  const current = running && estimate ? estimate : stored.data;
  if (!current) return <Spinner />;

  if (current.status !== "ok") {
    return (
      <div className="space-y-6">
        <Card title="AI prediction" subtitle="Waiting for enough data">
          <p className="text-sm text-slate-300">{current.message}</p>
          {current.baseline_progress && (
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full rounded-full bg-indigo-400 transition-all duration-700" style={{ width: (current.baseline_progress[0] / current.baseline_progress[1]) * 100 + "%" }} />
            </div>
          )}
        </Card>
        <Disclaimer />
      </div>
    );
  }

  const stress = current.stress;
  const workload = current.workload;
  const timeline = stress.timeline.map((t) => ({ minute: t.window_end_minute, score: t.score }));
  const model = info && info.models ? info.models.stress : null;
  const baselineText = current.baseline_source === "previous_sessions"
    ? "your earlier sessions"
    : "this session so far (provisional: it includes the minutes being judged, so differences are damped)";

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3" title="Stress-related indicator" subtitle={"Compared with " + baselineText}
          right={<LeaningBadge leaning={stress.leaning} />}>
          <div className="space-y-5">
            <ScoreMeter score={stress.score} reliable={stress.reliable} />
            <div className="grid gap-3 text-sm sm:grid-cols-3">
              <div><p className="text-xs text-slate-500">Recent score</p><p className="text-lg font-semibold">{num(stress.score, 2)}</p></div>
              <div><p className="text-xs text-slate-500">Whole-session score</p><p className="text-lg font-semibold">{num(stress.session_score, 2)}</p></div>
              <div><p className="text-xs text-slate-500">Confidence</p><p className="text-sm font-medium text-slate-200">{CONFIDENCE[stress.confidence]}</p></div>
            </div>
            <p className="text-xs text-slate-500">{stress.score_note}</p>
            <Evidence stress={stress} />
          </div>
        </Card>

        <Card className="lg:col-span-2" title="Cognitive workload estimate" subtitle="Experimental" right={<Badge tone="rose">not reliable</Badge>}>
          {workload ? (
            <div className="space-y-4">
              <ScoreMeter score={workload.score} reliable={false} />
              <p className="text-xs leading-relaxed text-slate-400">
                This model did <strong className="text-rose-300">not</strong> beat chance on held-out participants
                (ROC-AUC {num(workload.loso_block_roc_auc, 2)}, 95% CI {num(workload.loso_block_roc_auc_ci95[0], 2)} to {num(workload.loso_block_roc_auc_ci95[1], 2)}).
                It is shown only for transparency. Do not interpret it.
              </p>
            </div>
          ) : <Empty>Workload model unavailable.</Empty>}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="What influenced this estimate" subtitle="SHAP: the behaviours that moved the latest window's score most">
          <Contributions items={stress.contributions} />
        </Card>
        <Card title="Score over the session" subtitle="Each point = one 5-minute window. Grey band = unclear zone.">
          <TimeSeries data={timeline} series={[{ key: "score", name: "model score", color: "#f6ad55" }]} yDomain={[0, 1]} band={[0.4, 0.6]} />
        </Card>
      </div>

      <Card title="Comparison with your previous baseline" subtitle="This session's per-minute behaviour vs your earlier sessions">
        {analytics.data && analytics.data.versus_baseline ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(analytics.data.versus_baseline).map(([key, v]) => (
              <div key={key} className="rounded-xl border border-slate-800 p-3">
                <p className="text-xs capitalize text-slate-500">{key.replace(/_/g, " ")}</p>
                <p className="mt-1 text-sm text-slate-200">{num(v.session_mean, 2)} <span className="text-slate-500">vs {num(v.history_mean, 2)}</span></p>
              </div>
            ))}
          </div>
        ) : <Empty>No earlier sessions yet, so there is no personal baseline to compare with.</Empty>}
      </Card>

      {model && (
        <Card title="About the model" subtitle="Trained on SWELL-KW (25 participants, 75 labelled blocks)">
          <p className="text-xs leading-relaxed text-slate-400">
            Model: {model.model} (version {model.version}). Validation: leave-one-subject-out. Window: {model.window_minutes} minutes.
            Within-person permutation check p = {num(model.permutation_p, 3)}. The score is a model output, not a calibrated probability, and
            browser events only approximate the system-wide logging the model was trained on.
          </p>
        </Card>
      )}
      <Disclaimer />
    </div>
  );
}
