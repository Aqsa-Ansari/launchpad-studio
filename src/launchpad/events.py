"""Observability: a thread-safe event hub + a CrewAI event-bus listener.

The Streamlit UI (and the CLI) read from ``HUB``. Everything that happens in a run -
flow stages, task start/finish, tool calls, guardrail verdicts, handoffs - is pushed here,
which is also what proves that tasks and crews really run in parallel (see timestamps).

Note: HUB is a process-wide singleton, so it is designed for ONE active run at a time.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from crewai.events import (
    BaseEventListener,
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)


class EventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._t0 = time.time()

    def reset(self) -> None:
        with self._lock:
            self._events = []
            self._t0 = time.time()

    def emit(self, kind: str, **data: Any) -> dict[str, Any]:
        with self._lock:
            ev = {"seq": len(self._events), "t": round(time.time() - self._t0, 2), "kind": kind, **data}
            self._events.append(ev)
        return ev

    def snapshot(self, since: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events[since:])


HUB = EventHub()


def emit(kind: str, **data: Any) -> None:
    HUB.emit(kind, **data)


# --------------------------------------------------------------------------------------
# Static knowledge about our tasks: which crew they belong to and who they hand off to.
# Task names are set on every Task(...) in launchpad/crews/*.py
# --------------------------------------------------------------------------------------
TASK_META: dict[str, dict[str, Any]] = {
    "market_scan": {"crew": "market", "label": "Market scan", "feeds": ["research_synthesis"]},
    "voice_scan": {"crew": "market", "label": "Customer voice scan", "feeds": ["research_synthesis"]},
    "competitor_scan": {
        "crew": "market",
        "label": "Competitor scan",
        "feeds": ["competitor_deep_dive", "research_synthesis"],
    },
    "competitor_deep_dive": {"crew": "market", "label": "Competitor deep-dive (conditional)", "feeds": ["research_synthesis"]},
    "research_synthesis": {"crew": "market", "label": "Research synthesis", "feeds": []},
    "positioning": {"crew": "creative", "label": "Brand positioning", "feeds": ["copy_draft", "creative_package"]},
    "copy_draft": {"crew": "creative", "label": "Copy draft", "feeds": ["compliance_review", "creative_package"]},
    "compliance_review": {"crew": "creative", "label": "Compliance review", "feeds": ["creative_package"]},
    "creative_package": {"crew": "creative", "label": "Creative package", "feeds": []},
    "launch_brief": {"crew": "final", "label": "Launch brief", "feeds": []},
}

DELEGATION_TOOLS = {"delegate work to coworker", "ask question to coworker"}
MANAGER_ROLES = {"launch director"}


def _agent_role(event: Any) -> str:
    return str(getattr(event, "agent_role", None) or getattr(getattr(event, "agent", None), "role", "") or "")


def _short(text: Any, n: int = 4000) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[:n] + " …"


class StudioListener(BaseEventListener):
    """Translates CrewAI bus events into HUB events. Must stay alive (module-level instance)."""

    def setup_listeners(self, crewai_event_bus):  # noqa: D401 - CrewAI hook name
        @crewai_event_bus.on(TaskStartedEvent)
        def on_task_started(source, event):
            try:
                name = getattr(event, "task_name", None) or ""
                meta = TASK_META.get(name, {})
                HUB.emit(
                    "task_start",
                    task=name,
                    crew=meta.get("crew", "?"),
                    label=meta.get("label", name),
                    agent=_agent_role(event),
                )
            except Exception:  # never let telemetry break a run
                pass

        @crewai_event_bus.on(TaskCompletedEvent)
        def on_task_completed(source, event):
            try:
                name = getattr(event, "task_name", None) or ""
                meta = TASK_META.get(name, {})
                out = getattr(event, "output", None)
                HUB.emit(
                    "task_done",
                    task=name,
                    crew=meta.get("crew", "?"),
                    label=meta.get("label", name),
                    agent=_agent_role(event),
                    body=_short(getattr(out, "raw", out)),
                )
                for target in meta.get("feeds", []):
                    HUB.emit(
                        "handoff",
                        type="task-context",
                        src=meta.get("label", name),
                        dst=TASK_META.get(target, {}).get("label", target),
                        note="output passed through Task(context=[...])",
                    )
            except Exception:
                pass

        @crewai_event_bus.on(TaskFailedEvent)
        def on_task_failed(source, event):
            try:
                name = getattr(event, "task_name", None) or ""
                HUB.emit("task_fail", task=name, label=TASK_META.get(name, {}).get("label", name), body=_short(getattr(event, "error", ""), 600))
            except Exception:
                pass

        @crewai_event_bus.on(ToolUsageStartedEvent)
        def on_tool_started(source, event):
            try:
                tool = str(getattr(event, "tool_name", ""))
                role = _agent_role(event)
                args = getattr(event, "tool_args", None)
                if tool.lower() in DELEGATION_TOOLS:
                    manager = role.lower() in MANAGER_ROLES
                    coworker = ""
                    if isinstance(args, dict):
                        coworker = str(args.get("coworker", ""))
                    HUB.emit(
                        "handoff",
                        type="hierarchical" if manager else "delegation",
                        src=role,
                        dst=coworker or "a teammate",
                        note=("manager assigned work to a specialist" if manager else "agent used allow_delegation=True"),
                    )
                else:
                    HUB.emit("tool", tool=tool, agent=role, args=_short(args, 240))
            except Exception:
                pass

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def on_tool_finished(source, event):  # kept lightweight; the start event already tells the story
            return None


# Instantiate once so handlers stay registered (CrewAI docs: listener must not be garbage-collected).
LISTENER = StudioListener()
