"""LaunchFlow - the orchestrator.

    @start intake ──@router──┬─ "rejected" ─┐
                             ├─ "clarify"  ─┴─ or_ ─▶ stop_early
                             └─ "approved" ─▶ run_both_crews  (asyncio.gather + akickoff: Crew A ‖ Crew B)
                                                 ├─▶ score_research ─┐
                                                 └─▶ scan_creative  ─┴ and_ ─▶ assemble_brief (Crew C)
                                                                                    ▶ @router quality_gate
                                                                       "ship" ─┐
                                                                       "flag" ─┴ or_ ─▶ finalize

Flow-level features shown: Pydantic state, @router (flow-level guardrail + quality gate), or_/and_ conditions,
async listener, state handoff between steps, optional @persist, flow.plot().
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Literal

from crewai.flow.flow import Flow, and_, listen, or_, router, start
from crewai.flow.persistence import persist

from launchpad.config import OUTPUT_DIR, env_bool
from launchpad.crews.creative_crew import build_creative_crew
from launchpad.crews.final_crew import build_final_crew
from launchpad.crews.market_crew import build_market_crew
from launchpad.events import HUB, emit
from launchpad.guardrails import intake_decision
from launchpad.hooks import reset_tool_budget
from launchpad.intake import extract_brief_info
from launchpad.models import LaunchBrief, LaunchState
from launchpad.tools import scan_claims


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "launch"


def _briefing_markdown(b: LaunchBrief, status: str) -> str:
    lines = [
        f"# Launch Brief - {b.product_name}",
        f"*Status: {'ready to ship' if status == 'shipped' else 'flagged for human review'}*",
        "", "## Executive summary", b.executive_summary,
        "", "## Positioning", b.positioning_statement,
        "", "## Target audience", *[f"- {a}" for a in b.target_audience],
        "", "## Key messages", *[f"{i}. {m}" for i, m in enumerate(b.key_messages, 1)],
        "", "## Taglines", *[f"- {t}" for t in b.taglines],
        "", "## Channel plan", "| Channel | Tactic | KPI |", "|---|---|---|",
        *[f"| {c.channel} | {c.tactic} | {c.kpi} |" for c in b.channel_plan],
        "", "## Pricing", b.pricing_recommendation,
        "", "## Risks", *([f"- {r}" for r in b.risks] or ["- None identified"]),
        "", "## Call to action", b.call_to_action, "",
    ]
    return "\n".join(lines)


# Optional: LAUNCHPAD_PERSIST=1 stores the flow state in SQLite after every step (resume / audit trail).
_maybe_persist = persist() if env_bool("LAUNCHPAD_PERSIST") else (lambda cls: cls)


@_maybe_persist
class LaunchFlow(Flow[LaunchState]):
    # ------------------------------------------------------------------ 1. intake (flow guardrail)
    @start()
    def intake(self):
        HUB.reset() if not HUB.snapshot() else None
        reset_tool_budget()
        emit("stage", stage="intake", title="Intake check", body="Reading the brief and checking it against launch policy.")
        info = extract_brief_info(self.state.brief)
        self.state.product_name = info.product_name or "the product"
        self.state.category = info.category
        self.state.audience = info.audience or "general consumers"
        route, message = intake_decision(self.state.brief, info)
        self.state.status = route  # type: ignore[assignment]
        self.state.message = message
        emit("guardrail", name="flow: intake router", verdict={"approved": "pass", "clarify": "clarify", "rejected": "reject"}[route], detail=message)
        emit("handoff", type="flow-state", src="Intake", dst="Router", note="validated brief + extracted fields stored in Pydantic state")
        return route

    @router(intake)
    def intake_gate(self) -> Literal["approved", "clarify", "rejected"]:
        # literal return values let flow.plot() draw every branch
        if self.state.status == "rejected":
            return "rejected"
        if self.state.status == "clarify":
            return "clarify"
        return "approved"

    # ------------------------------------------------------------------ 2a. early exits
    @listen(or_("rejected", "clarify"))
    def stop_early(self):
        emit("stage", stage="stopped", title="Stopped before spending any tokens on crews", body=self.state.message)
        return self.state.status

    # ------------------------------------------------------------------ 2b. both crews, truly parallel
    @listen("approved")
    async def run_both_crews(self):
        emit("stage", stage="crews", title="Launching Crew A and Crew B in parallel",
             body="asyncio.gather(crew_a.akickoff(...), crew_b.akickoff(...)) - two independent crews at the same time.")
        inputs = {
            "brief": self.state.brief,
            "product_name": self.state.product_name,
            "category": self.state.category or "consumer product",
            "audience": self.state.audience,
        }
        crew_a, crew_b = build_market_crew(), build_creative_crew()

        async def guarded(label: str, coro):
            try:
                return True, await coro
            except Exception as exc:  # e.g. a guardrail that ran out of retries
                msg = f"{label} failed: {type(exc).__name__}: {str(exc)[:300]}"
                self.state.errors.append(msg)
                emit("error", body=msg)
                return False, None

        (ok_a, out_a), (ok_b, out_b) = await asyncio.gather(
            guarded("Crew A (market intelligence)", crew_a.akickoff(inputs=inputs)),
            guarded("Crew B (creative & compliance)", crew_b.akickoff(inputs=inputs)),
        )
        if ok_a and out_a is not None:
            self.state.market_report = out_a.raw
            report = next((t.output.pydantic for t in crew_a.tasks if t.name == "competitor_scan" and t.output), None)
            self.state.competitor_threat = getattr(report, "threat_level", "") or ""
        if ok_b and out_b is not None:
            self.state.creative_package = out_b.raw
        emit("handoff", type="flow-state", src="Crew A + Crew B", dst="Flow state", note="both crew outputs stored on the shared Pydantic state")
        return ok_a or ok_b

    # ------------------------------------------------------------------ 3. two cheap deterministic checks, run concurrently
    @listen(run_both_crews)
    def score_research(self):
        text = self.state.market_report
        self.state.research_score = {
            "words": len(text.split()),
            "sources": len(re.findall(r"https?://|(?i:source:)", text)),
            "competitor_threat": self.state.competitor_threat or "unknown",
        }
        emit("stage", stage="precheck", title="Pre-check: research coverage", body=json.dumps(self.state.research_score))

    @listen(run_both_crews)
    def scan_creative(self):
        flags = scan_claims(self.state.creative_package)
        self.state.creative_scan = {"flags": flags, "count": len(flags)}
        emit("stage", stage="precheck", title="Pre-check: claim scan of the creative package", body=f"{len(flags)} risky phrase(s) found")

    # ------------------------------------------------------------------ 4. final merge (needs BOTH pre-checks -> and_)
    @listen(and_(score_research, scan_creative))
    def assemble_brief(self):
        if not self.state.market_report and not self.state.creative_package:
            self.state.status = "failed"
            self.state.message = "Both crews failed, so there is nothing to assemble."
            return "failed"
        emit("stage", stage="final", title="Launch Editor assembling the final brief",
             body="Crew C receives the flow state (Crew A + Crew B outputs + pre-check flags) and runs chained guardrails.")
        flags = []
        if self.state.creative_scan.get("count"):
            flags.append("Claim scanner flagged: " + "; ".join(f["claim"] for f in self.state.creative_scan["flags"]))
        if not self.state.market_report:
            flags.append("Market intelligence is UNAVAILABLE - say so and avoid market numbers.")
        if not self.state.creative_package:
            flags.append("Creative package is UNAVAILABLE - draft copy yourself, conservatively, and mark needs_review.")
        try:
            out = build_final_crew().kickoff(inputs={
                "product_name": self.state.product_name,
                "market_report": self.state.market_report or "(unavailable)",
                "creative_package": self.state.creative_package or "(unavailable)",
                "flags": "\n".join(flags) or "No automated flags.",
            })
            brief = out.pydantic or LaunchBrief.model_validate_json(re.search(r"\{.*\}", out.raw, flags=re.DOTALL).group(0))
            self.state.launch_brief = brief.model_dump()
        except Exception as exc:
            msg = f"Launch Editor failed: {type(exc).__name__}: {str(exc)[:300]}"
            self.state.errors.append(msg)
            self.state.status = "failed"
            self.state.message = msg
            emit("error", body=msg)
            return "failed"
        return "assembled"

    # ------------------------------------------------------------------ 5. quality gate (router)
    @router(assemble_brief)
    def quality_gate(self, assembled: str) -> Literal["ship", "flag"]:
        if assembled != "assembled":
            return "flag"
        needs_review = (
            self.state.launch_brief.get("compliance_status") == "needs_review"
            or self.state.creative_scan.get("count", 0) > 0
            or bool(self.state.errors)
        )
        emit("guardrail", name="flow: quality gate", verdict="flag" if needs_review else "pass",
             detail="routed to human review" if needs_review else "clean - ready to ship")
        if needs_review:
            return "flag"
        return "ship"

    @listen(or_("ship", "flag"))
    def finalize(self):
        if self.state.status == "failed":
            emit("stage", stage="failed", title="Run failed", body=self.state.message)
            return "failed"
        flagged = bool(self.state.launch_brief) and (
            self.state.launch_brief.get("compliance_status") == "needs_review"
            or self.state.creative_scan.get("count", 0) > 0 or bool(self.state.errors)
        )
        self.state.status = "flagged" if flagged else "shipped"
        brief = LaunchBrief(**self.state.launch_brief)
        self.state.launch_brief_markdown = _briefing_markdown(brief, self.state.status)
        OUTPUT_DIR.mkdir(exist_ok=True)
        base = OUTPUT_DIR / f"{_slug(brief.product_name)}-{int(time.time())}"
        Path(f"{base}.md").write_text(self.state.launch_brief_markdown, encoding="utf-8")
        Path(f"{base}.json").write_text(json.dumps(self.state.launch_brief, indent=2), encoding="utf-8")
        self.state.saved_to = f"{base}.md"
        emit("stage", stage="done", title="Launch brief ready" if not flagged else "Launch brief ready - flagged for review",
             body=f"Saved to {self.state.saved_to}")
        return self.state.status


def run_flow(brief: str) -> LaunchFlow:
    """Convenience wrapper used by the CLI and the Streamlit app (blocking)."""
    flow = LaunchFlow(suppress_flow_events=True)
    flow.kickoff(inputs={"brief": brief})
    return flow
