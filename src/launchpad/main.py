"""Command-line entry point.

    launchpad "your product brief" [--mock]        (after `pip install -e .`)
    python -m launchpad.main "your product brief"  [--mock]
"""
import argparse
import os


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the LaunchPad flow from the terminal.")
    ap.add_argument("brief", help="the product brief")
    ap.add_argument("--mock", action="store_true", help="use the scripted fake LLM (no API calls, no cost)")
    args = ap.parse_args()
    if args.mock:
        os.environ["LAUNCHPAD_MOCK"] = "1"

    from launchpad.events import HUB
    from launchpad.flow import run_flow

    flow = run_flow(args.brief)
    for e in HUB.snapshot():
        label = e.get("task") or e.get("name") or e.get("title") or e.get("label") or e.get("tool") or ""
        print(f"{e['t']:7.2f}s  {e['kind']:<12} {label:<36} {e.get('verdict') or e.get('type') or ''}")
    s = flow.state
    print("\nSTATUS:", s.status, "|", s.message)
    if s.launch_brief_markdown:
        print("\n" + s.launch_brief_markdown)
        print("Saved to:", s.saved_to)


if __name__ == "__main__":
    main()
