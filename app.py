"""LaunchPad - Streamlit front-end.   Run with:  streamlit run app.py"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))  # lets `streamlit run app.py` work without `pip install -e .`

import streamlit as st  # noqa: E402

st.set_page_config(page_title="LaunchPad - dispatch desk", page_icon="📎", layout="wide")

from launchpad import config  # noqa: E402
from launchpad.events import HUB  # noqa: E402
from launchpad.flow import run_flow  # noqa: E402
from launchpad.tools import search_backend_name  # noqa: E402
from launchpad.ui import render  # noqa: E402
from launchpad.ui.styles import CSS  # noqa: E402

EXAMPLES = [
    "A solar-powered smart water bottle for hikers that tracks hydration and charges from sunlight",
    "A subscription coffee grinder for home baristas that learns your taste and reorders beans",
    "Noise-cancelling headphones for open-plan office workers, priced under $120",
]

st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------------------------------------ run handling
class Run:
    """One background execution of the flow (Streamlit reruns the script, so the work happens in a thread)."""

    def __init__(self) -> None:
        self.done = False
        self.flow = None
        self.error: str | None = None


def start_run(user_text: str) -> None:
    turns: list[dict] = st.session_state.turns
    prev = turns[-1] if turns else None
    # if the studio asked a clarifying question, the reply is appended to the earlier brief
    brief = f"{prev['brief']} {user_text}" if prev and prev["result"] and prev["result"]["status"] == "clarify" else user_text
    turn = {"user": user_text, "brief": brief, "events": [], "result": None, "done": False}
    turns.append(turn)

    if not config.is_mock() and not os.getenv("OPENAI_API_KEY"):
        turn.update(done=True, result={"status": "failed", "message": "No OPENAI_API_KEY found. Add it to .env, or switch on the dry-run toggle in the sidebar.", "launch_brief": {}, "errors": []})
        return

    HUB.reset()
    run = Run()

    def work() -> None:
        try:
            run.flow = run_flow(brief)
        except Exception as exc:  # the flow degrades gracefully, but never leave the UI hanging
            run.error = f"{type(exc).__name__}: {exc}"
        finally:
            run.done = True

    st.session_state.run = run
    threading.Thread(target=work, daemon=True).start()


def finalize_if_done() -> bool:
    run: Run | None = st.session_state.get("run")
    if not run or not run.done:
        return False
    turn = st.session_state.turns[-1]
    s = run.flow.state if run.flow else None
    turn["events"] = HUB.snapshot()
    turn["result"] = (
        {"status": "failed", "message": run.error or "The run ended without a result.", "launch_brief": {}, "errors": []}
        if s is None
        else {"status": s.status, "message": s.message, "launch_brief": s.launch_brief, "markdown": s.launch_brief_markdown,
              "saved_to": s.saved_to, "errors": list(s.errors)}
    )
    turn["done"] = True
    st.session_state.run = None
    return True


# ------------------------------------------------------------------------------------------------ session + sidebar
st.session_state.setdefault("turns", [])
st.session_state.setdefault("run", None)
running = st.session_state.run is not None

with st.sidebar:
    st.markdown("### LaunchPad")
    st.caption("Dispatch desk for product launches")
    default_mock = config.is_mock() or not os.getenv("OPENAI_API_KEY")
    mock = st.toggle("Dry run (scripted agents, no API cost)", value=default_mock, disabled=running,
                     help="Runs the real flow, crews, guardrails and handoffs, but with a scripted fake LLM. Good for a free demo.")
    os.environ["LAUNCHPAD_MOCK"] = "1" if mock else "0"
    if not mock and not os.getenv("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY is not set.")
    st.markdown("**Engine**")
    st.caption(f"Workers: `{config.worker_model()}`  \nManager / editor: `{config.manager_model()}`  \nSearch: {search_backend_name()}")
    st.markdown("**Try an example**")
    for i, ex in enumerate(EXAMPLES):
        if st.button(ex[:46] + "…", key=f"ex{i}", disabled=running, use_container_width=True):
            st.session_state.pending = ex
    st.divider()
    if st.button("New conversation", disabled=running, use_container_width=True):
        st.session_state.turns = []
        HUB.reset()
        st.rerun()

st.markdown(
    '<div class="mast"><h1>Launch<i>Pad</i></h1><div class="sub">Dispatch desk<br>two crews &middot; one flow &middot; one brief</div></div>',
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------------------------ input
prompt = st.chat_input("Describe a product to launch, or answer the studio's question…", disabled=running)
prompt = prompt or st.session_state.pop("pending", None)
if prompt and not running:
    start_run(prompt)
    running = st.session_state.run is not None


# ------------------------------------------------------------------------------------------------ live workspace
def workspace() -> None:
    if finalize_if_done():
        st.rerun()  # full rerun: re-enables the chat box and stops the polling fragment
    turns: list[dict] = st.session_state.turns
    active = st.session_state.run is not None
    if not turns:
        st.html(render.welcome_html())
        return

    chat, side = st.columns([1.6, 1], gap="large")
    with chat:
        for i, t in enumerate(turns):
            st.html(render.user_note(t["user"]))
            is_live = active and i == len(turns) - 1
            events = HUB.snapshot() if is_live else t["events"]
            st.html(render.feed_html(events, active=is_live))
            r = t["result"]
            if r and not is_live:
                if r["status"] in ("clarify", "rejected", "failed"):
                    st.html(render.status_memo(r))
                elif r["launch_brief"]:
                    st.html(render.brief_html(r["launch_brief"], r["status"], r["errors"]))
                    d1, d2, _ = st.columns([1, 1, 2])
                    d1.download_button("Download .md", r["markdown"], file_name=Path(r["saved_to"]).name, key=f"md{i}")
                    d2.download_button("Download .json", json.dumps(r["launch_brief"], indent=2),
                                       file_name=Path(r["saved_to"]).with_suffix(".json").name, key=f"js{i}")
    with side:
        last = turns[-1]
        ev = HUB.snapshot() if active else last["events"]
        st.html(render.pipeline_html(ev))
        t1, t2, t3 = st.tabs(["Handoffs", "Guardrails", "Tools"])
        with t1:
            st.html(render.handoffs_html(ev))
        with t2:
            st.html(render.guardrails_html(ev))
        with t3:
            st.html(render.tools_html(ev))


# Poll once a second only while a run is in flight; otherwise render statically.
st.fragment(workspace, run_every=1.0 if running else None)()
