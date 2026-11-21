"""Request validation. Every counter is bounded so a bad client cannot poison the data."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool = Field(..., description="User explicitly agreed to behavioural monitoring")
    consent_version: str = Field(..., min_length=3, max_length=32)


class MinuteMetricIn(BaseModel):
    """One minute of aggregated counters. Extra fields are rejected (so typed text can't sneak in)."""
    model_config = ConfigDict(extra="forbid")

    mouse_act: float = Field(0, ge=0, le=20000)
    left_clicks: float = Field(0, ge=0, le=2000)
    right_clicks: float = Field(0, ge=0, le=2000)
    double_clicks: float = Field(0, ge=0, le=2000)
    wheel: float = Field(0, ge=0, le=5000)
    drags: float = Field(0, ge=0, le=20000)
    mouse_distance: float = Field(0, ge=0, le=2_000_000)
    keystrokes: float = Field(0, ge=0, le=3000)
    chars: float = Field(0, ge=0, le=3000)
    special_keys: float = Field(0, ge=0, le=3000)
    direction_keys: float = Field(0, ge=0, le=3000)
    error_keys: float = Field(0, ge=0, le=3000)
    shortcut_keys: float = Field(0, ge=0, le=3000)
    spaces: float = Field(0, ge=0, le=3000)
    app_changes: float = Field(0, ge=0, le=500)
    tab_changes: float = Field(0, ge=0, le=500)

    iki_mean_ms: Optional[float] = Field(None, ge=0, le=60000)
    iki_std_ms: Optional[float] = Field(None, ge=0, le=60000)
    idle_seconds: Optional[float] = Field(None, ge=0, le=60)


class WsMetricMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    data: MinuteMetricIn
