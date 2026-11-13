"""Pydantic schemas: structured task outputs, intake info and the flow state."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---- Structured task outputs -------------------------------------------------
class Competitor(BaseModel):
    name: str
    positioning: str = Field(description="How they position themselves in one sentence")
    price_usd: Optional[float] = Field(default=None, description="Typical retail price in USD")
    strength: str = Field(description="Their single biggest advantage")


class CompetitorReport(BaseModel):
    competitors: list[Competitor] = Field(min_length=2)
    threat_level: Literal["low", "medium", "high"] = Field(
        description="How hard it will be to win share against the strongest competitor"
    )
    strongest_competitor: str
    summary: str


class ChannelItem(BaseModel):
    channel: str
    tactic: str
    kpi: str


class LaunchBrief(BaseModel):
    product_name: str
    executive_summary: str
    positioning_statement: str
    target_audience: list[str] = Field(min_length=1)
    key_messages: list[str] = Field(min_length=3)
    taglines: list[str] = Field(min_length=3)
    channel_plan: list[ChannelItem] = Field(min_length=3)
    pricing_recommendation: str
    risks: list[str] = Field(default_factory=list)
    compliance_status: Literal["clear", "needs_review"]
    call_to_action: str


# ---- Intake ------------------------------------------------------------------
class BriefInfo(BaseModel):
    product_name: str = ""
    category: str = ""
    audience: str = ""
    missing: list[str] = Field(default_factory=list)


# ---- Flow state --------------------------------------------------------------
class LaunchState(BaseModel):
    id: str = ""  # populated by Flow (uuid); required by @persist
    brief: str = ""
    product_name: str = ""
    category: str = ""
    audience: str = ""

    status: Literal["new", "rejected", "clarify", "approved", "shipped", "flagged", "failed"] = "new"
    message: str = ""  # human-readable explanation for rejected / clarify / failed

    market_report: str = ""
    competitor_threat: str = ""
    creative_package: str = ""
    research_score: dict[str, Any] = Field(default_factory=dict)
    creative_scan: dict[str, Any] = Field(default_factory=dict)

    launch_brief: dict[str, Any] = Field(default_factory=dict)
    launch_brief_markdown: str = ""
    saved_to: str = ""
    errors: list[str] = Field(default_factory=list)
