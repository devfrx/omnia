"""Tests for backend.plugins.cad_generator.plugin — CadGeneratorPlugin."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.config import TrellisServiceConfig, load_config
from backend.core.context import AppContext
from backend.core.event_bus import EventBus
from backend.core.plugin_models import ConnectionStatus, ExecutionContext, ToolResult
from backend.plugins.cad_generator.client import GenerationResult
from backend.plugins.cad_generator.plugin import CadGeneratorPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_ctx(execution_id: str = "abcd1234-0000-0000-0000-000000000000") -> ExecutionContext:
    return ExecutionContext(
        session_id="test-session",
        conversation_id="test-conv",
        execution_id=execution_id,
    )


def _make_trellis_config(tmp_path: Path, **overrides) -> TrellisServiceConfig:
    defaults = {
        "enabled": True,
        "service_url": "http://localhost:8090",
        "request_timeout_s": 10,
        "max_model_size_mb": 100,
        "model_output_dir": str(tmp_path / "3d_models"),
        "auto_vram_swap": True,
        "trellis_model": "TRELLIS-text-large",
        "seed": 42,
    }
    defaults.update(overrides)
    return TrellisServiceConfig(**defaults)


def _make_app_context(tmp_path: Path, **config_overrides) -> AppContext:
    """Build a minimal AppContext with mocked services."""
    config = load_config()
    trellis_cfg = _make_trellis_config(tmp_path, **config_overrides)
    # Override trellis config on the loaded config
    object.__setattr__(config, "trellis", trellis_cfg)
    object.__setattr__(config, "project_root", str(tmp_path))

    lmstudio = AsyncMock()
    lmstudio.list_models = AsyncMock(return_value={
        "models": [{
            "key": "test-model",
            "type": "llm",
            "loaded_instances": ["inst-001"],
        }],
    })
    lmstudio.unload_model = AsyncMock(return_value={})
    lmstudio.load_model = AsyncMock(return_value={})

    return AppContext(
        config=config,
        event_bus=EventBus(),
        lmstudio_manager=lmstudio,
    )


def _mock_client() -> AsyncMock:
    """Create a mock TrellisClient with default successful responses."""
    mock = AsyncMock()
    mock.health_check = AsyncMock(return_value=True)
    mock.get_status = AsyncMock(return_value={
        "status": "ok",
        "model_name": "TRELLIS-text-large",
        "model_loaded": True,
    })
    mock.request_model = AsyncMock(return_value=True)
    mock.generate_from_text = AsyncMock(return_value=GenerationResult(
        model_name="test_cube",
        format="glb",
        size_bytes=2048,
        file_path="/outputs/test_cube.glb",
    ))
    mock.download_model = AsyncMock(return_value=b"glTF" + b"\x00" * 100)
    mock.unload_model = AsyncMock()
    mock.close = AsyncMock()
    return mock


# ===========================================================================
# 1. Plugin lifecycle
# ===========================================================================


class TestPluginLifecycle:
    """CadGeneratorPlugin init, cleanup, connection status."""

    def test_plugin_class_attributes(self) -> None:
        plugin = CadGeneratorPlugin()
        assert plugin.plugin_name == "cad_generator"
        assert plugin.plugin_version == "1.0.0"
        assert plugin.plugin_priority == 20

    @pytest.mark.asyncio
    async def test_initialize_reachable(self, tmp_path: Path) -> None:
        """When TRELLIS is reachable, plugin initializes successfully."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        assert plugin.is_initialized
        mock_instance.health_check.assert_awaited_once()
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_initialize_unreachable_no_crash(self, tmp_path: Path) -> None:
        """When TRELLIS is unreachable, plugin loads without crashing."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            mock_instance.health_check = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        assert plugin.is_initialized
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_closes_client(self, tmp_path: Path) -> None:
        """cleanup() must call client.close()."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        await plugin.cleanup()
        mock_instance.close.assert_awaited_once()


# ===========================================================================
# 2. Tool definition
# ===========================================================================


class TestToolDefinition:
    """get_tools() returns correct ToolDefinition for cad_generate."""

    def test_cad_generate_tool_definition(self) -> None:
        plugin = CadGeneratorPlugin()
        tools = plugin.get_tools()

        assert len(tools) >= 1
        cad_tool = next((t for t in tools if t.name == "cad_generate"), None)
        assert cad_tool is not None
        assert cad_tool.timeout_ms == 630_000  # (600 + 30) * 1000
        assert cad_tool.risk_level == "safe"
        assert "description" in cad_tool.parameters.get("properties", {})


# ===========================================================================
# 3. Tool execution — cad_generate
# ===========================================================================


class TestCadGenerate:
    """execute_tool('cad_generate', ...) with mocked TrellisClient."""

    @pytest.mark.asyncio
    async def test_cad_generate_success(self, tmp_path: Path) -> None:
        """Successful generation → ToolResult with CAD model JSON payload."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=False)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        result = await plugin.execute_tool(
            "cad_generate",
            {"description": "a red cube", "model_name": "test_cube"},
            _make_exec_ctx(),
        )

        assert result.success is True
        assert result.content_type == "application/json"
        payload = result.content
        assert payload["model_name"] == "test_cube"
        assert payload["export_url"] == "/api/cad/models/test_cube"
        assert payload["format"] == "glb"
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_cad_generate_microservice_offline(self, tmp_path: Path) -> None:
        """health_check False during execution → error ToolResult."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=False)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        # Now make health check fail
        mock_instance.health_check = AsyncMock(return_value=False)

        result = await plugin.execute_tool(
            "cad_generate",
            {"description": "a blue sphere"},
            _make_exec_ctx(),
        )

        assert result.success is False
        assert "not reachable" in (result.error_message or result.content or "")
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_cad_generate_generation_error(self, tmp_path: Path) -> None:
        """Generation raises exception → error ToolResult."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=False)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            mock_instance.generate_from_text = AsyncMock(
                side_effect=Exception("GPU OOM"),
            )
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        result = await plugin.execute_tool(
            "cad_generate",
            {"description": "something complex"},
            _make_exec_ctx(),
        )

        assert result.success is False
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_cad_generate_auto_name(self, tmp_path: Path) -> None:
        """No model_name → name generated from description."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=False)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_gen = GenerationResult(
                model_name="a_simple_box",
                format="glb",
                size_bytes=512,
                file_path="/outputs/a_simple_box.glb",
            )
            mock_instance = _mock_client()
            mock_instance.generate_from_text = AsyncMock(return_value=mock_gen)
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        result = await plugin.execute_tool(
            "cad_generate",
            {"description": "a simple box"},
            _make_exec_ctx(execution_id="abcd1234-0000-0000-0000-000000000000"),
        )

        assert result.success is True
        payload = result.content
        # Auto-name is derived from the description, not execution_id
        assert payload["model_name"] == "a_simple_box"
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_cad_generate_sanitizes_name(self, tmp_path: Path) -> None:
        """model_name with invalid chars → sanitized (slashes/dashes to underscores)."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=False)

        sanitized_gen = GenerationResult(
            model_name="test_model_v2",
            format="glb",
            size_bytes=512,
            file_path="/outputs/test_model_v2.glb",
        )
        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            mock_instance.generate_from_text = AsyncMock(return_value=sanitized_gen)
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        result = await plugin.execute_tool(
            "cad_generate",
            {"description": "versioned model", "model_name": "test-model/v2"},
            _make_exec_ctx(),
        )

        assert result.success is True
        payload = result.content
        # Slashes and dashes replaced with underscores
        assert "/" not in payload["model_name"]
        assert "-" not in payload["model_name"]
        await plugin.cleanup()


# ===========================================================================
# 4. VRAM swap orchestration
# ===========================================================================


class TestVRAMSwap:
    """VRAM unload/reload LLM around TRELLIS generation."""

    @pytest.mark.asyncio
    async def test_vram_swap_unload_reload(self, tmp_path: Path) -> None:
        """auto_vram_swap=True → LLM unloaded before, reloaded after generation."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=True)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        # Make list_models return loaded model for reload check
        lmstudio = ctx.lmstudio_manager
        lmstudio.list_models = AsyncMock(return_value={
            "models": [{
                "key": "test-model",
                "type": "llm",
                "loaded_instances": ["inst-001"],
            }],
        })

        result = await plugin.execute_tool(
            "cad_generate",
            {"description": "a vase"},
            _make_exec_ctx(),
        )

        assert result.success is True
        # Verify LLM was unloaded and reloaded
        lmstudio.unload_model.assert_awaited()
        lmstudio.load_model.assert_awaited()
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_vram_swap_disabled(self, tmp_path: Path) -> None:
        """auto_vram_swap=False → no unload/load calls on LM Studio."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=False)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        await plugin.execute_tool(
            "cad_generate",
            {"description": "a simple cube"},
            _make_exec_ctx(),
        )

        lmstudio = ctx.lmstudio_manager
        lmstudio.unload_model.assert_not_awaited()
        lmstudio.load_model.assert_not_awaited()
        await plugin.cleanup()

    @pytest.mark.asyncio
    async def test_vram_swap_reload_after_trellis_failure(self, tmp_path: Path) -> None:
        """TRELLIS generation fails → LLM is still reloaded (safety guarantee)."""
        plugin = CadGeneratorPlugin()
        ctx = _make_app_context(tmp_path, auto_vram_swap=True)

        with patch("backend.plugins.cad_generator.plugin.TrellisClient") as MockClient:
            mock_instance = _mock_client()
            mock_instance.generate_from_text = AsyncMock(
                side_effect=Exception("TRELLIS crashed"),
            )
            MockClient.return_value = mock_instance
            await plugin.initialize(ctx)

        lmstudio = ctx.lmstudio_manager
        lmstudio.list_models = AsyncMock(return_value={
            "models": [{
                "key": "test-model",
                "type": "llm",
                "loaded_instances": ["inst-001"],
            }],
        })

        result = await plugin.execute_tool(
            "cad_generate",
            {"description": "crash test"},
            _make_exec_ctx(),
        )

        assert result.success is False
        # LLM must be reloaded even after TRELLIS failure
        lmstudio.load_model.assert_awaited()
        await plugin.cleanup()
