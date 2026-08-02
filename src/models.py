"""Data models for governance-gateway — Pydantic, no plain dataclass."""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Dict

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class InterceptRequest(BaseModel):
    path: str
    method: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    agent_id: Optional[str] = None


class InterceptResponse(BaseModel):
    verdict: Verdict
    reason: str
    decision_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    matched_rule: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float


class DecisionRecord(BaseModel):
    id: str
    verdict: str
    reason: str
    matched_rule: Optional[str]
    timestamp: str
    path: str
    method: str
    agent_id: Optional[str]
