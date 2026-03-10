"""O.M.N.I.A. — Agent Task plugin package.

Importing this module registers :class:`AgentTaskPlugin` in the
static ``PLUGIN_REGISTRY`` so the plugin manager can discover it.
"""

from backend.core.plugin_manager import PLUGIN_REGISTRY
from backend.plugins.agent_task.plugin import AgentTaskPlugin  # noqa: F401

PLUGIN_REGISTRY["agent_task"] = AgentTaskPlugin
