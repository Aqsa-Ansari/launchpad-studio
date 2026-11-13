"""Brief intake: extract product name / category / audience and note what is missing."""
from __future__ import annotations

import json
import re

from launchpad.config import is_mock, make_llm
from launchpad.models import BriefInfo

PROMPT = """Extract launch information from this product brief.
Brief: "{brief}"
Reply with JSON only, using exactly these keys:
{{"product_name": str, "category": str, "audience": str, "missing": [str]}}
- Use "" for anything the brief does not state or clearly imply.
- "missing" may contain only these values: "audience", "category", "product_name", "details"."""


def _heuristic(brief: str) -> BriefInfo:
    low = brief.lower()
    audience = ""
    m = re.search(r"\bfor ([a-z ,&-]{3,60})", low)
    if m:
        audience = m.group(1).strip(" ,.")
    category = ""
    for kw in ("bottle", "headphone", "coffee", "skin", "watch", "app", "shoe", "backpack", "speaker", "lamp"):
        if kw in low:
            category = kw
            break
    name = ""
    m = re.search(r"(?:called|named)\s+([A-Z][\w-]+(?:\s[A-Z][\w-]+)?)", brief)
    if m:
        name = m.group(1)
    missing = [k for k, v in (("audience", audience), ("category", category)) if not v]
    return BriefInfo(product_name=name or "the product", category=category, audience=audience, missing=missing)


def extract_brief_info(brief: str) -> BriefInfo:
    if is_mock():
        return _heuristic(brief)
    try:
        raw = make_llm("judge").call(PROMPT.format(brief=brief.replace('"', "'")))
        match = re.search(r"\{.*\}", str(raw), flags=re.DOTALL)
        return BriefInfo(**json.loads(match.group(0)))
    except Exception:
        return _heuristic(brief)
