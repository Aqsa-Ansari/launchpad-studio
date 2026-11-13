"""Small helpers shared by all crews."""
from __future__ import annotations

from typing import Any, Callable

from launchpad.config import KNOWLEDGE_DIR, use_knowledge
from launchpad.events import emit


def lifecycle(crew_key: str, title: str) -> tuple[Callable, Callable]:
    """before_kickoff / after_kickoff callbacks: emit crew-level start/finish events."""

    def before(inputs: dict[str, Any] | None):
        emit("crew_start", crew=crew_key, label=title)
        return inputs

    def after(output: Any):
        emit("crew_done", crew=crew_key, label=title)
        return output

    return before, after


def knowledge_sources() -> list:
    """Optional: expose knowledge/brand_guidelines.txt as a CrewAI knowledge source (needs embeddings)."""
    if not use_knowledge():
        return []
    from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

    return [TextFileKnowledgeSource(file_paths=[str((KNOWLEDGE_DIR / "brand_guidelines.txt").name)])]
