"""End-to-end runs of the whole flow with the scripted fake LLM (no network, no cost)."""
from launchpad.events import HUB
from launchpad.flow import run_flow

GOOD = "A solar-powered smart water bottle for hikers that tracks hydration and charges from sunlight"


def kinds():
    return [(e["kind"], e.get("task") or e.get("name") or e.get("type")) for e in HUB.snapshot()]


def test_happy_path_ships_a_brief():
    HUB.reset()
    flow = run_flow(GOOD)
    s = flow.state
    assert s.status == "shipped", (s.status, s.message, s.errors)
    assert s.launch_brief["taglines"] and s.market_report and s.creative_package
    assert s.competitor_threat == "high"
    assert s.saved_to.endswith(".md")


def test_parallelism_is_real():
    HUB.reset()
    run_flow(GOOD)
    ev = HUB.snapshot()
    starts = {e["task"]: e["t"] for e in ev if e["kind"] == "task_start"}
    dones = {e["task"]: e["t"] for e in ev if e["kind"] == "task_done"}
    # the three async tasks of Crew A all start before any of them finishes
    a = ["market_scan", "voice_scan", "competitor_scan"]
    assert max(starts[t] for t in a) < min(dones[t] for t in a)
    # Crew A and Crew B overlap
    crew = {e["crew"]: e["t"] for e in ev if e["kind"] == "crew_start"}
    crew_done = {e["crew"]: e["t"] for e in ev if e["kind"] == "crew_done"}
    assert max(crew["market"], crew["creative"]) < min(crew_done["market"], crew_done["creative"])


def test_every_handoff_type_and_guardrail_kind_appears():
    HUB.reset()
    run_flow(GOOD)
    ev = HUB.snapshot()
    handoffs = {e["type"] for e in ev if e["kind"] == "handoff"}
    assert {"task-context", "delegation", "hierarchical", "flow-state"} <= handoffs
    names = {e["name"] for e in ev if e["kind"] == "guardrail"}
    for expected in ("function: sources + length", "function: banned claims", "llm-judge: grounding",
                     "function: schema check", "flow: intake router", "flow: quality gate"):
        assert expected in names, expected
    assert any(e["kind"] == "guardrail" and e["verdict"] == "retry" for e in ev)  # a guardrail made an agent retry


def test_conditional_task_runs_on_high_threat():
    HUB.reset()
    run_flow(GOOD)
    assert ("task_start", "competitor_deep_dive") in kinds()


def test_clarify_route():
    HUB.reset()
    flow = run_flow("water bottle")
    assert flow.state.status == "clarify" and "who the product is for" in flow.state.message
    assert not any(e["kind"] == "crew_start" for e in HUB.snapshot())  # no crew was spent


def test_reject_route():
    HUB.reset()
    flow = run_flow("A rifle scope and ammunition bundle for hunters and sport shooters this season")
    assert flow.state.status == "rejected"
    assert not any(e["kind"] == "crew_start" for e in HUB.snapshot())
