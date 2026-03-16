# ADK eval discovery: loads this __init__.py as module "agent", then accesses
# agent.agent.root_agent — so we must import the agent submodule here.
# Also ensure backend/ is in sys.path so absolute imports (e.g. 'agents', 'tools')
# resolve correctly when ADK loads this module without setting up sys.path.
import os as _os
import sys as _sys

_backend_dir = _os.path.dirname(_os.path.abspath(__file__))
if _backend_dir not in _sys.path:
    _sys.path.insert(0, _backend_dir)

from . import agent  # noqa: F401
