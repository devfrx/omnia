"""Tests for the /settings/ REST endpoints."""

from __future__ import annotations

import pytest

_URL = "/api/settings/tool-confirmations"


@pytest.mark.asyncio
class TestToolConfirmations:
    """Tests for PUT / GET /api/settings/tool-confirmations."""

    async def test_get_default_returns_true(self, client):
        resp = await client.get(_URL)
        assert resp.status_code == 200
        assert resp.json()["confirmations_enabled"] is True

    async def test_put_disable(self, client):
        resp = await client.put(_URL, json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["confirmations_enabled"] is False

    async def test_get_after_disable(self, client):
        await client.put(_URL, json={"enabled": False})
        resp = await client.get(_URL)
        assert resp.status_code == 200
        assert resp.json()["confirmations_enabled"] is False

    async def test_put_reenable(self, client):
        await client.put(_URL, json={"enabled": False})
        resp = await client.put(_URL, json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["confirmations_enabled"] is True

    async def test_put_invalid_body_returns_422(self, client):
        resp = await client.put(_URL, json={"enabled": "nope"})
        assert resp.status_code == 422

    async def test_put_missing_field_returns_422(self, client):
        resp = await client.put(_URL, json={})
        assert resp.status_code == 422
