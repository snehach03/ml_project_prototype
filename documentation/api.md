# API reference

Base URL (dev): `http://localhost:8000`. Interactive docs: `/docs` (Swagger) and `/redoc`.

All `/api/sessions*`, `/api/overview` and `/api/data` calls need the header
`X-Client-Id: <16-64 chars [A-Za-z0-9_-]>`. The React app generates one per browser and stores it in localStorage.
It scopes data to that browser; it is **not** authentication (see "Production hardening" in the README).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness + whether the model is loaded |
| GET | `/api/model/info` | model names, versions, LOSO metrics, feature list, consent text version |
| POST | `/api/sessions/start` | body `{"consent": true, "consent_version": "2026-11-v1"}` -> `{session_id, baseline_available}`. 400 without consent. Ends any older active session of the same client. |
| POST | `/api/sessions/{id}/stop` | stop; returns session summary |
| POST | `/api/sessions/{id}/metrics` | one minute of aggregated counters -> stored + model estimate |
| GET | `/api/sessions` | list this client's sessions |
| GET | `/api/sessions/{id}` | summary + last estimate |
| GET | `/api/sessions/{id}/prediction` | last model estimate |
| GET | `/api/sessions/{id}/analytics` | per-minute series, summary, variability, first-vs-second-half changes, comparison with earlier sessions, estimate history |
| GET | `/api/overview` | dashboard overview |
| DELETE | `/api/sessions/{id}` | delete one session |
| DELETE | `/api/data` | delete everything of this client |
| WS | `/ws/sessions/{id}?client_id=...` | live updates |

## Metrics payload (`POST .../metrics`)
All fields are numbers, bounded and non-negative; **unknown fields are rejected (422)**, so text cannot be submitted.
```json
{
  "mouse_act": 12, "left_clicks": 8, "right_clicks": 0, "double_clicks": 0, "wheel": 5, "drags": 1,
  "mouse_distance": 5400, "keystrokes": 140, "chars": 118, "special_keys": 10, "direction_keys": 3,
  "error_keys": 9, "shortcut_keys": 2, "spaces": 21, "app_changes": 1, "tab_changes": 0,
  "iki_mean_ms": 210, "iki_std_ms": 180, "idle_seconds": 14
}
```
`iki_*` and `idle_seconds` are optional display-only fields; the model never uses them.
Minutes are rate-limited (`MIN_METRIC_INTERVAL_SECONDS`, default 20 s) and a session holds at most 6 hours.

## Estimate object
```json
{
  "status": "ok | insufficient_data | calibrating | model_unavailable",
  "baseline_source": "previous_sessions | this_session_provisional",
  "stress": {
    "score": 0.72, "session_score": 0.70,
    "leaning": "higher_than_usual | lower_than_usual | unclear",
    "confidence": "very_low | low | moderate | moderate_high",
    "reliable": true, "evidence": "...", "loso_block_roc_auc": 0.687, "loso_block_roc_auc_ci95": [0.56, 0.80],
    "contributions": [{"feature": "rel_error_ratio", "description": "...", "relative_value_sd": -1.8,
                       "shap": 0.05, "direction": "up", "explanation": "..."}],
    "timeline": [{"window_end_minute": 5, "score": 0.61}]
  },
  "workload": { "... same shape, reliable=false ..." },
  "disclaimer": "..."
}
```
`score` is a model output between 0 and 1, **not a calibrated probability**. `leaning` is `unclear` for 0.40-0.60.

## WebSocket protocol
Client -> server: `{"type":"ping"}` or `{"type":"metrics","data":{...metrics payload...}}`.
Server -> client: `{"type":"pong"}`, `{"type":"update","minute_index":n,"metric":{...},"estimate":{...}}` (also pushed when
metrics arrive by REST), `{"type":"stopped","session":{...}}`, `{"type":"error","detail":"..."}`.
Close codes: 4401 invalid client id, 4404 session not found / not yours.
