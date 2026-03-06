"""O.M.N.I.A. — LM Studio v1 REST API client for model management."""

from __future__ import annotations

import httpx
from loguru import logger


class LMStudioManager:
    """Async client for the LM Studio v1 REST API.

    Handles model listing, loading, unloading, downloading,
    and health checks against the ``/api/v1/`` endpoints.

    Args:
        base_url: LM Studio server base URL (e.g. ``http://localhost:1234``).
        api_token: Optional Bearer token for authenticated requests.
    """

    def __init__(self, base_url: str, api_token: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        headers: dict[str, str] = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        )

    # -- Models -------------------------------------------------------------

    async def list_models(self) -> dict:
        """List all models known to LM Studio.

        Returns:
            The JSON response from ``GET /api/v1/models``.
        """
        try:
            resp = await self._client.get("/api/v1/models")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("LM Studio list_models failed: {}", exc)
            raise

    async def load_model(
        self,
        model: str,
        *,
        context_length: int | None = None,
        flash_attention: bool | None = None,
        eval_batch_size: int | None = None,
        num_experts: int | None = None,
        offload_kv_cache_to_gpu: bool | None = None,
    ) -> dict:
        """Load a model into LM Studio.

        Args:
            model: The model key to load.
            context_length: Override context window size.
            flash_attention: Enable flash attention.
            eval_batch_size: Evaluation batch size.
            num_experts: Number of experts for MoE models.
            offload_kv_cache_to_gpu: Offload KV cache to GPU.

        Returns:
            The JSON response from ``POST /api/v1/models/load``.
        """
        payload: dict = {"model": model, "echo_load_config": True}
        if context_length is not None:
            payload["context_length"] = context_length
        if flash_attention is not None:
            payload["flash_attention"] = flash_attention
        if eval_batch_size is not None:
            payload["eval_batch_size"] = eval_batch_size
        if num_experts is not None:
            payload["num_experts"] = num_experts
        if offload_kv_cache_to_gpu is not None:
            payload["offload_kv_cache_to_gpu"] = offload_kv_cache_to_gpu

        try:
            resp = await self._client.post(
                "/api/v1/models/load",
                json=payload,
                timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("LM Studio load_model({}) failed: {}", model, exc)
            raise

    async def unload_model(self, instance_id: str) -> dict:
        """Unload a model from LM Studio.

        Args:
            instance_id: The instance ID of the loaded model.

        Returns:
            The JSON response from ``POST /api/v1/models/unload``.
        """
        try:
            resp = await self._client.post(
                "/api/v1/models/unload",
                json={"instance_id": instance_id},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("LM Studio unload_model({}) failed: {}", instance_id, exc)
            raise

    async def download_model(
        self,
        model: str,
        *,
        quantization: str | None = None,
    ) -> dict:
        """Start a model download.

        Args:
            model: The model identifier (e.g. ``ibm/granite-4-micro``).
            quantization: Quantization format (e.g. ``Q4_K_M``).

        Returns:
            The JSON response from ``POST /api/v1/models/download``.
        """
        payload: dict = {"model": model}
        if quantization is not None:
            payload["quantization"] = quantization
        try:
            resp = await self._client.post(
                "/api/v1/models/download",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("LM Studio download_model({}) failed: {}", model, exc)
            raise

    async def get_download_status(self, job_id: str) -> dict:
        """Get the status of a model download job.

        Args:
            job_id: The download job identifier.

        Returns:
            The JSON response from ``GET /api/v1/models/download/status/{job_id}``.
        """
        try:
            resp = await self._client.get(
                f"/api/v1/models/download/status/{job_id}",
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("LM Studio get_download_status({}) failed: {}", job_id, exc)
            raise

    # -- Health -------------------------------------------------------------

    async def check_health(self) -> bool:
        """Return ``True`` if LM Studio is reachable.

        Performs a lightweight ``GET /api/v1/models`` and returns
        ``False`` on any connection or HTTP error.
        """
        try:
            resp = await self._client.get(
                "/api/v1/models",
                timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0),
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    # -- Lifecycle ----------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
