from types import SimpleNamespace

from launchpad import hooks
from launchpad.events import HUB


def ctx(tool="Offline Web Search", **tool_input):
    return SimpleNamespace(tool_name=tool, tool_input=tool_input, agent=SimpleNamespace(role="Tester"), tool_result=None)


def test_sensitive_query_is_blocked():
    HUB.reset()
    assert hooks.block_sensitive_queries(ctx(search_query="find leaked passwords of customers")) is False
    assert any(e["kind"] == "tool_blocked" for e in HUB.snapshot())
    assert hooks.block_sensitive_queries(ctx(search_query="market size smart bottles")) is None


def test_search_budget(monkeypatch):
    monkeypatch.setenv("LAUNCHPAD_MAX_SEARCHES", "2")
    hooks.reset_tool_budget()
    assert hooks.enforce_search_budget(ctx(search_query="a")) is None
    assert hooks.enforce_search_budget(ctx(search_query="b")) is None
    assert hooks.enforce_search_budget(ctx(search_query="c")) is False
    hooks.reset_tool_budget()


def test_non_search_tools_are_not_budgeted():
    hooks.reset_tool_budget()
    for _ in range(50):
        assert hooks.enforce_search_budget(ctx(tool="Market Size Lookup", category="x")) is None


def test_domain_allowlist(monkeypatch):
    monkeypatch.setenv("LAUNCHPAD_ALLOWED_DOMAINS", "example.com")
    assert hooks.enforce_domain_allowlist(ctx(tool="Read", url="https://www.example.com/a")) is None
    assert hooks.enforce_domain_allowlist(ctx(tool="Read", url="https://evil.test/a")) is False


def test_pii_redaction():
    c = ctx()
    c.tool_result = "Contact jane.doe@mail.com or 555-123-4567 for details"
    cleaned = hooks.redact_pii_in_results(c)
    assert "jane.doe" not in cleaned and "555-123" not in cleaned
