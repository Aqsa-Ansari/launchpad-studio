"""CREW C - the Launch Editor (one agent, one task) - the flow's final merge step.

Shows the CHAINED guardrails=[...] feature: python check -> schema/business-rule check -> plain-English rule.
Each guardrail receives the previous guardrail's output; any failure sends feedback to the agent for a retry.
Its inputs are the *flow state* (outputs of Crew A and Crew B), i.e. the flow-state handoff.
"""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from launchpad.config import make_llm, verbose
from launchpad.crews.common import lifecycle
from launchpad.guardrails import STRING_RULES, launch_brief_schema_check, no_banned_claims
from launchpad.models import LaunchBrief


def build_final_crew() -> Crew:
    editor = Agent(
        role="Launch Editor",
        goal="Turn research and creative work into one precise, structured launch brief",
        backstory="A chief of staff who edits ruthlessly, resolves conflicts between teams and never invents facts.",
        llm=make_llm("manager"), allow_delegation=False, verbose=verbose(),
    )
    launch_brief = Task(
        name="launch_brief",
        description=(
            "Produce the final launch brief for {product_name}.\n\n"
            "=== MARKET INTELLIGENCE (Crew A) ===\n{market_report}\n\n"
            "=== CREATIVE PACKAGE (Crew B) ===\n{creative_package}\n\n"
            "=== AUTOMATED PRE-CHECKS ===\n{flags}\n\n"
            "Rules: use only facts present above. Provide at least 3 key messages, 3 unique taglines (max 12 words each), "
            "3 channel-plan items with a KPI each, a pricing recommendation, and the key risks. Set compliance_status to "
            "'needs_review' if any pre-check flagged something or the reviewer said NEEDS REVIEW, otherwise 'clear'."
        ),
        expected_output="A JSON object matching the LaunchBrief schema.",
        agent=editor,
        output_pydantic=LaunchBrief,
        guardrails=[                                  # CHAINED guardrails, executed in order
            launch_brief_schema_check,                #   1. python: schema + business rules
            no_banned_claims,                         #   2. python: banned-claim scan on the JSON text
            STRING_RULES["brief_tone_and_cta"],       #   3. natural language, judged by the agent's LLM
        ],
        guardrail_max_retries=2,
    )
    before, after = lifecycle("final", "Crew C - Launch Editor")
    return Crew(
        name="launch_editor",
        agents=[editor],
        tasks=[launch_brief],
        process=Process.sequential,
        verbose=verbose(),
        before_kickoff_callbacks=[before],
        after_kickoff_callbacks=[after],
    )
