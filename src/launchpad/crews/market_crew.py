"""CREW A - Market Intelligence  (Process.sequential, 4 agents)

Shows:
  * PARALLEL tasks:   three async_execution=True tasks run concurrently
  * CONTEXT handoff:  the synthesis task receives all of their outputs via context=[...]
  * DELEGATION:       the Research Synthesizer has allow_delegation=True (everyone else is locked down)
  * ConditionalTask:  a competitor deep-dive that only runs when the threat level is medium/high
  * GUARDRAILS:       python function (market_scan), natural-language string (voice_scan),
                      structured output_pydantic (competitor_scan), LLM-judge + built-in
                      HallucinationGuardrail chained (research_synthesis)
  * planning=True, tools (search + custom), before/after-kickoff callbacks
"""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task, TaskOutput
from crewai.tasks.conditional_task import ConditionalTask
from crewai.tasks.hallucination_guardrail import HallucinationGuardrail

from launchpad.config import env_bool, is_mock, make_llm, verbose
from launchpad.crews.common import lifecycle
from launchpad.events import emit
from launchpad.guardrails import STRING_RULES, cite_sources_and_length, make_grounding_guardrail
from launchpad.models import CompetitorReport
from launchpad.tools import get_search_tool, market_size_lookup, price_band_calculator


def is_serious_threat(previous: TaskOutput) -> bool:
    """Condition for the ConditionalTask - receives the previous task's output."""
    report = previous.pydantic
    level = getattr(report, "threat_level", None)
    run = level in ("medium", "high")
    if not run:
        emit("task_skipped", task="competitor_deep_dive", label="Competitor deep-dive (conditional)",
             body=f"Skipped: competitor threat is '{level}', so no deep-dive is needed.")
    else:
        emit("message", who="Flow", body=f"Competitor threat is '{level}': triggering the conditional deep-dive task.")
    return run


def build_market_crew() -> Crew:
    worker = make_llm("worker")
    search = get_search_tool()

    # ---- agents (only the synthesizer may delegate) ------------------------------------
    market_researcher = Agent(
        role="Market Researcher",
        goal="Size the market and find the real growth drivers for {category}",
        backstory="A former equity analyst who never quotes a number without a source.",
        tools=[search, market_size_lookup],
        llm=worker, allow_delegation=False, verbose=verbose(), max_iter=6,
    )
    competitor_analyst = Agent(
        role="Competitor Analyst",
        goal="Map the strongest competitors for {category} and judge how hard they are to beat",
        backstory="A competitive-intelligence specialist who has dissected hundreds of product launches.",
        tools=[search, price_band_calculator],
        llm=worker, allow_delegation=False, verbose=verbose(), max_iter=6,
    )
    voice_analyst = Agent(
        role="Customer Voice Analyst",
        goal="Distil what real buyers of {category} praise, fear and complain about",
        backstory="A qual researcher who reads thousands of reviews and writes about patterns, never individuals.",
        tools=[search],
        llm=worker, allow_delegation=False, verbose=verbose(), max_iter=6,
    )
    synthesizer = Agent(
        role="Research Synthesizer",
        goal="Merge the three research streams into one decision-ready briefing",
        backstory=(
            "A strategy lead who trusts but verifies. If two reports disagree she asks the relevant analyst "
            "to double-check before writing anything down."
        ),
        llm=make_llm("manager"), allow_delegation=True, verbose=verbose(), max_iter=8,
    )

    # ---- tasks ---------------------------------------------------------------------------
    market_scan = Task(
        name="market_scan",
        description=(
            "Research the market for this product: {brief}\n"
            "Cover market size, growth rate and the 2-3 forces driving demand in the {category} category. "
            "Use the Market Size Lookup tool and web search. Cite every figure with a URL or 'Source:' line."
        ),
        expected_output="60-400 words of bullet-point findings, each figure followed by its source.",
        agent=market_researcher,
        async_execution=True,                       # runs in parallel with the next two tasks
        guardrail=cite_sources_and_length,          # GUARDRAIL 1: python function
        guardrail_max_retries=2,
    )
    voice_scan = Task(
        name="voice_scan",
        description=(
            "Analyse customer sentiment for products like this: {brief}\n"
            "Search for reviews and forum discussions. Report the top 3 praised aspects, top 3 complaints and any "
            "unmet needs. Describe patterns only - never quote or name individual reviewers."
        ),
        expected_output="A neutral, structured summary: praised / complaints / unmet needs.",
        agent=voice_analyst,
        async_execution=True,
        guardrail=STRING_RULES["voice_no_pii"],     # GUARDRAIL 2: natural-language (LLM-checked)
        guardrail_max_retries=2,
    )
    competitor_scan = Task(
        name="competitor_scan",
        description=(
            "Identify the 3 strongest competitors for: {brief}\n"
            "For each: positioning, typical retail price in USD and their biggest strength. Then judge the overall threat "
            "level (low, medium or high) and name the strongest competitor."
        ),
        expected_output="A structured competitor report.",
        agent=competitor_analyst,
        async_execution=True,
        output_pydantic=CompetitorReport,           # structured output the ConditionalTask can inspect
    )
    # NOTE: competitor_scan is deliberately the LAST task before the conditional one - a ConditionalTask
    # evaluates the output of the task immediately before it.
    deep_dive = ConditionalTask(
        name="competitor_deep_dive",
        description=(
            "The competitor threat is serious. Take the strongest competitor from the competitor report and analyse their "
            "weaknesses, pricing moves and the one angle where a newcomer could beat them."
        ),
        expected_output="A short attack plan against the strongest competitor (under 200 words).",
        agent=competitor_analyst,
        condition=is_serious_threat,
        context=[competitor_scan],
    )

    def research_context() -> str:
        return "\n\n".join(
            f"## {t.name}\n{t.output.raw}" for t in (market_scan, voice_scan, competitor_scan, deep_dive) if t.output
        )

    synthesis = Task(
        name="research_synthesis",
        description=(
            "Combine the market scan, customer-voice scan, competitor scan and (if present) the deep-dive into a single "
            "market briefing for the launch of: {brief}\n"
            "Only state facts that appear in those reports. If two reports conflict, ask the responsible analyst to verify "
            "before you finalise. End with 3 concrete implications for the launch."
        ),
        expected_output="A cohesive briefing under 450 words: market, customers, competition, 3 launch implications.",
        agent=synthesizer,
        context=[market_scan, voice_scan, competitor_scan, deep_dive],   # CONTEXT handoff from 4 tasks
        guardrails=[                                                    # GUARDRAIL 3 + 4: chained
            make_grounding_guardrail(research_context),                 #   working LLM-as-judge
            HallucinationGuardrail(llm=make_llm("judge"), threshold=8.0),  # built-in (no-op in open source)
        ],
        guardrail_max_retries=2,
    )

    before, after = lifecycle("market", "Crew A - Market Intelligence")
    return Crew(
        name="market_intelligence",
        agents=[market_researcher, competitor_analyst, voice_analyst, synthesizer],
        tasks=[market_scan, voice_scan, competitor_scan, deep_dive, synthesis],
        process=Process.sequential,
        planning=env_bool("LAUNCHPAD_PLANNING"),
        planning_llm=worker,
        verbose=verbose(),
        before_kickoff_callbacks=[before],
        after_kickoff_callbacks=[after],
    )
