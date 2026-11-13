"""TASK-LEVEL and FLOW-LEVEL guardrails.

Task guardrails receive a ``TaskOutput`` and return ``(bool, Any)``:
    (True, value)  -> accepted; ``value`` becomes the task output (return the TaskOutput to keep it as-is)
    (False, "why") -> the agent is told what to fix and retries (up to guardrail_max_retries)
If retries are exhausted CrewAI raises - the flow catches that and degrades gracefully.

Kinds shown in this project
  1. Custom python functions ........ cite_sources_and_length, no_banned_claims, launch_brief_schema_check
  2. Built-in HallucinationGuardrail  (wired in market_crew.py; a no-op in open-source CrewAI)
  3. Working LLM-as-judge ............ make_grounding_guardrail (real hallucination check)
  4. Natural-language strings ........ see STRING_RULES, used in market_crew.py / final_crew.py
  5. Chained guardrails=[...] ........ final_crew.py
  6. Flow-level intake gate .......... intake_decision (used by the @router in flow.py)
  7. Tool-level hooks ................ launchpad/hooks.py
"""

import json
import re
from typing import Any, Callable, Tuple

from crewai import TaskOutput

from launchpad.config import is_mock, make_llm
from launchpad.events import emit
from launchpad.models import BriefInfo, LaunchBrief
from launchpad.tools import scan_claims

URL_RE = re.compile(r"https?://\S+")


def _verdict(name: str, ok: bool, detail: str) -> None:
    emit("guardrail", name=name, verdict="pass" if ok else "retry", detail=detail)


# --------------------------------------------------------------------------------------
# 1. Custom python-function guardrails
# --------------------------------------------------------------------------------------
def cite_sources_and_length(result: TaskOutput) -> Tuple[bool, Any]:
    """Market researcher: 60-400 words and at least two cited URLs / 'Source:' markers."""
    words = len(result.raw.split())
    sources = len(URL_RE.findall(result.raw)) + len(re.findall(r"(?i)\bsource:", result.raw))
    if words < 60 or words > 400:
        msg = f"Output is {words} words; it must be between 60 and 400."
        _verdict("function: sources + length", False, msg)
        return False, msg
    if sources < 2:
        msg = "Cite at least two sources (full URLs or 'Source: ...' lines) for the figures you quote."
        _verdict("function: sources + length", False, msg)
        return False, msg
    _verdict("function: sources + length", True, f"{words} words, {sources} sources")
    return True, result


_BANNED = [
    r"\bguarantee[sd]?\b", r"\b100\s?%\s*(safe|effective)\b", r"\brisk[- ]free\b",
    r"\bcures?\b", r"\bmiracle\b", r"\bclinically proven\b", r"\bbest in the world\b",
]


def no_banned_claims(result: TaskOutput) -> Tuple[bool, Any]:
    """Copy / brief must not contain claims our compliance policy forbids."""
    text = result.raw
    hits = [m.group(0) for p in _BANNED for m in re.finditer(p, text, flags=re.IGNORECASE)]
    if hits:
        msg = f"Remove these banned claims and rephrase without them: {sorted(set(h.lower() for h in hits))}."
        _verdict("function: banned claims", False, msg)
        return False, msg
    _verdict("function: banned claims", True, "no banned claims")
    return True, result


def creative_package_has_sections(result: TaskOutput) -> Tuple[bool, Any]:
    text = result.raw.lower()
    missing = [s for s in ("positioning", "tagline", "compliance") if s not in text]
    if missing:
        msg = f"The creative package must contain sections covering: {missing}."
        _verdict("function: package sections", False, msg)
        return False, msg
    _verdict("function: package sections", True, "all sections present")
    return True, result


def launch_brief_schema_check(result: TaskOutput) -> Tuple[bool, Any]:
    """Second link in the chain: validate the *structured* output, not just text."""
    brief = result.pydantic
    cleaned_json = None
    if brief is None:  # the model may have wrapped the JSON in prose or code fences; try to recover it
        try:
            match = re.search(r"\{.*\}", result.raw, flags=re.DOTALL)
            brief = LaunchBrief.model_validate_json(match.group(0)) if match else None
            cleaned_json = match.group(0) if brief else None
        except Exception:
            brief = None
    if brief is None:
        msg = "Return the launch brief as valid JSON that matches the LaunchBrief schema."
        _verdict("function: schema check", False, msg)
        return False, msg
    problems = []
    if len(set(t.lower() for t in brief.taglines)) < len(brief.taglines):
        problems.append("taglines must be unique")
    if any(len(t.split()) > 12 for t in brief.taglines):
        problems.append("each tagline must be 12 words or fewer")
    if len(brief.executive_summary.split()) > 140:
        problems.append("executive_summary must be 140 words or fewer")
    if problems:
        msg = "Fix: " + "; ".join(problems) + "."
        _verdict("function: schema check", False, msg)
        return False, msg
    _verdict("function: schema check", True, "schema + business rules ok")
    return True, (cleaned_json if cleaned_json else result)


# --------------------------------------------------------------------------------------
# 3. Working LLM-as-judge grounding guardrail (the real hallucination check)
# --------------------------------------------------------------------------------------
JUDGE_PROMPT = """You are a strict fact-checking judge.
REFERENCE MATERIAL (the only allowed source of facts):
---
{context}
---
CANDIDATE TEXT:
---
{candidate}
---
List every specific number, statistic, named company or factual claim in the candidate text that is NOT supported
by the reference material. Then score faithfulness from 0 (mostly invented) to 10 (fully grounded).
Respond with JSON only: {{"score": <number>, "unsupported": ["..."]}}"""


def make_grounding_guardrail(get_context: Callable[[], str], threshold: float = 7.0):
    """Factory: returns a guardrail judging output against ``get_context()`` at call time."""

    def grounded_in_research(result: TaskOutput) -> Tuple[bool, Any]:
        if is_mock():
            _verdict("llm-judge: grounding", True, "skipped in mock mode")
            return True, result
        context = get_context()
        if not context.strip():
            _verdict("llm-judge: grounding", True, "no reference context available - skipped")
            return True, result
        try:
            raw = make_llm("judge").call(JUDGE_PROMPT.format(context=context[:12000], candidate=result.raw[:6000]))
            match = re.search(r"\{.*\}", str(raw), flags=re.DOTALL)
            data = json.loads(match.group(0)) if match else {}
            score = float(data.get("score", 10))
            unsupported = data.get("unsupported", [])
        except Exception as exc:  # fail OPEN: a flaky judge must not kill the run
            _verdict("llm-judge: grounding", True, f"judge unavailable ({type(exc).__name__}) - skipped")
            return True, result
        if score < threshold:
            msg = (
                f"Faithfulness score {score}/10 (< {threshold}). Remove or soften claims not supported by the research: "
                f"{unsupported[:6]}"
            )
            _verdict("llm-judge: grounding", False, msg)
            return False, msg
        _verdict("llm-judge: grounding", True, f"faithfulness {score}/10")
        return True, result

    return grounded_in_research


# --------------------------------------------------------------------------------------
# 4. Natural-language guardrails (CrewAI turns these into LLM guardrails using the agent's LLM)
# --------------------------------------------------------------------------------------
STRING_RULES = {
    "voice_no_pii": (
        "The analysis must not contain personally identifiable information (no names, e-mail addresses or phone numbers "
        "of individual reviewers) and must use a neutral, professional tone."
    ),
    "brief_tone_and_cta": (
        "The executive summary must be written in a confident but professional tone, and the call_to_action must be a single, "
        "specific action with a reason to act now."
    ),
}


# --------------------------------------------------------------------------------------
# 6. Flow-level guardrail: validate the *input* before any crew is spent on it
# --------------------------------------------------------------------------------------
BANNED_CATEGORIES = {
    "weapons": r"\b(gun|firearm|ammunition|explosive|silencer)s?\b",
    "illegal drugs": r"\b(cocaine|heroin|meth(amphetamine)?|fentanyl)\b",
    "adult content": r"\b(porn\w*|escort service)\b",
    "gambling": r"\b(online casino|sports betting)\b",
    "miracle health claims": r"\b(cures? cancer|miracle cure)\b",
}


def intake_decision(brief: str, info: BriefInfo) -> tuple[str, str]:
    """Return (route, message). route in {'approved', 'clarify', 'rejected'}."""
    for name, pattern in BANNED_CATEGORIES.items():
        if re.search(pattern, brief, flags=re.IGNORECASE):
            return "rejected", f"This brief falls into a category we do not launch ({name}). Please try a different product."
    words = len(brief.split())
    missing = list(info.missing)
    if words < 8 and "details" not in missing:
        missing.append("details")
    if not info.category and "category" not in missing:
        missing.append("category")
    if missing:
        asks = {
            "audience": "who the product is for",
            "category": "what kind of product it is",
            "details": "a bit more detail about what it does",
            "product_name": "the product name (or a working title)",
        }
        wanted = ", ".join(asks.get(m, m) for m in missing)
        return "clarify", f"I need a little more to work with. Could you tell me {wanted}?"
    return "approved", "Brief accepted."
