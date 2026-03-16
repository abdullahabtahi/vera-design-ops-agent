"""
ADK agents package.

ADK's `adk web` command discovers root_agent from this module.
"""

from agents.orchestrator_agent import root_agent  # noqa: F401

__all__ = ["root_agent"]
