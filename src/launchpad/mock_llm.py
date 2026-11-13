"""ScriptedLLM - a fake LLM so the whole pipeline can run offline, free and deterministic.

It is NOT part of the CrewAI story; it only exists so you can (a) try the UI without spending money and
(b) prove the plumbing - parallel tasks, hierarchical delegation, guardrail retries, flow routing - works.
It deliberately fails some guardrails on the first attempt so you can watch the retry loop.
"""
from __future__ import annotations

import json
import re
import threading
from typing import Any

from crewai.llms.base_llm import BaseLLM

from launchpad.models import CompetitorReport, LaunchBrief

_MARKET_BAD = (
    "The category is growing at roughly 6.8% a year and is worth about $10.5B globally, driven by outdoor lifestyles "
    "and premium connected products."
)
_MARKET_GOOD = (
    "- Market size: roughly $10.5B globally, growing about 6.8% a year (Source: LaunchPad internal estimates table).\n"
    "- Demand driver 1: outdoor and wellness lifestyles push shoppers to trade up to premium variants "
    "(Source: https://example.com/reports/category-outlook-2026).\n"
    "- Demand driver 2: direct-to-consumer sales make it easier for new brands to reach niche audiences "
    "(Source: https://example.com/insights/consumer-spending).\n"
    "- Price sensitivity rises above the $50-$80 band, so the premium tier must justify itself with a clear benefit, "
    "durable build quality and an honest warranty story that buyers can trust."
)
_VOICE = (
    "Praised: build quality, convenience and design. Complaints: unclear durability and battery claims, vague warranty, "
    "high price. Unmet needs: proof of real-world durability and honest, specific marketing language. "
    "Patterns come from many reviews; no individual reviewers are identified."
)
_COMPETITORS = CompetitorReport.model_validate({
    "competitors": [
        {"name": "AlpineGear", "positioning": "Trusted, rugged and widely available", "price_usd": 45, "strength": "Retail distribution"},
        {"name": "TrailSip", "positioning": "Design-led challenger brand", "price_usd": 68, "strength": "Brand story and community"},
        {"name": "HydroNova", "positioning": "Smart-tech premium", "price_usd": 119, "strength": "App ecosystem"},
    ],
    "threat_level": "high",
    "strongest_competitor": "AlpineGear",
    "summary": "AlpineGear dominates shelves; challengers win on story and design, so a newcomer needs a sharp, proven benefit.",
}).model_dump_json()
_DEEP_DIVE = (
    "AlpineGear's weakness is innovation pace: its range barely changed in three years and its warranty terms are vague. "
    "A newcomer can win by pairing a clear durability guarantee-style policy (worded carefully) with a visible, measurable "
    "benefit the incumbent lacks, priced just above AlpineGear's core tier."
)
_SYNTH = (
    "Market: roughly $10.5B and growing about 6.8% a year, led by premium and direct-to-consumer demand (Source: "
    "https://example.com/reports/category-outlook-2026). Customers: they praise build quality and convenience but distrust "
    "vague durability and eco claims. Competition: AlpineGear leads on distribution; TrailSip and HydroNova compete on story "
    "and technology; threat level is high. Implications: 1) lead with one proven, specific benefit; 2) price in the $65-$79 core "
    "band with a transparent warranty; 3) build trust through community and honest, verifiable claims."
)
_POSITIONING = (
    "Positioning: For active people who want gear that keeps up, this product is the smart outdoor companion that turns a "
    "daily essential into a reliable ritual, unlike generic basics. Key messages: 1) Built for real trails. 2) One clear benefit "
    "you can measure. 3) Honest claims, backed by testing. Target audience: hikers and outdoor commuters."
)
_COPY_BAD = (
    "Taglines: 1) Go further, stay ready. 2) Hydration, guaranteed. 3) Built for the long way round. 4) Your trail, powered. "
    "5) Carry less worry. Blurb: Meet the companion that keeps pace with every climb. Call to action: Order today and join "
    "the first 1,000 trailblazers."
)
_COPY_GOOD = _COPY_BAD.replace("Hydration, guaranteed.", "Hydration that keeps pace.")
_REVIEW = (
    "Flagged: 'guaranteed' - outcome promise needing substantiation; rewrite as 'Hydration that keeps pace.' "
    "Eco claims: none found. Verdict: CLEAR once the rewrite is applied."
)
_PACKAGE = (
    "# Creative Package\n## Positioning\n" + _POSITIONING + "\n## Key Messages\n1. Built for real trails.\n2. One measurable benefit.\n"
    "3. Honest, tested claims.\n## Taglines\n1. Go further, stay ready.\n2. Hydration that keeps pace.\n3. Built for the long way round.\n"
    "## Blurb\nMeet the companion that keeps pace with every climb.\n## Call to Action\nOrder this week and join the first 1,000 trailblazers.\n"
    "## Compliance Notes\nReviewer verdict: CLEAR after rewriting one outcome promise."
)
_PACKAGE_BAD = _PACKAGE.replace("Hydration that keeps pace.", "Hydration, guaranteed.", 1)
_BRIEF = LaunchBrief.model_validate({
    "product_name": "the product",
    "executive_summary": "A premium, honestly-marketed outdoor product entering a growing, competitive category. Win by leading with one "
                         "measurable benefit, pricing in the core band and building trust through transparent claims.",
    "positioning_statement": "For active people who want gear that keeps up, the smart outdoor companion that turns a daily essential into a reliable ritual.",
    "target_audience": ["Hikers", "Outdoor commuters"],
    "key_messages": ["Built for real trails", "One clear, measurable benefit", "Honest claims, backed by testing"],
    "taglines": ["Go further, stay ready.", "Hydration that keeps pace.", "Built for the long way round."],
    "channel_plan": [
        {"channel": "Email list + site (owned)", "tactic": "Waitlist with early-bird tier", "kpi": "5,000 sign-ups"},
        {"channel": "Outdoor media and creators (earned)", "tactic": "Field-test loans and reviews", "kpi": "20 independent reviews"},
        {"channel": "Paid social test", "tactic": "Two-week creative test on trail audiences", "kpi": "CAC under $18"},
    ],
    "pricing_recommendation": "Launch in the $65-$79 core band with a transparent two-year warranty.",
    "risks": ["Incumbent price pressure", "Durability proof needed before making performance claims"],
    "compliance_status": "clear",
    "call_to_action": "Join the waitlist this week to lock in the founder price before launch.",
}).model_dump_json()

_FINAL = "Thought: I now can give a great answer\nFinal Answer: {text}"


class ScriptedLLM(BaseLLM):
    """Deterministic fake chat model. Thread-safe enough for parallel tasks."""

    llm_type: str = "scripted"

    def model_post_init(self, __context: Any) -> None:  # pydantic hook
        super().model_post_init(__context)
        object.__setattr__(self, "_lock", threading.Lock())
        object.__setattr__(self, "_counts", {})

    # -- capabilities ------------------------------------------------------------------
    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 128000

    # -- helpers -----------------------------------------------------------------------
    def _bump(self, key: str) -> int:
        with self._lock:
            n = self._counts.get(key, 0)
            self._counts[key] = n + 1
            return n

    @staticmethod
    def _text(messages: Any) -> tuple[str, str]:
        if isinstance(messages, str):
            return "", messages
        sys_txt = " ".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
        rest = " ".join(str(m.get("content", "")) for m in messages if m.get("role") != "system")
        return sys_txt, rest

    def _answer(self, messages: Any, response_model: Any = None) -> str:
        sys_txt, rest = self._text(messages)
        full = sys_txt + " " + rest
        low = rest.lower()
        role = (re.search(r"You are ([^.\n]+)\.", sys_txt) or re.search(r"role[:=]\s*([^\n]+)", sys_txt) or [None, ""])[1].strip()

        # natural-language (string) guardrails are judged by an LLM that must return {valid, feedback}
        if "complies with the given guardrail" in low or getattr(response_model, "__name__", "") == "LLMGuardrailResult":
            verdict = json.dumps({"valid": True, "feedback": None})
            return verdict if response_model is not None else _FINAL.format(text=verdict)
        # converter / structured-output requests ask us to emit raw JSON
        if response_model is not None:
            name = getattr(response_model, "__name__", "")
            if name == "CompetitorReport":
                return _COMPETITORS
            if name == "LaunchBrief":
                return _BRIEF
        # ---- Crew A ----
        if "research the market for this product" in low:
            n = self._bump("market")
            return _FINAL.format(text=_MARKET_BAD if n == 0 else _MARKET_GOOD)
        if "analyse customer sentiment" in low:
            return _FINAL.format(text=_VOICE)
        if "identify the 3 strongest competitors" in low:
            return _FINAL.format(text=_COMPETITORS)
        if "the competitor threat is serious" in low:
            return _FINAL.format(text=_DEEP_DIVE)
        if "combine the market scan" in low:
            if role == "Research Synthesizer" and self._bump("synth") == 0:
                return (
                    "Thought: The market figure should be double-checked by the researcher.\n"
                    "Action: Ask question to coworker\n"
                    'Action Input: {"question": "Please confirm the market size and growth figure with its source.", '
                    '"context": "Preparing the final briefing", "coworker": "Market Researcher"}'
                )
            return _FINAL.format(text=_SYNTH)
        # ---- Crew B (manager delegates, specialists answer) ----
        if role == "Launch Director":
            for key, who, task_words in (
                ("pos", "Brand Strategist", "create the positioning"),
                ("copy", "Copywriter", "write launch copy"),
                ("rev", "Compliance Reviewer", "review the copy draft"),
            ):
                if task_words in low:
                    n = self._bump(key)
                    if n == 0:
                        return (
                            f"Thought: This is a job for the {who}.\n"
                            "Action: Delegate work to coworker\n"
                            f'Action Input: {{"task": "{task_words}", "context": "Follow the brand guidelines", "coworker": "{who}"}}'
                        )
                    out = {"pos": _POSITIONING, "copy": _COPY_BAD if n == 1 else _COPY_GOOD, "rev": _REVIEW}[key]
                    return _FINAL.format(text=out)
            if "assemble the final creative package" in low:
                return _FINAL.format(text=_PACKAGE_BAD if self._bump("pkg") == 0 else _PACKAGE)
        if role == "Brand Strategist":
            return _FINAL.format(text=_POSITIONING)
        if role == "Copywriter":
            return _FINAL.format(text=_COPY_GOOD)
        if role == "Compliance Reviewer":
            return _FINAL.format(text=_REVIEW)
        if role == "Market Researcher":  # answering a delegated question
            return _FINAL.format(text=_MARKET_GOOD)
        # ---- Crew C ----
        if "produce the final launch brief" in low:
            return _FINAL.format(text=_BRIEF)
        return _FINAL.format(text="OK.")

    # -- BaseLLM interface ---------------------------------------------------------------
    def call(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None, from_agent=None, response_model=None):
        text = self._answer(messages, response_model)
        if response_model is not None and not text.lstrip().startswith("{"):
            text = text.split("Final Answer:", 1)[-1].strip()
        return text

    async def acall(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None, from_agent=None, response_model=None):
        return self.call(messages, tools, callbacks, available_functions, from_task, from_agent, response_model)
