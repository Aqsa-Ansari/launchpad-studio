# LaunchPad — an AI product-launch studio built to show off CrewAI

Type a product idea into a chat. LaunchPad checks it, runs **two crews of AI specialists in parallel**
(market intelligence + creative & compliance), merges their work into one structured **launch brief**, and
shows you every handoff and guardrail as it happens.

It is a teaching project: every major CrewAI feature appears once, in a place where it makes sense.
Built and tested against **CrewAI 1.15.40**.

```
 you ──▶ intake guardrail ──┬─ rejected ──▶ polite refusal
                            ├─ clarify  ──▶ the studio asks you a question (you answer in the chat)
                            └─ approved
                                  │         asyncio.gather( crewA.akickoff() , crewB.akickoff() )
                    ┌─────────────┴──────────────┐
                    ▼                            ▼
          CREW A  Market intelligence     CREW B  Creative & compliance
          (sequential, 4 agents)          (hierarchical, manager + 3 agents)
          3 tasks run in parallel         Launch Director delegates to specialists
          → conditional deep-dive
          → synthesis (delegation)
                    └─────────────┬──────────────┘
                                  ▼
                  2 parallel pre-checks ──and_──▶ CREW C  Launch editor (chained guardrails)
                                                      ▼
                                              quality-gate router ──▶ "ship" / "flag for review"
                                                      ▼
                                       launch brief (.md + .json saved to output/)
```

---

## Quick start

**Requirements:** Python 3.10 – 3.13 and (for real runs) an OpenAI API key.

```bash
# 1. create an environment and install
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"              # installs crewai 1.15.40, crewai-tools, streamlit, pytest

# 2. configure
cp .env.example .env                 # then put your OPENAI_API_KEY in .env

# 3. run the chat app
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501) and describe a product.

### No API key? Try the free dry run
Flip **“Dry run”** in the sidebar (it is on by default when no key is found). The *real* flow, crews, guardrails and
handoffs run, but a scripted fake LLM replaces OpenAI, so it costs nothing and finishes in seconds. It even makes
a couple of guardrails fail on purpose so you can watch the retry loop.

### Other ways to run it
```bash
launchpad "A solar-powered smart water bottle for hikers" --mock   # CLI, prints the event timeline + brief
python scripts/plot_flow.py                                        # draws the flow diagram → output/launch_flow.html
pytest                                                             # 20 offline tests, no API key needed
```

### Things to try in the chat
| You type | What happens |
|---|---|
| A full brief (“…smart bottle for hikers that tracks hydration”) | Full run, brief at the end |
| `water bottle` | Intake **asks a clarifying question**; your reply is merged into the original brief |
| `sell firearms and ammunition to hobbyists` | Intake **rejects** it before any crew is spent |

---

## What you will see in the app

* **Chat (left):** your messages as sticky notes, agents’ finished work as memo cards (expand for full output),
  inline notes whenever a guardrail sends work back or a handoff happens, and the final launch brief as a document.
* **Control room (right):** a live **pipeline** (with a *PARALLEL ×N* badge while tasks overlap) and three ledgers:
  **Handoffs**, **Guardrails**, **Tools**.

---

## Where each CrewAI feature lives

### Handoffs
| Type | Where |
|---|---|
| **Sequential task pipeline** | Crew A (`process=Process.sequential`), Crew C |
| **Task context sharing** (`context=[...]`) | `research_synthesis` takes 4 tasks; `creative_package` takes 3; each Crew B task takes the previous one |
| **Agent delegation** (`allow_delegation=True`) | Research Synthesizer can ask analysts to verify a figure. Everyone else is locked to `False` to show the contrast |
| **Hierarchical manager** (`Process.hierarchical`) | Crew B: a custom `manager_agent` (Launch Director) assigns every task to a specialist |
| **Flow-state handoff** | A Pydantic `LaunchState` carries crew outputs between flow steps; Crew C receives them as inputs |

### Guardrails
| Type | Where |
|---|---|
| **Custom Python function** | `cite_sources_and_length` (Market Researcher), `no_banned_claims` (copy + package), `creative_package_has_sections` — `guardrails.py` |
| **Built-in `HallucinationGuardrail`** | On `research_synthesis`. ⚠️ In open-source CrewAI this is a **no-op** (it always passes and prints a warning — that is expected) |
| **Working LLM-as-judge** | `make_grounding_guardrail` scores the synthesis against the raw research and rejects unsupported claims |
| **Natural-language string** | `voice_scan` (“no PII, neutral tone”) and the final brief’s tone/CTA rule |
| **Chained `guardrails=[...]`** | Crew C: python schema check → banned-claims check → plain-English rule. Also `research_synthesis` |
| **Flow-level (`@router`)** | `intake` gate (reject / clarify / approve) and the `quality_gate` router (ship / flag) |
| **Tool-level (`@before_tool_call`)** | `hooks.py`: blocks sensitive searches, caps searches per run, enforces a domain allow-list; `@after_tool_call` redacts e-mails/phones |

### Parallelism
| Kind | Where |
|---|---|
| **Parallel tasks inside one crew** | Crew A: `market_scan`, `voice_scan`, `competitor_scan` are `async_execution=True`, followed by a synchronous task that uses their `context` |
| **Parallel crews (`akickoff`)** | `flow.py → run_both_crews`: `asyncio.gather(crew_a.akickoff(), crew_b.akickoff())` |
| **Parallel flow listeners** | `score_research` and `scan_creative` run concurrently; `and_()` joins them before the final crew |

### Extras
`@start / @listen / @router`, `or_` / `and_`, Pydantic flow state, `ConditionalTask` (deep-dive only if competitor threat is
medium/high), structured output (`output_pydantic`), `planning=True` (real runs), custom `@tool`s, Tavily/Serper search,
`before_kickoff` / `after_kickoff` callbacks, a CrewAI **event listener** feeding the UI, optional `@persist`,
optional knowledge source, `flow.plot()`.

---

## Project structure

```
launchpad-studio/
├── app.py                      # Streamlit chat front-end (run this)
├── pyproject.toml              # package + dependencies (pip install -e .)
├── requirements.txt            # same pins, for plain `pip install -r`
├── .env.example                # copy to .env
├── .streamlit/config.toml      # light theme
├── knowledge/
│   └── brand_guidelines.txt    # house tone + claims policy (tool, and optional knowledge source)
├── output/                     # generated launch briefs (.md + .json) land here
├── scripts/
│   └── plot_flow.py            # render the flow diagram
├── src/launchpad/
│   ├── main.py                 # CLI entry point
│   ├── flow.py                 # ★ LaunchFlow: routers, parallel crews, and_/or_, state
│   ├── crews/
│   │   ├── market_crew.py      # ★ Crew A — sequential, parallel tasks, conditional task, delegation
│   │   ├── creative_crew.py    # ★ Crew B — hierarchical with a custom manager
│   │   ├── final_crew.py       # ★ Crew C — chained guardrails
│   │   └── common.py           # kickoff callbacks, optional knowledge source
│   ├── guardrails.py           # task-level + flow-level guardrails
│   ├── hooks.py                # tool-level guardrails (before/after tool call)
│   ├── tools.py                # search (Tavily/Serper/offline) + custom tools
│   ├── models.py               # Pydantic: structured outputs, intake info, flow state
│   ├── intake.py               # brief → product / category / audience
│   ├── events.py               # event hub + CrewAI event-bus listener (powers the UI)
│   ├── config.py               # env switches + LLM factory
│   ├── mock_llm.py             # scripted fake LLM for free dry runs and tests
│   └── ui/
│       ├── styles.py           # CSS (paper-and-ink theme)
│       └── render.py           # HTML builders for chat, pipeline, ledgers, brief
└── tests/                      # 20 offline tests (guardrails, hooks, full flow end-to-end)
```
Start reading at **`flow.py`**, then the three files in `crews/`. Agents and tasks are defined in Python (not YAML)
so each feature sits next to its explanation.

---

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | – | Required for real runs |
| `LAUNCHPAD_MODEL` | `gpt-4o-mini` | Worker agents |
| `LAUNCHPAD_MANAGER_MODEL` | `gpt-4o` | Crew B manager, synthesizer and final editor |
| `LAUNCHPAD_JUDGE_MODEL` | worker model | Intake extraction + LLM-as-judge |
| `TAVILY_API_KEY` / `SERPER_API_KEY` | – | Real web search (Tavily wins if both are set). With neither, agents use offline sample data |
| `LAUNCHPAD_MOCK` | `0` | `1` = scripted fake LLM |
| `LAUNCHPAD_VERBOSE` | `0` | `1` = CrewAI console logs |
| `LAUNCHPAD_USE_KNOWLEDGE` | `0` | `1` = also load `knowledge/` as a CrewAI knowledge source (uses embeddings) |
| `LAUNCHPAD_PERSIST` | `0` | `1` = save flow state to SQLite after every step |
| `LAUNCHPAD_MAX_SEARCHES` | `24` | Tool guardrail: search budget per run |
| `LAUNCHPAD_ALLOWED_DOMAINS` | empty | Comma list; if set, URL-taking tools may only visit these |

**Cost note:** a real run makes dozens of LLM calls (two crews, planning, delegation, guardrail retries, judge).
Expect cents with the default models; use the dry run while developing.

---

## Troubleshooting

* **“Hallucination detection is a no-op in open source”** — expected; see *Guardrails* above. The LLM-as-judge is the working check.
* **A guardrail keeps failing** — after its retries CrewAI raises; LaunchPad catches it and continues with whatever the other crew produced (the brief is then *flagged for review*). Raise `guardrail_max_retries` in the crew files to be more forgiving.
* **Search returns “OFFLINE SAMPLE DATA”** — no Tavily/Serper key is set; add one to `.env` for live results.
* **The UI looks unstyled** — fonts load from Google Fonts; offline it falls back to Georgia/system fonts (still fine).
* **One run at a time** — the event hub is a process-wide singleton, so this demo is built for a single active user.

## Extending it
Add an agent: edit the crew file and add a task. Add a guardrail: write a `(TaskOutput) -> Tuple[bool, Any]` function in
`guardrails.py` and attach it with `guardrail=` / `guardrails=[...]`. Add a tool: decorate a function with `@tool` in `tools.py`.


## License
MIT - see [LICENSE](LICENSE).