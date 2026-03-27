import asyncio, sys
sys.path.insert(0, '.')
from backend.core.config import load_config
from backend.core.context import create_context
from backend.core.plugin_manager import PluginManager
from backend.core.tool_registry import ToolRegistry

async def test():
    cfg = load_config()
    ctx = create_context(cfg)
    pm = PluginManager(ctx)
    await pm.startup()
    tr = ToolRegistry(pm)
    await tr.refresh()
    tools = sorted(tr._tools.keys())
    ws = [t for t in tools if 'search' in t.lower() or 'web' in t.lower()]
    print('web-related:', ws)
    print('total:', len(tools))
    print('all tools:', tools)

asyncio.run(test())
