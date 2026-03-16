"""
ADK eval entry point.

`adk eval .` loads this directory as a module named "agent", then looks for
`agent.agent.root_agent`. This file provides that path by re-exporting root_agent
from the agents package.
"""

from agents.orchestrator_agent import root_agent  # noqa: F401

__all__ = ["root_agent"]
