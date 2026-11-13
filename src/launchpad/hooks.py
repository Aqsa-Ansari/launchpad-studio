"""TOOL-LEVEL guardrails: CrewAI tool-call hooks.

Hooks are global (registered at import) and run on *every* tool call of *every* crew:
  * block_sensitive_queries - refuse searches that hunt for personal / secret data
  * enforce_search_budget   - cap the number of web searches per run (cost + loop guard)
  * enforce_domain_allowlist- for tools that take a URL, only allow approved domains
  * redact_pii_in_results   - after-hook: scrub e-mails / phone numbers from tool output
Returning ``False`` from a before-hook blocks the call; the agent just sees
"Tool execution blocked by hook" and carries on (the run does not crash).
"""
from __future__ import annotations

import os
import re
import threading
from urllib.parse import urlparse

from crewai.hooks import ToolCallHookContext, after_tool_call, before_tool_call

from launchpad.events import emit
from launchpad.tools import SEARCH_TOOL_NAMES

SENSITIVE = re.compile(
    r"(password|passwd|social security|\bssn\b|credit card|card number|home address|private key|api[_ -]?key|leaked|doxx?)",
    re.IGNORECASE,
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\b(?:\+?\d{1,2}[ -.])?(?:\(?\d{3}\)?[ -.])\d{3}[ -.]\d{4}\b")

_lock = threading.Lock()
_search_calls = 0


def reset_tool_budget() -> None:
    global _search_calls
    with _lock:
        _search_calls = 0


def _is_search(name: str) -> bool:
    return name.lower() in SEARCH_TOOL_NAMES or "search" in name.lower()


def _query(ctx: ToolCallHookContext) -> str:
    args = ctx.tool_input or {}
    return str(args.get("search_query") or args.get("query") or "")


@before_tool_call
def block_sensitive_queries(ctx: ToolCallHookContext) -> bool | None:
    if not _is_search(ctx.tool_name):
        return None
    q = _query(ctx)
    if SENSITIVE.search(q):
        emit("tool_blocked", tool=ctx.tool_name, agent=getattr(ctx.agent, "role", ""), reason="sensitive terms in query", detail=q[:140])
        return False
    return None


@before_tool_call
def enforce_search_budget(ctx: ToolCallHookContext) -> bool | None:
    global _search_calls
    if not _is_search(ctx.tool_name):
        return None
    limit = int(os.getenv("LAUNCHPAD_MAX_SEARCHES", "24"))
    with _lock:
        _search_calls += 1
        used = _search_calls
    if used > limit:
        emit("tool_blocked", tool=ctx.tool_name, agent=getattr(ctx.agent, "role", ""), reason=f"search budget of {limit} exhausted", detail=_query(ctx)[:140])
        return False
    return None


@before_tool_call
def enforce_domain_allowlist(ctx: ToolCallHookContext) -> bool | None:
    allowed = [d.strip().lower() for d in os.getenv("LAUNCHPAD_ALLOWED_DOMAINS", "").split(",") if d.strip()]
    if not allowed:
        return None
    url = (ctx.tool_input or {}).get("url") or (ctx.tool_input or {}).get("website_url")
    if not url:
        return None
    host = (urlparse(str(url)).hostname or "").lower()
    if not any(host == d or host.endswith("." + d) for d in allowed):
        emit("tool_blocked", tool=ctx.tool_name, agent=getattr(ctx.agent, "role", ""), reason="domain not on allow-list", detail=host)
        return False
    return None


@after_tool_call
def redact_pii_in_results(ctx: ToolCallHookContext) -> str | None:
    result = ctx.tool_result
    if not result or not isinstance(result, str):
        return None
    cleaned = PHONE.sub("[phone removed]", EMAIL.sub("[email removed]", result))
    if cleaned != result:
        emit("guardrail", name="tool: PII redaction", verdict="redacted", detail=f"scrubbed personal data from {ctx.tool_name} output")
        return cleaned
    return None
