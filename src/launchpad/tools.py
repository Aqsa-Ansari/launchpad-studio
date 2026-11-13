"""Tools: a real web-search tool (Tavily / Serper) plus simple deterministic custom tools.

The custom tools are intentionally tiny and offline so runs are cheap and reproducible,
and so you can see how @tool-decorated functions plug into agents.
"""
from __future__ import annotations

import os
import re
from typing import Type

from crewai.tools import BaseTool, tool
from pydantic import BaseModel, Field

from launchpad.config import KNOWLEDGE_DIR


# ---------------------------------------------------------------------------------------
# 1. Search: Tavily -> Serper -> offline sample data
# ---------------------------------------------------------------------------------------
class _SearchInput(BaseModel):
    search_query: str = Field(..., description="What to search the web for")


_OFFLINE_BANK = {
    "market": [
        ("Global category outlook 2026", "https://example.com/reports/category-outlook-2026",
         "Analysts expect mid-to-high single digit annual growth, driven by premium and 'smart' variants and by online direct-to-consumer sales."),
        ("Consumer spending trends", "https://example.com/insights/consumer-spending",
         "Shoppers are trading up in categories tied to outdoor activity and wellness, but remain price sensitive above the $50-$80 band."),
    ],
    "competitor": [
        ("Top brands compared", "https://example.com/reviews/top-brands-compared",
         "The category is led by two established brands with wide retail distribution and a long tail of crowdfunded start-ups."),
        ("Brand watch: challengers", "https://example.com/brandwatch/challengers",
         "Challenger brands compete on design and sustainability stories; incumbents compete on price, warranty and availability."),
    ],
    "review": [
        ("Customer review roundup", "https://example.com/community/review-roundup",
         "Recurring praise: build quality and convenience. Recurring complaints: battery or durability doubts, unclear warranty, and price."),
        ("Forum thread: what I wish I knew", "https://example.com/forum/what-i-wish-i-knew",
         "Buyers want proof of real-world durability and honest claims; they distrust vague 'eco' or 'smart' marketing language."),
    ],
    "price": [
        ("Pricing guide", "https://example.com/guides/pricing",
         "Entry products cluster near $25-$40, mainstream near $45-$70, premium connected products at $90-$150."),
    ],
}


class OfflineSearchTool(BaseTool):
    """Deterministic stand-in used when no search API key is configured."""

    name: str = "Offline Web Search"
    description: str = (
        "Search the web for market data, competitors, prices and customer reviews. "
        "Returns titles, URLs and snippets. (Offline sample data - no API key configured.)"
    )
    args_schema: Type[BaseModel] = _SearchInput

    def _run(self, search_query: str) -> str:
        q = search_query.lower()
        hits: list[tuple[str, str, str]] = []
        for key, rows in _OFFLINE_BANK.items():
            if key in q or (key == "review" and any(w in q for w in ("customer", "voice", "complain", "sentiment"))):
                hits.extend(rows)
        if not hits:
            hits = _OFFLINE_BANK["market"] + _OFFLINE_BANK["competitor"][:1]
        lines = [f"[OFFLINE SAMPLE DATA] Results for: {search_query}"]
        for i, (title, url, snippet) in enumerate(hits[:4], 1):
            lines.append(f"{i}. {title}\n   URL: {url}\n   {snippet}")
        return "\n".join(lines)


SEARCH_TOOL_NAMES = {"offline web search", "tavily_search", "tavily search", "search the internet with serper", "search the internet"}


def get_search_tool() -> BaseTool:
    if os.getenv("TAVILY_API_KEY"):
        from crewai_tools import TavilySearchTool

        return TavilySearchTool(max_results=5, search_depth="basic")
    if os.getenv("SERPER_API_KEY"):
        from crewai_tools import SerperDevTool

        return SerperDevTool(n_results=5)
    return OfflineSearchTool()


def search_backend_name() -> str:
    if os.getenv("TAVILY_API_KEY"):
        return "Tavily"
    if os.getenv("SERPER_API_KEY"):
        return "Serper"
    return "offline sample data"


# ---------------------------------------------------------------------------------------
# 2. Simple custom tools
# ---------------------------------------------------------------------------------------
_MARKET_TABLE = {
    "bottle": ("hydration & outdoor drinkware", 10.5, 6.8, "hikers, commuters, gym-goers"),
    "headphone": ("personal audio", 72.0, 9.1, "commuters, students, remote workers"),
    "coffee": ("home coffee equipment", 31.0, 5.5, "home enthusiasts, gift buyers"),
    "skin": ("skin care", 130.0, 5.9, "self-care shoppers, gift buyers"),
    "watch": ("wearables", 61.0, 14.0, "fitness users, early adopters"),
}


@tool("Market Size Lookup")
def market_size_lookup(category: str) -> str:
    """Look up an estimated global market size (USD billions), yearly growth rate and key
    segments for a product category. Use this before quoting any market-size number."""
    c = category.lower()
    for key, (name, size, cagr, seg) in _MARKET_TABLE.items():
        if key in c:
            return (
                f"Segment: {name}. Estimated global market: ${size}B. Growth (CAGR): {cagr}%. "
                f"Key buyer segments: {seg}. Source: LaunchPad internal estimates table (illustrative)."
            )
    return (
        f"No exact match for '{category}'. Generic consumer-hardware estimate: ~$20B, ~6% CAGR. "
        "Source: LaunchPad internal estimates table (illustrative). Treat as low confidence."
    )


@tool("Price Band Calculator")
def price_band_calculator(unit_cost_usd: float, target_gross_margin_pct: float) -> str:
    """Given a unit cost in USD and a target gross margin percentage (0-95), return the
    minimum retail price and a suggested 3-tier price ladder."""
    if not 0 <= target_gross_margin_pct < 95:
        return "target_gross_margin_pct must be between 0 and 95."
    floor = unit_cost_usd / (1 - target_gross_margin_pct / 100)
    return (
        f"Minimum retail price for a {target_gross_margin_pct:.0f}% margin: ${floor:.2f}. "
        f"Suggested ladder -> entry ${floor:.0f}, core ${floor * 1.25:.0f}, premium ${floor * 1.6:.0f}."
    )


_RISKY = {
    r"\bguarantee[sd]?\b": "Outcome guarantee - needs substantiation or removal",
    r"\b100\s?%\s*(safe|effective|natural)\b": "Absolute claim",
    r"\brisk[- ]free\b": "Risk-free claims are legally sensitive",
    r"\bcures?\b|\bheals?\b": "Medical/therapeutic claim",
    r"\bclinically proven\b": "Requires a cited clinical study",
    r"\bmiracle\b": "Hyperbolic claim",
    r"\bcarbon[- ]neutral\b|\beco[- ]friendly\b": "Environmental claim - needs verifiable proof",
    r"\b(best|#1|number one)\b.*\b(in the world|on the market|ever)\b": "Unqualified superlative",
}


def scan_claims(text: str) -> list[dict]:
    """Pure-python helper (also used by the flow). Returns [{claim, issue}]."""
    found = []
    for pattern, issue in _RISKY.items():
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            found.append({"claim": m.group(0), "issue": issue})
    return found


@tool("Claim Risk Scanner")
def claim_risk_scanner(text: str) -> str:
    """Scan marketing copy for risky or unsubstantiated claims (guarantees, medical,
    environmental, superlatives). Returns each flagged phrase with the reason."""
    found = scan_claims(text)
    if not found:
        return "No risky claim patterns detected by the rule-based scanner."
    return "Flagged:\n" + "\n".join(f"- '{f['claim']}': {f['issue']}" for f in found)


@tool("Brand Guidelines Lookup")
def brand_guidelines_lookup(topic: str) -> str:
    """Look up the house brand, tone and claims-policy rules for a topic such as 'tone',
    'claims', 'positioning', 'channels' or 'call to action'."""
    path = KNOWLEDGE_DIR / "brand_guidelines.txt"
    if not path.exists():
        return "Brand guidelines file not found."
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"\n(?=[A-Z][A-Z &()]+\n)", text)
    topic_l = topic.lower()
    matches = [s.strip() for s in sections if any(w in s.lower() for w in topic_l.split())]
    return "\n\n".join(matches[:2]) if matches else text[:1200]
