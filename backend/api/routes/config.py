"""O.M.N.I.A. — Configuration endpoints (read/update runtime config)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from backend.api.routes.models import serialise_model
from backend.core.config import KNOWN_MODELS, DEFAULT_MODEL
from backend.core.context import AppContext

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.context


@router.get("/config/models")
async def list_models(request: Request) -> list[dict[str, Any]]:
    """Fetch locally available models and return enriched metadata.

    Uses the LM Studio v1 API as primary source, falling back to
    OpenAI-compatible ``/v1/models`` or Ollama ``/api/tags``.
    """
    ctx = _ctx(request)
    active_model = ctx.config.llm.model

    # -- Primary: LM Studio v1 API ------------------------------------------
    mgr = ctx.lmstudio_manager
    if mgr is not None:
        try:
            data = await mgr.list_models()
            return _models_from_v1(data, active_model)
        except Exception:
            logger.debug("v1 API unavailable, falling back to legacy")

    # -- Fallback: legacy OpenAI-compat / Ollama ----------------------------
    return await _models_legacy(ctx)


def _models_from_v1(
    data: dict, active_model: str,
) -> list[dict[str, Any]]:
    """Map LM Studio v1 response to the frontend-expected shape."""
    return [
        serialise_model(m, active_model)
        for m in data.get("models", [])
    ]


async def _models_legacy(ctx: AppContext) -> list[dict[str, Any]]:
    """Fetch models via OpenAI-compatible or Ollama endpoint."""
    active_model = ctx.config.llm.model
    base_url = ctx.config.llm.base_url
    is_ollama = ":11434" in base_url

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if is_ollama:
                resp = await client.get(f"{base_url}/api/tags")
                resp.raise_for_status()
                raw_models = resp.json().get("models", [])
            else:
                resp = await client.get(f"{base_url}/v1/models")
                resp.raise_for_status()
                raw_models = resp.json().get("data", [])
    except Exception:
        logger.debug("Failed to fetch models from {}", base_url)
        return []

    models: list[dict[str, Any]] = []
    for m in raw_models:
        name = m.get("id", "") or m.get("name", "")
        known = KNOWN_MODELS.get(name, {})
        models.append({
            "name": name,
            "display_name": name,
            "size": m.get("size", 0),
            "modified_at": m.get("modified_at", m.get("created", "")),
            "is_active": name == active_model,
            "loaded": True,
            "loaded_instances": [],
            "architecture": None,
            "quantization": None,
            "params_string": None,
            "format": None,
            "max_context_length": 0,
            "capabilities": {
                "vision": known.get("vision", False),
                "thinking": known.get("thinking", False),
                "trained_for_tool_use": False,
            },
        })
    return models


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Return the current server configuration as JSON."""
    ctx = _ctx(request)
    cfg = ctx.config
    return {
        "llm": {
            "provider": cfg.llm.provider,
            "base_url": cfg.llm.base_url,
            "model": cfg.llm.model,
            "temperature": cfg.llm.temperature,
            "max_tokens": cfg.llm.max_tokens,
            "supports_thinking": cfg.llm.supports_thinking,
            "supports_vision": cfg.llm.supports_vision,
        },
        "stt": {
            "engine": cfg.stt.engine,
            "model": cfg.stt.model,
            "language": cfg.stt.language,
            "device": cfg.stt.device,
        },
        "tts": {
            "engine": cfg.tts.engine,
            "voice": cfg.tts.voice,
            "sample_rate": cfg.tts.sample_rate,
        },
        "ui": {
            "theme": cfg.ui.theme,
            "language": cfg.ui.language,
        },
    }


@router.put("/config")
async def update_config(request: Request) -> dict[str, Any]:
    """Update configuration values at runtime.

    Body: a partial config dict with only the keys to change.

    Note: Currently a stub — changes are accepted but NOT persisted to
    disk.  Full persistence is planned for a future phase.
    """
    ctx = _ctx(request)
    body = await request.json()

    cfg = ctx.config

    # Apply supported runtime overrides.
    if "llm" in body:
        llm_updates = body["llm"]
        if "model" in llm_updates:
            new_model = str(llm_updates["model"])

            # Load the model on LM Studio BEFORE mutating config so
            # the active-model state stays consistent on failure.
            mgr = ctx.lmstudio_manager
            if mgr is not None:
                if mgr.is_busy:
                    raise HTTPException(
                        409,
                        "Another model operation is already in progress",
                    )

                # Check if model is already loaded — skip redundant load
                models_data: dict | None = None
                try:
                    models_data = await mgr.list_models()
                    already_loaded = any(
                        m.get("key") == new_model
                        and m.get("loaded_instances")
                        for m in models_data.get("models", [])
                    )
                except Exception as exc:
                    logger.debug(
                        "Could not check loaded models: {}", exc,
                    )
                    already_loaded = False

                if not already_loaded:
                    try:
                        await mgr.load_model(new_model)
                        logger.info(
                            "Loaded model '{}' on LM Studio",
                            new_model,
                        )
                    except RuntimeError as exc:
                        raise HTTPException(409, str(exc))
                    except Exception as exc:
                        raise HTTPException(
                            503,
                            f"Failed to load model '{new_model}': {exc}",
                        )
                else:
                    logger.info(
                        "Model '{}' already loaded, skipping load",
                        new_model,
                    )

            object.__setattr__(cfg.llm, "model", new_model)
            caps = KNOWN_MODELS.get(
                new_model, {"vision": False, "thinking": False},
            )
            if mgr is not None:
                # Reuse models_data from loaded-check; re-query
                # only if the model was just loaded (data may be stale).
                if not already_loaded or models_data is None:
                    try:
                        models_data = await mgr.list_models()
                    except Exception as exc:
                        logger.debug(
                            "Could not query models for '{}': {}",
                            new_model, exc,
                        )
                        models_data = None
                if models_data is not None:
                    for m_info in models_data.get("models", []):
                        if m_info.get("key") == new_model:
                            live_caps = m_info.get(
                                "capabilities", {},
                            )
                            caps = {
                                "vision": live_caps.get(
                                    "vision",
                                    caps.get("vision", False),
                                ),
                                "thinking": live_caps.get(
                                    "thinking",
                                    caps.get("thinking", False),
                                ),
                            }
                            break
            object.__setattr__(
                cfg.llm, "supports_vision",
                caps.get("vision", False),
            )
            object.__setattr__(
                cfg.llm, "supports_thinking",
                caps.get("thinking", False),
            )
        if "temperature" in llm_updates:
            object.__setattr__(cfg.llm, "temperature", float(llm_updates["temperature"]))
        if "max_tokens" in llm_updates:
            object.__setattr__(cfg.llm, "max_tokens", int(llm_updates["max_tokens"]))

    if "ui" in body:
        ui_updates = body["ui"]
        if "theme" in ui_updates:
            object.__setattr__(cfg.ui, "theme", ui_updates["theme"])
        if "language" in ui_updates:
            object.__setattr__(cfg.ui, "language", ui_updates["language"])

    # Return the full config after applying changes.
    return await get_config(request)
