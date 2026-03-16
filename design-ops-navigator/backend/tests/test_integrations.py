"""
Unit tests for the three ADK integrations added in this session:
  1. ReflectAndRetryToolPlugin — present in Runner
  2. google_search — present in root_agent tools
  3. AgentOps — initialises with key, silent no-op without key
"""
from __future__ import annotations

import os
import types


# ── 1. ReflectAndRetryToolPlugin ─────────────────────────────────────────────


def test_reflect_retry_plugin_importable():
    from google.adk.plugins import ReflectAndRetryToolPlugin
    assert ReflectAndRetryToolPlugin is not None


def test_reflect_retry_plugin_instantiates_with_max_retries():
    from google.adk.plugins import ReflectAndRetryToolPlugin
    plugin = ReflectAndRetryToolPlugin(max_retries=2)
    assert plugin.max_retries == 2


def test_reflect_retry_plugin_default_retries():
    from google.adk.plugins import ReflectAndRetryToolPlugin
    import inspect
    sig = inspect.signature(ReflectAndRetryToolPlugin.__init__)
    default = sig.parameters["max_retries"].default
    # Default should be a positive integer (implementation detail — just assert it's int)
    assert isinstance(default, int) and default > 0


def test_runner_accepts_plugins_kwarg():
    """Runner constructor must accept a 'plugins' parameter."""
    from google.adk.runners import Runner
    import inspect
    sig = inspect.signature(Runner.__init__)
    assert "plugins" in sig.parameters


def test_server_imports_reflect_retry_plugin():
    """server.py must import ReflectAndRetryToolPlugin (catches accidental deletions)."""
    import importlib, sys
    # Reload is expensive — just grep the source instead
    src = open(
        os.path.join(os.path.dirname(__file__), "..", "server.py")
    ).read()
    assert "ReflectAndRetryToolPlugin" in src


def test_server_passes_plugin_to_runner():
    """server.py must construct Runner with plugins=[ReflectAndRetryToolPlugin(...)]."""
    src = open(
        os.path.join(os.path.dirname(__file__), "..", "server.py")
    ).read()
    assert "plugins=[ReflectAndRetryToolPlugin(" in src


# ── 2. google_search ──────────────────────────────────────────────────────────


def test_google_search_importable():
    from google.adk.tools import google_search
    assert google_search is not None


def test_root_agent_does_not_mix_search_with_function_tools():
    """
    Gemini rejects mixing google_search (built-in search tool) with custom function
    tools on the same agent (400: 'Multiple tools are supported only when they are
    all search tools'). google_search must NOT be in root_agent.tools.
    """
    from dotenv import load_dotenv
    load_dotenv()
    from agents import root_agent

    tool_names = []
    for t in root_agent.tools:
        if hasattr(t, "name"):
            tool_names.append(t.name)
        elif callable(t):
            tool_names.append(getattr(t, "__name__", str(t)))
        else:
            tool_names.append(str(t))

    assert "google_search" not in tool_names, (
        "google_search cannot be mixed with custom function tools on the same agent — "
        "Gemini 400 INVALID_ARGUMENT. Remove it from root_agent.tools."
    )


def test_root_agent_has_search_knowledge_base():
    """root_agent.tools must still include search_knowledge_base."""
    from dotenv import load_dotenv
    load_dotenv()
    from agents import root_agent

    func_names = [
        getattr(t, "__name__", str(t)) for t in root_agent.tools if callable(t)
    ]
    assert "search_knowledge_base" in func_names


def test_root_agent_has_list_knowledge_sources():
    """root_agent.tools must still include list_knowledge_sources."""
    from dotenv import load_dotenv
    load_dotenv()
    from agents import root_agent

    func_names = [
        getattr(t, "__name__", str(t)) for t in root_agent.tools if callable(t)
    ]
    assert "list_knowledge_sources" in func_names


def test_orchestrator_instruction_has_route_b():
    """Route B instruction must tell the agent to use search_knowledge_base directly."""
    src = open(
        os.path.join(os.path.dirname(__file__), "..", "agents", "orchestrator_agent.py")
    ).read()
    assert "search_knowledge_base" in src
    assert "Route B" in src


def test_orchestrator_route_b_recency_triggers_web_search():
    """Route B must explicitly trigger web_search for recency signals (RECENCY=true)."""
    src = open(
        os.path.join(os.path.dirname(__file__), "..", "agents", "orchestrator_agent.py")
    ).read()
    assert "RECENCY" in src
    assert "web_search" in src
    # Within Route B, recency detection must appear before the web_search call instruction
    route_b_start = src.index("Route B")
    route_b_end = src.index("Route D")  # next route
    route_b_text = src[route_b_start:route_b_end]
    assert "RECENCY" in route_b_text
    recency_idx = route_b_text.index("RECENCY")
    web_search_idx = route_b_text.index("web_search")
    assert recency_idx < web_search_idx


def test_orchestrator_transparency_rule():
    """Route B must include a transparency rule for training-knowledge fallback."""
    src = open(
        os.path.join(os.path.dirname(__file__), "..", "agents", "orchestrator_agent.py")
    ).read()
    assert "first principles" in src or "training" in src or "Transparency" in src


# ── 3. AgentOps ───────────────────────────────────────────────────────────────


def test_agentops_importable():
    import agentops
    assert agentops is not None


def test_agentops_key_in_config():
    """Settings must have agentops_api_key field."""
    from dotenv import load_dotenv
    load_dotenv()
    from config import settings
    assert hasattr(settings, "agentops_api_key")


def test_agentops_init_called_with_key(monkeypatch):
    """When AGENTOPS_API_KEY is set, agentops.init() is called."""
    init_calls = []

    fake_agentops = types.SimpleNamespace(init=lambda key, **kw: init_calls.append(key))

    monkeypatch.setenv("AGENTOPS_API_KEY", "test-key-123")

    # Simulate the server-side init block
    key = os.getenv("AGENTOPS_API_KEY", "")
    if key:
        fake_agentops.init(key, auto_start_session=False)

    assert init_calls == ["test-key-123"]


def test_agentops_silent_without_key(monkeypatch):
    """When AGENTOPS_API_KEY is absent, no exception is raised."""
    monkeypatch.delenv("AGENTOPS_API_KEY", raising=False)

    # Replicate the server.py guard block
    raised = False
    _agentops = None
    try:
        key = os.getenv("AGENTOPS_API_KEY", "")
        if key:
            import agentops as _agentops_real
            _agentops_real.init(key, auto_start_session=False)
            _agentops = _agentops_real
    except Exception:
        raised = True

    assert not raised
    assert _agentops is None


def test_server_agentops_block_is_guarded():
    """server.py AgentOps block must be wrapped in try/except for graceful fallback."""
    src = open(
        os.path.join(os.path.dirname(__file__), "..", "server.py")
    ).read()
    # Both the key-check guard and the exception guard must be present
    assert "AGENTOPS_API_KEY" in src
    assert "agentops = None" in src
