"""Tests for ``backend.services.conversation_file_manager.ConversationFileManager``."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db.models import Attachment, Conversation, Message
from backend.services.conversation_file_manager import ConversationFileManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_conversation(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid conversation dict."""
    now = datetime.now(timezone.utc).isoformat()
    defaults: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "title": "Test conversation",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    defaults.update(overrides)
    return defaults


def _sample_conversation_with_messages() -> dict[str, Any]:
    """Return a conversation with two messages and an attachment."""
    conv_id = str(uuid.uuid4())
    msg1_id = str(uuid.uuid4())
    msg2_id = str(uuid.uuid4())
    att_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": conv_id,
        "title": "Full conversation",
        "created_at": now,
        "updated_at": now,
        "messages": [
            {
                "id": msg1_id,
                "role": "user",
                "content": "Hello",
                "thinking_content": None,
                "tool_calls": None,
                "tool_call_id": None,
                "created_at": now,
                "attachments": None,
            },
            {
                "id": msg2_id,
                "role": "assistant",
                "content": "Hi there!",
                "thinking_content": "I should greet back",
                "tool_calls": None,
                "tool_call_id": None,
                "created_at": now,
                "attachments": [
                    {
                        "file_id": att_id,
                        "url": f"/uploads/{conv_id}/{att_id}.png",
                        "filename": "image.png",
                        "content_type": "image/png",
                        "file_path": f"data/uploads/{conv_id}/{att_id}.png",
                    }
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fm(tmp_path: Path) -> ConversationFileManager:
    """Create a ``ConversationFileManager`` backed by a temp directory."""
    return ConversationFileManager(tmp_path)


# ---------------------------------------------------------------------------
# Tests — save
# ---------------------------------------------------------------------------


class TestSave:
    """``save()`` should write atomic JSON files."""

    async def test_save_creates_json_file(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """After save, a ``{id}.json`` file must exist."""
        data = _sample_conversation()
        await fm.save(data)
        target = tmp_path / f"{data['id']}.json"
        assert target.exists()

    async def test_save_file_is_valid_json(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """The saved file must be parseable JSON matching the input."""
        data = _sample_conversation()
        await fm.save(data)
        raw = (tmp_path / f"{data['id']}.json").read_text(encoding="utf-8")
        assert json.loads(raw) == data

    async def test_save_overwrites_existing(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """A second save to the same id must overwrite the file."""
        data = _sample_conversation()
        await fm.save(data)
        data["title"] = "Updated title"
        await fm.save(data)
        raw = json.loads(
            (tmp_path / f"{data['id']}.json").read_text(encoding="utf-8")
        )
        assert raw["title"] == "Updated title"

    async def test_save_is_atomic_no_tmp_leftover(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """After a successful save, no ``.tmp`` file should remain."""
        data = _sample_conversation()
        await fm.save(data)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    async def test_save_complex_conversation(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """Conversations with messages and attachments are persisted."""
        data = _sample_conversation_with_messages()
        await fm.save(data)
        raw = json.loads(
            (tmp_path / f"{data['id']}.json").read_text(encoding="utf-8")
        )
        assert len(raw["messages"]) == 2
        assert raw["messages"][1]["attachments"] is not None


# ---------------------------------------------------------------------------
# Tests — load
# ---------------------------------------------------------------------------


class TestLoad:
    """``load()`` should round-trip saved data."""

    async def test_load_returns_saved_data(
        self, fm: ConversationFileManager,
    ) -> None:
        """load(id) must return exactly what was saved."""
        data = _sample_conversation()
        await fm.save(data)
        loaded = await fm.load(data["id"])
        assert loaded == data

    async def test_load_nonexistent_returns_none(
        self, fm: ConversationFileManager,
    ) -> None:
        """Loading a missing conversation must return ``None``."""
        result = await fm.load(str(uuid.uuid4()))
        assert result is None

    async def test_load_corrupted_json_raises(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """A corrupted JSON file causes a ``JSONDecodeError`` on load."""
        cid = str(uuid.uuid4())
        (tmp_path / f"{cid}.json").write_text("{invalid json!!!", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            await fm.load(cid)


# ---------------------------------------------------------------------------
# Tests — load_all
# ---------------------------------------------------------------------------


class TestLoadAll:
    """``load_all()`` should aggregate all valid conversation files."""

    async def test_load_all_empty_directory(
        self, fm: ConversationFileManager,
    ) -> None:
        """An empty directory yields an empty list."""
        result = await fm.load_all()
        assert result == []

    async def test_load_all_returns_all(
        self, fm: ConversationFileManager,
    ) -> None:
        """All saved conversations must appear in load_all."""
        c1 = _sample_conversation()
        c2 = _sample_conversation()
        await fm.save(c1)
        await fm.save(c2)
        results = await fm.load_all()
        ids = {r["id"] for r in results}
        assert c1["id"] in ids
        assert c2["id"] in ids

    async def test_load_all_skips_corrupted_json(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """Corrupted files are silently skipped in ``load_all``."""
        good = _sample_conversation()
        await fm.save(good)
        # Write a corrupted file.
        (tmp_path / "bad.json").write_text("NOT VALID JSON", encoding="utf-8")
        results = await fm.load_all()
        assert len(results) == 1
        assert results[0]["id"] == good["id"]

    async def test_load_all_ignores_non_json_files(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """Non-JSON files in the directory must be ignored."""
        good = _sample_conversation()
        await fm.save(good)
        (tmp_path / "readme.txt").write_text("ignore me", encoding="utf-8")
        results = await fm.load_all()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------


class TestDelete:
    """``delete()`` should remove conversation files safely."""

    async def test_delete_removes_file(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """After delete, the JSON file must no longer exist."""
        data = _sample_conversation()
        await fm.save(data)
        assert (tmp_path / f"{data['id']}.json").exists()
        await fm.delete(data["id"])
        assert not (tmp_path / f"{data['id']}.json").exists()

    async def test_delete_idempotent(
        self, fm: ConversationFileManager,
    ) -> None:
        """Deleting a non-existent conversation must not raise."""
        await fm.delete(str(uuid.uuid4()))  # no error expected

    async def test_delete_then_load_returns_none(
        self, fm: ConversationFileManager,
    ) -> None:
        """After deletion, ``load()`` must return ``None``."""
        data = _sample_conversation()
        await fm.save(data)
        await fm.delete(data["id"])
        assert await fm.load(data["id"]) is None


# ---------------------------------------------------------------------------
# Tests — rebuild_from_files
# ---------------------------------------------------------------------------


class TestRebuildFromFiles:
    """``rebuild_from_files()`` must restore the DB from JSON files."""

    async def _make_session_factory(self) -> Any:
        """Create a real in-memory DB session factory for rebuild tests."""
        from backend.db.database import create_engine_and_session, init_db

        engine, factory = create_engine_and_session("sqlite+aiosqlite://")
        await init_db(engine)
        return factory, engine

    async def test_rebuild_restores_conversation(
        self, fm: ConversationFileManager,
    ) -> None:
        """A single valid JSON file should be restored into the DB."""
        data = _sample_conversation_with_messages()
        await fm.save(data)

        factory, engine = await self._make_session_factory()
        try:
            count = await fm.rebuild_from_files(factory)
            assert count == 1

            async with factory() as session:
                conv = await session.get(Conversation, uuid.UUID(data["id"]))
                assert conv is not None
                assert conv.title == data["title"]
        finally:
            await engine.dispose()

    async def test_rebuild_skips_existing_conversation(
        self, fm: ConversationFileManager,
    ) -> None:
        """Conversations already in the DB must not be duplicated."""
        data = _sample_conversation_with_messages()
        await fm.save(data)

        factory, engine = await self._make_session_factory()
        try:
            # First rebuild.
            assert await fm.rebuild_from_files(factory) == 1
            # Second rebuild — same file, should skip.
            assert await fm.rebuild_from_files(factory) == 0
        finally:
            await engine.dispose()

    async def test_rebuild_multiple_conversations(
        self, fm: ConversationFileManager,
    ) -> None:
        """Multiple JSON files should all be restored."""
        c1 = _sample_conversation_with_messages()
        c2 = _sample_conversation_with_messages()
        await fm.save(c1)
        await fm.save(c2)

        factory, engine = await self._make_session_factory()
        try:
            count = await fm.rebuild_from_files(factory)
            assert count == 2
        finally:
            await engine.dispose()

    async def test_rebuild_skips_corrupted_file(
        self, fm: ConversationFileManager, tmp_path: Path,
    ) -> None:
        """Corrupted JSON files must not crash the rebuild."""
        good = _sample_conversation_with_messages()
        await fm.save(good)
        (tmp_path / "corrupt.json").write_text("{bad", encoding="utf-8")

        factory, engine = await self._make_session_factory()
        try:
            count = await fm.rebuild_from_files(factory)
            assert count == 1
        finally:
            await engine.dispose()

    async def test_rebuild_empty_directory(
        self, fm: ConversationFileManager,
    ) -> None:
        """An empty directory should restore zero conversations."""
        factory, engine = await self._make_session_factory()
        try:
            assert await fm.rebuild_from_files(factory) == 0
        finally:
            await engine.dispose()
