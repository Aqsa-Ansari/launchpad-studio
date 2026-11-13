from crewai import TaskOutput

from launchpad.guardrails import (
    cite_sources_and_length,
    creative_package_has_sections,
    intake_decision,
    launch_brief_schema_check,
    no_banned_claims,
)
from launchpad.models import BriefInfo
from launchpad.tools import scan_claims


def out(text: str) -> TaskOutput:
    return TaskOutput(description="d", raw=text, agent="a")


def test_sources_and_length_rejects_short_and_unsourced():
    ok, msg = cite_sources_and_length(out("too short"))
    assert not ok and "words" in msg
    body = "word " * 100
    ok, msg = cite_sources_and_length(out(body))
    assert not ok and "sources" in msg


def test_sources_and_length_accepts_good_text():
    body = ("word " * 80) + "Source: a. https://example.com/x"
    ok, _ = cite_sources_and_length(out(body))
    assert ok


def test_banned_claims():
    ok, msg = no_banned_claims(out("Hydration, guaranteed."))
    assert not ok and "guarantee" in msg
    ok, _ = no_banned_claims(out("Hydration that keeps pace."))
    assert ok


def test_package_sections():
    ok, _ = creative_package_has_sections(out("Positioning ... Taglines ... Compliance notes"))
    assert ok
    ok, msg = creative_package_has_sections(out("only positioning"))
    assert not ok and "tagline" in msg


def test_schema_check_rejects_non_json():
    ok, _ = launch_brief_schema_check(out("not json"))
    assert not ok


def test_schema_check_rejects_duplicate_taglines():
    from launchpad.mock_llm import _BRIEF
    import json

    data = json.loads(_BRIEF)
    data["taglines"] = ["Same", "Same", "Other"]
    ok, msg = launch_brief_schema_check(out(json.dumps(data)))
    assert not ok and "unique" in msg


def test_schema_check_recovers_json_wrapped_in_prose():
    from launchpad.mock_llm import _BRIEF

    ok, result = launch_brief_schema_check(out("Here you go:\n```json\n" + _BRIEF + "\n```"))
    assert ok and isinstance(result, str) and result.startswith("{")


def test_intake_decisions():
    good = BriefInfo(product_name="X", category="bottle", audience="hikers")
    assert intake_decision("A solar powered smart bottle for hikers who need hydration data", good)[0] == "approved"
    assert intake_decision("bottle", BriefInfo(category="bottle", missing=["audience"]))[0] == "clarify"
    assert intake_decision("Sell firearms to hobbyists for target practice, new line", good)[0] == "rejected"


def test_claim_scanner():
    flags = scan_claims("This miracle bottle is risk-free and eco-friendly")
    kinds = {f["claim"].lower() for f in flags}
    assert {"miracle", "risk-free", "eco-friendly"} <= kinds
