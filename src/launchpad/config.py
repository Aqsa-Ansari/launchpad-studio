"""Environment-driven configuration and LLM factories.

Everything that can change between runs is read at *call time* (not import time),
so the Streamlit sidebar can flip switches such as mock mode without a restart.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = ROOT / "knowledge"
OUTPUT_DIR = ROOT / "output"

load_dotenv(ROOT / ".env")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
# Closures used as callbacks/guardrails trigger a harmless "cannot be saved in a checkpoint" notice.
warnings.filterwarnings("ignore", message="A function callback cannot be saved")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_mock() -> bool:
    return env_bool("LAUNCHPAD_MOCK")


def verbose() -> bool:
    return env_bool("LAUNCHPAD_VERBOSE")


def use_knowledge() -> bool:
    return env_bool("LAUNCHPAD_USE_KNOWLEDGE") and not is_mock()


def worker_model() -> str:
    return os.getenv("LAUNCHPAD_MODEL", "gpt-4o-mini")


def manager_model() -> str:
    return os.getenv("LAUNCHPAD_MANAGER_MODEL", "gpt-4o")


def judge_model() -> str:
    return os.getenv("LAUNCHPAD_JUDGE_MODEL", worker_model())


def make_llm(kind: str = "worker"):
    """Return a CrewAI LLM. kind: worker | manager | judge."""
    if is_mock():
        from launchpad.mock_llm import ScriptedLLM

        return ScriptedLLM(model=f"mock-{kind}")

    from crewai import LLM

    name = {"worker": worker_model, "manager": manager_model, "judge": judge_model}[kind]()
    kwargs: dict = {"model": f"openai/{name}"}
    # Reasoning-family models reject custom temperatures; only set it for classic chat models.
    if name.startswith(("gpt-4", "gpt-3.5")):
        kwargs["temperature"] = 0.2 if kind == "judge" else 0.4
    return LLM(**kwargs)
