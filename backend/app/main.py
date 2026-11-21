"""
FastAPI application.

REST    : /api/...        (see documentation/api.md)
WebSocket: /ws/sessions/{session_id}?client_id=...

Run from the PROJECT ROOT:
    uvicorn backend.app.main:app --reload --port 8000
"""

import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import analytics, settings  # noqa: E402
from backend.app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from backend.app.models import EstimateLog, MinuteMetric, MonitoringSession, utcnow  # noqa: E402
from backend.app.schemas import MinuteMetricIn, StartSessionRequest, WsMetricMessage  # noqa: E402
from backend.app.ws_manager import manager  # noqa: E402
from ml import config as ml_config  # noqa: E402
from ml.inference import ModelService  # noqa: E402

CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
model_service = None


def purge_old_data():
    """Data-retention rule: delete sessions older than DATA_RETENTION_DAYS."""
    cutoff = utcnow() - timedelta(days=settings.DATA_RETENTION_DAYS)
    db = SessionLocal()
    try:
        old = db.execute(select(MonitoringSession).where(MonitoringSession.started_at < cutoff)).scalars().all()
        for session in old:
            db.delete(session)
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app):
    global model_service
    Base.metadata.create_all(bind=engine)
    purge_old_data()
    model_service = ModelService()   # loads models/*.joblib and builds SHAP explainers
    yield


app = FastAPI(title="HCI Stress & Workload Estimation API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Client-Id"],
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def require_client_id(x_client_id: str = Header(default="")):
    if not CLIENT_ID_PATTERN.match(x_client_id):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Client-Id header")
    return x_client_id


def get_owned_session(db, session_id, client_id):
    session = db.get(MonitoringSession, session_id)
    if session is None or session.client_id != client_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def metrics_to_dataframe(metric_rows):
    records = []
    for row in metric_rows:
        record = {}
        for field in ml_config.MINUTE_FIELDS:
            record[field] = float(getattr(row, field))
        records.append(record)
    if len(records) == 0:
        return pd.DataFrame(columns=ml_config.MINUTE_FIELDS)
    return pd.DataFrame(records)[ml_config.MINUTE_FIELDS]


def iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def session_summary(session):
    minutes = len(session.metrics)
    duration = None
    if session.ended_at is not None:
        started = session.started_at if session.started_at.tzinfo else session.started_at.replace(tzinfo=timezone.utc)
        ended = session.ended_at if session.ended_at.tzinfo else session.ended_at.replace(tzinfo=timezone.utc)
        duration = (ended - started).total_seconds() / 60.0
    stress_score = None
    leaning = None
    if session.last_estimate_json and "stress" in session.last_estimate_json:
        stress_score = session.last_estimate_json["stress"]["session_score"]
        leaning = session.last_estimate_json["stress"]["leaning"]
    return {
        "id": session.id,
        "status": session.status,
        "started_at": iso(session.started_at),
        "ended_at": iso(session.ended_at),
        "minutes_recorded": minutes,
        "duration_minutes": duration,
        "stress_session_score": stress_score,
        "stress_leaning": leaning,
        "baseline_source": (session.last_estimate_json or {}).get("baseline_source"),
    }


def history_rows_for_client(db, client_id, exclude_session_id=None):
    query = select(MonitoringSession).where(
        MonitoringSession.client_id == client_id, MonitoringSession.status == "stopped")
    sessions = db.execute(query).scalars().all()
    rows = []
    for session in sessions:
        if session.id == exclude_session_id:
            continue
        rows.extend(session.metrics)
    return rows


# ---------------------------------------------------------------------------
# core: store one minute + run the real model
# ---------------------------------------------------------------------------
def process_metric_sync(session_id, client_id, metric_dict):
    db = SessionLocal()
    try:
        session = get_owned_session(db, session_id, client_id)
        if session.status != "active":
            raise HTTPException(status_code=409, detail="Session is not active")

        existing = session.metrics
        if len(existing) > 0 and settings.MIN_METRIC_INTERVAL_SECONDS > 0:
            last = existing[-1].received_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            gap = (utcnow() - last).total_seconds()
            if gap < settings.MIN_METRIC_INTERVAL_SECONDS:
                raise HTTPException(status_code=429, detail="Metrics arriving too quickly")
        if len(existing) >= 6 * 60:
            raise HTTPException(status_code=409, detail="Maximum session length (6 hours) reached")

        row = MinuteMetric(session_id=session.id, minute_index=len(existing), **metric_dict)
        db.add(row)
        db.commit()
        db.refresh(session)

        minutes_df = metrics_to_dataframe(session.metrics)
        if model_service is not None and model_service.is_ready:
            estimate = model_service.estimate(minutes_df, session.baseline_json)
        else:
            estimate = {"status": "model_unavailable",
                        "message": "No trained model found in models/. Run: python -m ml.train"}

        session.last_estimate_json = estimate
        log = EstimateLog(
            session_id=session.id, minute_index=row.minute_index, status=estimate["status"],
            baseline_source=estimate.get("baseline_source"),
            stress_score=estimate.get("stress", {}).get("score"),
            stress_leaning=estimate.get("stress", {}).get("leaning"),
            workload_score=estimate.get("workload", {}).get("score"),
            reliable=bool(estimate.get("stress", {}).get("reliable", False)),
        )
        db.add(log)
        db.commit()

        metric_out = analytics.minute_series([row])[0]
        return {"minute_index": row.minute_index, "metric": metric_out, "estimate": estimate}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": bool(model_service and model_service.is_ready)}


@app.get("/api/model/info")
def model_info():
    if model_service is None or not model_service.is_ready:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "models": model_service.model_info(),
        "window_minutes": ml_config.WINDOW_MINUTES,
        "min_baseline_windows": ml_config.MIN_BASELINE_WINDOWS,
        "model_features": ml_config.MODEL_FEATURES,
        "feature_descriptions": ml_config.FEATURE_DESCRIPTIONS,
        "consent_version": settings.CONSENT_VERSION,
        "disclaimer": "Research prototype. Estimates compare your behaviour with your own usual behaviour. "
                      "Not a medical or psychological diagnosis.",
    }


@app.post("/api/sessions/start", status_code=201)
def start_session(body: StartSessionRequest, client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(status_code=400, detail="Explicit consent is required before monitoring starts")
    if body.consent_version != settings.CONSENT_VERSION:
        raise HTTPException(status_code=400, detail="Consent text version is outdated; reload the page")

    count = len(db.execute(select(MonitoringSession.id).where(MonitoringSession.client_id == client_id)).all())
    if count >= settings.MAX_SESSIONS_PER_CLIENT:
        raise HTTPException(status_code=409, detail="Session limit reached; delete old sessions first")

    active = db.execute(select(MonitoringSession).where(
        MonitoringSession.client_id == client_id, MonitoringSession.status == "active")).scalars().all()
    for old_session in active:
        old_session.status = "stopped"
        old_session.ended_at = utcnow()

    history_sequences = []
    stopped = db.execute(select(MonitoringSession).where(
        MonitoringSession.client_id == client_id, MonitoringSession.status == "stopped")).scalars().all()
    for past in stopped:
        history_sequences.append(metrics_to_dataframe(past.metrics))
    baseline = None
    if model_service is not None and model_service.is_ready:
        baseline = model_service.baseline_from_sequences(history_sequences)

    session = MonitoringSession(client_id=client_id, consent_version=body.consent_version, baseline_json=baseline)
    db.add(session)
    db.commit()
    return {
        "session_id": session.id,
        "started_at": iso(session.started_at),
        "baseline_available": baseline is not None,
        "baseline_windows": None if baseline is None else baseline["n_windows"],
    }


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str, client_id: str = Depends(require_client_id)):
    def work():
        db = SessionLocal()
        try:
            session = get_owned_session(db, session_id, client_id)
            if session.status == "active":
                session.status = "stopped"
                session.ended_at = utcnow()
                db.commit()
                db.refresh(session)
            return session_summary(session)
        finally:
            db.close()

    summary = await run_in_threadpool(work)
    await manager.broadcast(session_id, {"type": "stopped", "session": summary})
    return summary


@app.post("/api/sessions/{session_id}/metrics")
async def post_metrics(session_id: str, body: MinuteMetricIn, client_id: str = Depends(require_client_id)):
    result = await run_in_threadpool(process_metric_sync, session_id, client_id, body.model_dump())
    await manager.broadcast(session_id, {"type": "update", **result})
    return result


@app.get("/api/sessions")
def list_sessions(client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    sessions = db.execute(select(MonitoringSession).where(MonitoringSession.client_id == client_id)
                          .order_by(MonitoringSession.started_at.desc()).limit(100)).scalars().all()
    return [session_summary(s) for s in sessions]


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    session = get_owned_session(db, session_id, client_id)
    result = session_summary(session)
    result["last_estimate"] = session.last_estimate_json
    return result


@app.get("/api/sessions/{session_id}/prediction")
def get_prediction(session_id: str, client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    session = get_owned_session(db, session_id, client_id)
    if session.last_estimate_json is None:
        return {"status": "insufficient_data", "message": "No metrics received yet."}
    return session.last_estimate_json


@app.get("/api/sessions/{session_id}/analytics")
def get_analytics(session_id: str, client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    session = get_owned_session(db, session_id, client_id)
    series = analytics.minute_series(session.metrics)
    history = analytics.history_means(history_rows_for_client(db, client_id, exclude_session_id=session.id))
    return {
        "session": session_summary(session),
        "series": series,
        "summary": analytics.summary(series),
        "variability": analytics.variability(series),
        "pattern_changes": analytics.pattern_changes(series),
        "versus_baseline": analytics.versus_baseline(series, history),
        "estimate_history": [
            {"minute": e.minute_index + 1, "stress_score": e.stress_score, "workload_score": e.workload_score,
             "leaning": e.stress_leaning}
            for e in session.estimates if e.stress_score is not None
        ],
    }


@app.get("/api/overview")
def overview(client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    sessions = db.execute(select(MonitoringSession).where(MonitoringSession.client_id == client_id)
                          .order_by(MonitoringSession.started_at.desc()).limit(30)).scalars().all()
    active = None
    trend = []
    total_minutes = 0
    for session in sessions:
        total_minutes += len(session.metrics)
        summary = session_summary(session)
        if session.status == "active" and active is None:
            active = summary
        series = analytics.minute_series(session.metrics)
        if len(series) > 0:
            overall = analytics.summary(series)
            trend.append({
                "session_id": session.id, "started_at": iso(session.started_at),
                "avg_keystrokes_per_min": overall["avg_keystrokes_per_min"],
                "avg_mouse_distance_per_min": overall["avg_mouse_distance_per_min"],
                "total_switches": overall["total_switches"],
                "stress_session_score": summary["stress_session_score"],
            })
    trend.reverse()
    return {"active_session": active, "session_count": len(sessions), "total_minutes": total_minutes,
            "trend": trend, "latest": None if len(sessions) == 0 else session_summary(sessions[0])}


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    session = get_owned_session(db, session_id, client_id)
    db.delete(session)
    db.commit()


@app.delete("/api/data", status_code=204)
def delete_all_my_data(client_id: str = Depends(require_client_id), db: Session = Depends(get_db)):
    sessions = db.execute(select(MonitoringSession).where(MonitoringSession.client_id == client_id)).scalars().all()
    for session in sessions:
        db.delete(session)
    db.commit()


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws/sessions/{session_id}")
async def session_socket(websocket: WebSocket, session_id: str, client_id: str = Query(default="")):
    if not CLIENT_ID_PATTERN.match(client_id):
        await websocket.close(code=4401)
        return

    def check_owner():
        db = SessionLocal()
        try:
            session = db.get(MonitoringSession, session_id)
            return session is not None and session.client_id == client_id
        finally:
            db.close()

    if not await run_in_threadpool(check_owner):
        await websocket.close(code=4404)
        return

    await manager.connect(session_id, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif message_type == "metrics":
                try:
                    parsed = WsMetricMessage(**message)
                    result = await run_in_threadpool(process_metric_sync, session_id, client_id, parsed.data.model_dump())
                    await manager.broadcast(session_id, {"type": "update", **result})
                except ValidationError as error:
                    await websocket.send_json({"type": "error", "detail": "Invalid metrics payload",
                                               "errors": error.errors(include_url=False, include_context=False)})
                except HTTPException as error:
                    await websocket.send_json({"type": "error", "detail": error.detail})
            else:
                await websocket.send_json({"type": "error", "detail": "Unknown message type"})
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)


# ---------------------------------------------------------------------------
# Optional: serve the built React app from the same service (single-service deploy)
# ---------------------------------------------------------------------------
if os.path.isdir(settings.FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIST, html=True), name="frontend")
