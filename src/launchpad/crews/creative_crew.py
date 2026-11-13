"""CREW B - Creative & Compliance  (Process.hierarchical, manager + 3 specialists)

Shows:
  * HIERARCHICAL process: the Launch Director (manager_agent) breaks the goal down, delegates each task to the
    right specialist, reviews the result and can bounce work back.
  * custom manager agent (manager_agent=..., allow_delegation=True) instead of the auto-generated manager_llm
  * CONTEXT handoff between tasks, tools (brand guidelines lookup, claim scanner)
  * GUARDRAILS on tasks the manager owns (python-function guardrails)
Tasks deliberately have no ``agent=``: in a hierarchical crew the manager decides who does what.
"""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from launchpad.config import KNOWLEDGE_DIR, make_llm, verbose
from launchpad.crews.common import knowledge_sources, lifecycle
from launchpad.guardrails import creative_package_has_sections, no_banned_claims
from launchpad.tools import brand_guidelines_lookup, claim_risk_scanner


def build_creative_crew() -> Crew:
    worker = make_llm("worker")

    brand_strategist = Agent(
        role="Brand Strategist",
        goal="Define a sharp positioning for {product_name} that a {audience} audience will remember",
        backstory="An ex-agency strategist who writes positioning statements in one breath and hates buzzwords.",
        tools=[brand_guidelines_lookup],
        llm=worker, allow_delegation=False, verbose=verbose(),
    )
    copywriter = Agent(
        role="Copywriter",
        goal="Write launch copy that is vivid, specific and honest",
        backstory="A direct-response writer who turns features into one-line benefits.",
        tools=[brand_guidelines_lookup],
        llm=worker, allow_delegation=False, verbose=verbose(),
    )
    compliance_reviewer = Agent(
        role="Compliance Reviewer",
        goal="Make sure no claim in the copy is unsubstantiated, misleading or legally risky",
        backstory="A former advertising-standards reviewer. Polite, precise and impossible to sweet-talk.",
        tools=[claim_risk_scanner, brand_guidelines_lookup],
        llm=worker, allow_delegation=False, verbose=verbose(),
    )
    launch_director = Agent(
        role="Launch Director",
        goal="Deliver a compliant, persuasive creative package for {product_name}, on time",
        backstory=(
            "A veteran head of launches. Assigns each job to the right specialist, reads their work critically and sends "
            "it back when it is not good enough - especially when the Compliance Reviewer flags a claim."
        ),
        llm=make_llm("manager"), allow_delegation=True, verbose=verbose(),   # required for a manager
    )

    positioning = Task(
        name="positioning",
        description=(
            "Create the positioning for this launch: {brief}\n"
            "Deliver a one-sentence positioning statement (For <audience> who <need>, <product> is the <category> that "
            "<benefit>, unlike <alternative>), 3 key messages and the target audience. Follow the house brand guidelines."
        ),
        expected_output="Positioning statement, 3 key messages, target audience.",
    )
    copy_draft = Task(
        name="copy_draft",
        description=(
            "Using the positioning, write launch copy for {product_name}: 5 tagline options, a 50-word product blurb and "
            "one call to action. Follow the house tone and claims policy."
        ),
        expected_output="5 taglines, a ~50-word blurb and one call to action.",
        context=[positioning],
        guardrail=no_banned_claims,                 # GUARDRAIL: python function on the manager-owned task
        guardrail_max_retries=2,
    )
    compliance_review = Task(
        name="compliance_review",
        description=(
            "Review the copy draft for risky claims (use the Claim Risk Scanner). List each issue with a safer rewrite, then "
            "state whether the copy is CLEAR or NEEDS REVIEW. If it NEEDS REVIEW, the copywriter must revise it first."
        ),
        expected_output="A list of flagged claims with fixes, and a final verdict: CLEAR or NEEDS REVIEW.",
        context=[copy_draft],
    )
    creative_package = Task(
        name="creative_package",
        description=(
            "Assemble the final creative package for {product_name} as markdown with these sections: Positioning, "
            "Key Messages, Taglines, Blurb, Call to Action and Compliance Notes (include the reviewer's verdict). "
            "Use only the reviewed, compliant copy."
        ),
        expected_output="A markdown creative package with the six sections listed.",
        context=[positioning, copy_draft, compliance_review],     # final task sees everything before it
        guardrails=[creative_package_has_sections, no_banned_claims],
        guardrail_max_retries=2,
    )

    before, after = lifecycle("creative", "Crew B - Creative & Compliance")
    return Crew(
        name="creative_compliance",
        agents=[brand_strategist, copywriter, compliance_reviewer],   # manager is NOT in this list
        tasks=[positioning, copy_draft, compliance_review, creative_package],
        process=Process.hierarchical,
        manager_agent=launch_director,
        knowledge_sources=knowledge_sources(),
        verbose=verbose(),
        before_kickoff_callbacks=[before],
        after_kickoff_callbacks=[after],
    )
