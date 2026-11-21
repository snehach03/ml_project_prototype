"""
Database tables. NOTE what is NOT stored: typed text, key identities, page
content, URLs or window titles. Only per-minute counters.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return uuid.uuid4().hex


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | stopped
    consent_version: Mapped[str] = mapped_column(String(32))
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_estimate_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    metrics = relationship("MinuteMetric", cascade="all, delete-orphan", order_by="MinuteMetric.minute_index")
    estimates = relationship("EstimateLog", cascade="all, delete-orphan", order_by="EstimateLog.minute_index")


class MinuteMetric(Base):
    __tablename__ = "minute_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), index=True)
    minute_index: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # model features (same names as ml.config.MINUTE_FIELDS)
    mouse_act: Mapped[float] = mapped_column(Float, default=0)
    left_clicks: Mapped[float] = mapped_column(Float, default=0)
    right_clicks: Mapped[float] = mapped_column(Float, default=0)
    double_clicks: Mapped[float] = mapped_column(Float, default=0)
    wheel: Mapped[float] = mapped_column(Float, default=0)
    drags: Mapped[float] = mapped_column(Float, default=0)
    mouse_distance: Mapped[float] = mapped_column(Float, default=0)
    keystrokes: Mapped[float] = mapped_column(Float, default=0)
    chars: Mapped[float] = mapped_column(Float, default=0)
    special_keys: Mapped[float] = mapped_column(Float, default=0)
    direction_keys: Mapped[float] = mapped_column(Float, default=0)
    error_keys: Mapped[float] = mapped_column(Float, default=0)
    shortcut_keys: Mapped[float] = mapped_column(Float, default=0)
    spaces: Mapped[float] = mapped_column(Float, default=0)
    app_changes: Mapped[float] = mapped_column(Float, default=0)
    tab_changes: Mapped[float] = mapped_column(Float, default=0)

    # display-only (never fed to the model)
    iki_mean_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    iki_std_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    idle_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class EstimateLog(Base):
    __tablename__ = "estimate_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), index=True)
    minute_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    baseline_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stress_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_leaning: Mapped[str | None] = mapped_column(String(24), nullable=True)
    workload_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reliable: Mapped[bool] = mapped_column(Boolean, default=False)
