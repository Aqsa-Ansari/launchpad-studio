"""HTML builders. Everything takes plain dicts (the events from launchpad.events.HUB) and returns an HTML string."""
from __future__ import annotations

import html
import json
from typing import Any

from launchpad.events import TASK_META

CREWS = {
    "market": {"name": "Market", "color": "#3F6B4F"},
    "creative": {"name": "Creative", "color": "#B4532A"},
    "final": {"name": "Editor", "color": "#2F4B6B"},
    "flow": {"name": "Flow", "color": "#9A7410"},
}
LANES = [
    ("market", "Crew A  Market intelligence", "sequential + parallel"),
    ("creative", "Crew B  Creative & compliance", "hierarchical"),
    ("final", "Crew C  Launch editor", "chained guardrails"),
]
VERDICT_COLOR = {"pass": "#3F6B4F", "retry": "#B7791F", "flag": "#A63D2F", "reject": "#A63D2F", "clarify": "#2F4B6B", "redacted": "#6B4E8C"}
HANDOFF_COLOR = {"task-context": "#3F6B4F", "delegation": "#B7791F", "hierarchical": "#B4532A", "flow-state": "#2F4B6B"}


def h(s: str) -> str:
    """Collapse to a single line so Markdown never mistakes indented HTML for a code block."""
    return "".join(line.strip() for line in s.splitlines())


def esc(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def _crew(key: str) -> dict:
    return CREWS.get(key, CREWS["flow"])


def _summary(body: str, n: int = 210) -> str:
    text = " ".join(body.replace("#", " ").replace("*", " ").split())
    try:
        data = json.loads(body)
        if isinstance(data, dict) and "threat_level" in data:
            text = f"Threat level: {data['threat_level']}. Strongest competitor: {data.get('strongest_competitor', '?')}. {data.get('summary', '')}"
        elif isinstance(data, dict) and "taglines" in data:
            text = data.get("executive_summary", text)
    except Exception:
        pass
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


# ----------------------------------------------------------------------------------------------- chat feed
def user_note(text: str) -> str:
    return h(f'<div class="note-user"><div class="sticky"><span class="who">You</span>{esc(text)}</div></div>')


def running_tasks(events: list[dict]) -> list[dict]:
    started: dict[str, dict] = {}
    for e in events:
        if e["kind"] == "task_start":
            started[e["task"]] = e
        elif e["kind"] in ("task_done", "task_fail", "task_skipped"):
            started.pop(e.get("task", ""), None)
    return list(started.values())


def feed_html(events: list[dict], active: bool) -> str:
    out: list[str] = []
    for e in events:
        k = e["kind"]
        if k == "stage":
            out.append(h(f'<div class="line"><span><b>{esc(e["title"])}</b></span></div>'))
            if e["stage"] in ("stopped", "failed", "crews", "final"):
                out.append(h(f'<div class="alert" style="--c:#9A7410"><span class="k">Flow</span>{esc(e["body"])}</div>'))
        elif k == "task_done":
            c = _crew(e.get("crew", "flow"))
            body = e.get("body", "")
            out.append(h(f'''<div class="memo" style="--c:{c["color"]}">
              <div class="hd"><span class="tag">{c["name"]}</span><span class="role">{esc(e.get("agent") or "Agent")}</span>
              <span class="what">finished {esc(e.get("label"))}</span><span class="ts">{e["t"]:.1f}s</span></div>
              <div class="sum">{esc(_summary(body))}</div>
              <details><summary>Full output</summary><pre>{esc(body).replace(chr(10), "&#10;")}</pre></details></div>'''))
        elif k == "task_skipped":
            out.append(h(f'<div class="alert" style="--c:#6B6A5E"><span class="k">Skipped</span>{esc(e.get("body"))}</div>'))
        elif k == "message":
            out.append(h(f'<div class="alert" style="--c:#9A7410"><span class="k">{esc(e.get("who", "Flow"))}</span>{esc(e["body"])}</div>'))
        elif k == "error":
            out.append(h(f'<div class="alert" style="--c:#A63D2F"><span class="k">Error</span>{esc(e["body"])}</div>'))
        elif k == "task_fail":
            out.append(h(f'<div class="alert" style="--c:#A63D2F"><span class="k">Task failed</span>{esc(e.get("label"))}: {esc(e.get("body"))}</div>'))
        elif k == "guardrail" and e.get("verdict") in ("retry", "reject", "flag", "redacted"):
            col = VERDICT_COLOR[e["verdict"]]
            label = {"retry": "Guardrail: sent back", "reject": "Guardrail: rejected", "flag": "Guardrail: flagged", "redacted": "Guardrail: redacted"}[e["verdict"]]
            out.append(h(f'<div class="alert" style="--c:{col}"><span class="k">{label}</span>{esc(e["name"])} - {esc(e["detail"])}</div>'))
        elif k == "tool_blocked":
            out.append(h(f'<div class="alert" style="--c:#A63D2F"><span class="k">Tool blocked</span>{esc(e["agent"])} tried <b>{esc(e["tool"])}</b>: {esc(e["reason"])}</div>'))
        elif k == "handoff" and e.get("type") in ("delegation", "hierarchical"):
            c = HANDOFF_COLOR[e["type"]]
            out.append(h(f'<div class="alert" style="--c:{c}"><span class="k">Handoff - {esc(e["type"])}</span>{esc(e["src"])} &rarr; {esc(e["dst"])}</div>'))
    if active:
        run = running_tasks(events)
        if run:
            names = " and ".join(sorted({esc(r.get("agent") or r.get("label")) for r in run}))
            out.append(h(f'<div class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span> {names} working</div>'))
        else:
            out.append(h('<div class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span> studio working</div>'))
    return "".join(out)


def status_memo(result: dict) -> str:
    kind = {"clarify": ("Question", "#2F4B6B"), "rejected": ("Declined", "#A63D2F"), "failed": ("Failed", "#A63D2F")}.get(result["status"])
    if not kind:
        return ""
    msg = result.get("message") or "Something went wrong."
    extra = " Reply below and I will pick up where we left off." if result["status"] == "clarify" else ""
    return h(f'<div class="memo" style="--c:{kind[1]}"><div class="hd"><span class="tag">{kind[0]}</span><span class="role">Intake desk</span></div><div class="sum">{esc(msg)}{extra}</div></div>')


def brief_html(b: dict, status: str, errors: list[str] | None = None) -> str:
    flagged = status == "flagged"
    stamp = ("Flagged for review", "#A63D2F") if flagged else ("Ready to ship", "#3F6B4F")
    chips = "".join(f'<span class="chip">{esc(t)}</span>' for t in b["taglines"])
    aud = "".join(f'<span class="chip plain">{esc(a)}</span>' for a in b["target_audience"])
    msgs = "".join(f"<li>{esc(m)}</li>" for m in b["key_messages"])
    rows = "".join(f'<tr><td><b>{esc(c["channel"])}</b></td><td>{esc(c["tactic"])}</td><td>{esc(c["kpi"])}</td></tr>' for c in b["channel_plan"])
    risks = "".join(f"<li>{esc(r)}</li>" for r in b.get("risks", [])) or "<li>None identified</li>"
    errs = "".join(f"<li>{esc(x)}</li>" for x in (errors or []))
    err_block = f'<h4>Run notes</h4><ul>{errs}</ul>' if errs else ""
    return h(f'''<div class="doc">
      <div class="top"><div><div class="eyebrow">Launch brief</div><h2>{esc(b["product_name"])}</h2></div>
      <div class="stamp" style="--c:{stamp[1]}">{stamp[0]}</div></div>
      <h4>Executive summary</h4><p>{esc(b["executive_summary"])}</p>
      <h4>Positioning</h4><blockquote>{esc(b["positioning_statement"])}</blockquote>
      <h4>Audience</h4>{aud}
      <h4>Key messages</h4><ol>{msgs}</ol>
      <h4>Taglines</h4>{chips}
      <h4>Channel plan</h4><table><tr><th>Channel</th><th>Tactic</th><th>KPI</th></tr>{rows}</table>
      <h4>Pricing</h4><p>{esc(b["pricing_recommendation"])}</p>
      <h4>Risks</h4><ul>{risks}</ul>{err_block}
      <div class="cta">{esc(b["call_to_action"])}</div></div>''')


# ----------------------------------------------------------------------------------------------- control room
def pipeline_html(events: list[dict]) -> str:
    started = {e["task"] for e in events if e["kind"] == "task_start"}
    done = {e["task"] for e in events if e["kind"] == "task_done"}
    skipped = {e["task"] for e in events if e["kind"] == "task_skipped"}
    failed = {e["task"] for e in events if e["kind"] == "task_fail"}
    running = started - done - skipped - failed
    badge = '<span class="par">PARALLEL x%d</span>' % len(running) if len(running) > 1 else ""
    lanes = []
    for key, title, proc in LANES:
        steps = []
        for name, meta in TASK_META.items():
            if meta["crew"] != key:
                continue
            cls = "st-done" if name in done else "st-run" if name in running else "st-skip" if name in skipped else "st-fail" if name in failed else "st-wait"
            steps.append(f'<div class="tk {cls}"><span class="dot-s"></span>{esc(meta["label"])}</div>')
        lanes.append(f'<div class="lane" style="--c:{CREWS[key]["color"]}"><div class="t"><span>{esc(title)}</span><span class="p">{proc}</span></div>{"".join(steps)}</div>')
    return h(f'<div class="panel"><h5><span>Pipeline</span>{badge}</h5>{"".join(lanes)}</div>')


def _ledger(rows: list[str], empty: str) -> str:
    return h("".join(rows) if rows else f'<div class="empty">{empty}</div>')


def handoffs_html(events: list[dict]) -> str:
    rows = [
        f'<div class="led"><span class="tm">{e["t"]:.1f}s</span><span class="v" style="--c:{HANDOFF_COLOR.get(e["type"], "#666")}">{esc(e["type"])}</span>'
        f'{esc(e["src"])} &rarr; {esc(e["dst"])}<span class="d">{esc(e.get("note", ""))}</span></div>'
        for e in events if e["kind"] == "handoff"
    ]
    legend = '<div class="legend">task-context &middot; delegation &middot; hierarchical &middot; flow-state</div>'
    return h(legend) + _ledger(rows[-40:], "No handoffs yet.")


def guardrails_html(events: list[dict]) -> str:
    gs = [e for e in events if e["kind"] == "guardrail"]
    blocked = [e for e in events if e["kind"] == "tool_blocked"]
    rows = []
    for e in gs:
        rows.append(
            f'<div class="led"><span class="tm">{e["t"]:.1f}s</span><span class="v" style="--c:{VERDICT_COLOR.get(e["verdict"], "#666")}">{esc(e["verdict"])}</span>'
            f'{esc(e["name"])}<span class="d">{esc(str(e["detail"])[:120])}</span></div>'
        )
    for e in blocked:
        rows.append(f'<div class="led"><span class="tm">{e["t"]:.1f}s</span><span class="v" style="--c:#A63D2F">blocked</span>tool: {esc(e["reason"])}<span class="d">{esc(e["tool"])}: {esc(e["detail"])}</span></div>')
    retries = sum(1 for e in gs if e["verdict"] == "retry")
    head = f'<div class="legend">{len(gs)} checks &middot; {retries} sent back &middot; {len(blocked)} tool calls blocked</div>'
    return h(head) + _ledger(rows[-60:], "No guardrail checks yet.")


def tools_html(events: list[dict]) -> str:
    rows = [
        f'<div class="led"><span class="tm">{e["t"]:.1f}s</span><b>{esc(e["tool"])}</b> <span style="color:#6B6A5E">by {esc(e["agent"])}</span><span class="d">{esc(e["args"])}</span></div>'
        for e in events if e["kind"] == "tool"
    ]
    return _ledger(rows[-40:], "No tool calls yet.")


def welcome_html() -> str:
    return h('''<div class="welcome"><h3>Hand us a product. We will hand you a launch plan.</h3>
      <p>Describe what you are launching in a sentence or two - what it is and who it is for. Two crews of AI specialists then work on it at the same time.</p>
      <div class="steps">
      <div class="step" style="--c:#9A7410"><b>1 &middot; Intake</b>A flow-level guardrail reads your brief. It can decline it, or ask you a question first.</div>
      <div class="step" style="--c:#3F6B4F"><b>2 &middot; Two crews, in parallel</b>Market intelligence and creative &amp; compliance run side by side.</div>
      <div class="step" style="--c:#2F4B6B"><b>3 &middot; Launch brief</b>An editor merges both into one structured plan, checked by chained guardrails.</div>
      </div></div>''')
