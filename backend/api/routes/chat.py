"""O.M.N.I.A. — Chat endpoints (WebSocket streaming + REST history)."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from loguru import logger
from sqlalchemy import func as sa_func
from sqlmodel import select

from backend.core.config import PROJECT_ROOT
from backend.core.context import AppContext
from backend.db.models import Attachment, Conversation, Message
from backend.services.llm_service import LLMService

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ctx(ws_or_request: Any) -> AppContext:
    """Extract the ``AppContext`` from the ASGI app state."""
    return ws_or_request.app.state.context


# ---------------------------------------------------------------------------
# WebSocket — streaming chat
# ---------------------------------------------------------------------------


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """Accept a WebSocket, stream LLM responses token-by-token.

    Incoming JSON::

        {"content": "user message", "conversation_id": "optional-uuid"}

    Outgoing JSON (one per frame)::

        {"type": "token", "content": "..."} | {"type": "done",
         "conversation_id": "...", "message_id": "..."}
    """
    await websocket.accept()
    ctx = _ctx(websocket)
    llm: LLMService = ctx.llm_service
    session_factory = ctx.db

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "content": "Invalid JSON"}
                )
                continue

            user_content: str = data.get("content", "").strip()
            if not user_content:
                await websocket.send_json(
                    {"type": "error", "content": "Empty message"}
                )
                continue

            conv_id_raw: str | None = data.get("conversation_id")
            attachment_ids: list[str] = data.get("attachments", [])

            async with session_factory() as session:
                # --- resolve or create conversation -----------------------
                if conv_id_raw:
                    conv_id = uuid.UUID(conv_id_raw)
                    conv = await session.get(Conversation, conv_id)
                    if conv is None:
                        conv = Conversation(id=conv_id)
                        session.add(conv)
                        await session.flush()
                else:
                    conv = Conversation()
                    session.add(conv)
                    await session.flush()
                    conv_id = conv.id

                # --- save user message ------------------------------------
                user_msg = Message(
                    conversation_id=conv_id,
                    role="user",
                    content=user_content,
                )
                session.add(user_msg)
                await session.flush()

                # --- link uploaded attachments to the user message --------
                attachment_info: list[dict[str, str]] = []
                for att_id_str in attachment_ids:
                    try:
                        att_id = uuid.UUID(att_id_str)
                    except ValueError:
                        logger.warning("Invalid attachment id: {}", att_id_str)
                        continue
                    att = await session.get(Attachment, att_id)
                    if att is None:
                        logger.warning("Attachment {} not found", att_id_str)
                        continue
                    att.message_id = user_msg.id
                    attachment_info.append(
                        {
                            "file_path": str(PROJECT_ROOT / att.file_path),
                            "content_type": att.content_type,
                        }
                    )
                if attachment_info:
                    await session.flush()

                # --- fetch history for context ----------------------------
                stmt = (
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.created_at)
                )
                results = await session.exec(stmt)
                history: list[dict[str, Any]] = [
                    {"role": m.role, "content": m.content}
                    for m in results.all()
                ]

                # --- call LLM (streaming) ---------------------------------
                messages = llm.build_messages(
                    user_content,
                    history=history[:-1],  # history already has user msg
                    attachments=attachment_info or None,
                )

                full_content = ""
                thinking_content = ""
                try:
                    async for event in llm.chat(messages):
                        if event["type"] == "token":
                            full_content += event["content"]
                            await websocket.send_json(event)
                        elif event["type"] == "thinking":
                            thinking_content += event["content"]
                            await websocket.send_json(event)
                        elif event["type"] == "tool_call":
                            await websocket.send_json(event)
                        elif event["type"] == "done":
                            pass  # handled below
                except Exception:
                    logger.exception("LLM streaming error")
                    await websocket.send_json(
                        {"type": "error", "content": "LLM error"}
                    )
                    await session.rollback()
                    continue

                # --- save assistant message --------------------------------
                try:
                    asst_msg = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=full_content,
                        thinking_content=thinking_content or None,
                    )
                    session.add(asst_msg)

                    # --- update conversation timestamp -------------------------
                    conv.updated_at = _utcnow()
                    if conv.title is None and full_content:
                        conv.title = user_content[:100]

                    await session.commit()
                except Exception:
                    logger.exception("DB commit error after streaming")
                    await session.rollback()
                    # Generate a fallback message id so the client can finalise.
                    asst_msg_id = uuid.uuid4()
                    await websocket.send_json(
                        {"type": "error", "content": "Failed to save response"}
                    )
                    continue

                await websocket.send_json(
                    {
                        "type": "done",
                        "conversation_id": str(conv_id),
                        "message_id": str(asst_msg.id),
                    }
                )

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket unexpected error")


# ---------------------------------------------------------------------------
# REST — conversation history
# ---------------------------------------------------------------------------


@router.get("/chat/conversations")
async def list_conversations(request: Request) -> list[dict[str, Any]]:
    """List all conversations ordered by most recently updated."""
    ctx = _ctx(request)
    async with ctx.db() as session:
        stmt = (
            select(Conversation)
            .order_by(Conversation.updated_at.desc())  # type: ignore[union-attr]
        )
        results = await session.exec(stmt)
        conversations = results.all()

        summaries: list[dict[str, Any]] = []
        for conv in conversations:
            count_stmt = (
                select(sa_func.count())
                .select_from(Message)
                .where(Message.conversation_id == conv.id)
            )
            count_result = await session.exec(count_stmt)
            msg_count: int = count_result.one()

            summaries.append(
                {
                    "id": str(conv.id),
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": msg_count,
                }
            )

        return summaries


@router.get("/chat/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, request: Request
) -> dict[str, Any]:
    """Get a single conversation with all its messages."""
    ctx = _ctx(request)
    async with ctx.db() as session:
        conv = await session.get(Conversation, conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        results = await session.exec(msg_stmt)
        messages = results.all()

        # Pre-fetch attachments for all messages in one query.
        msg_ids = [m.id for m in messages]
        att_map: dict[uuid.UUID, list[dict[str, str]]] = {}
        if msg_ids:
            att_stmt = select(Attachment).where(
                Attachment.message_id.in_(msg_ids)  # type: ignore[union-attr]
            )
            att_results = await session.exec(att_stmt)
            for att in att_results.all():
                att_map.setdefault(att.message_id, []).append(
                    {
                        "file_id": str(att.id),
                        "url": f"/uploads/{att.file_path.split('data/uploads/', 1)[-1]}"
                        if "data/uploads/" in att.file_path
                        else f"/uploads/{att.file_path}",
                        "filename": att.filename,
                        "content_type": att.content_type,
                    }
                )

        return {
            "id": str(conv.id),
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "thinking_content": m.thinking_content,
                    "tool_calls": m.tool_calls,
                    "tool_call_id": m.tool_call_id,
                    "created_at": m.created_at.isoformat(),
                    "attachments": att_map.get(m.id, []) or None,
                }
                for m in messages
            ],
        }


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID, request: Request
) -> dict[str, str]:
    """Delete a conversation and all its messages."""
    ctx = _ctx(request)
    async with ctx.db() as session:
        conv = await session.get(Conversation, conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Delete messages first.
        msg_stmt = select(Message).where(
            Message.conversation_id == conversation_id
        )
        results = await session.exec(msg_stmt)
        msg_list = results.all()

        # Delete attachment DB records for those messages.
        msg_ids = [m.id for m in msg_list]
        if msg_ids:
            att_stmt = select(Attachment).where(
                Attachment.message_id.in_(msg_ids)  # type: ignore[union-attr]
            )
            att_results = await session.exec(att_stmt)
            for att in att_results.all():
                await session.delete(att)

        for msg in msg_list:
            await session.delete(msg)

        await session.delete(conv)
        await session.commit()

        # Clean up uploaded files for this conversation.
        upload_dir = PROJECT_ROOT / "data" / "uploads" / str(conversation_id)
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
            logger.debug("Removed upload dir {}", upload_dir)

        return {"status": "deleted"}


@router.post("/chat/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    """Update the title of a conversation.

    Body: ``{"title": "new title"}``
    """
    ctx = _ctx(request)
    body = await request.json()
    new_title: str = body.get("title", "")

    async with ctx.db() as session:
        conv = await session.get(Conversation, conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conv.title = new_title
        conv.updated_at = _utcnow()
        await session.commit()

        return {
            "id": str(conv.id),
            "title": conv.title,
            "updated_at": conv.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# REST — file upload for vision models
# ---------------------------------------------------------------------------

# Allowed MIME types for image uploads.
_ALLOWED_IMAGE_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


@router.post("/chat/upload")
async def upload_image(
    request: Request,
    conversation_id: str = Form(..., description="Target conversation UUID"),
    file: UploadFile = File(..., description="Image file (jpg/png/gif/webp)"),
) -> dict[str, Any]:
    """Upload an image for use with vision-capable models.

    Saves the file to ``data/uploads/{conversation_id}/`` and creates a
    pending :class:`Attachment` record (``message_id`` is set later when the
    WebSocket message referencing this file is sent).

    Returns:
        A dict with ``file_id``, ``url``, ``filename``, and ``content_type``.

    Raises:
        HTTPException 400: If the file type is not an allowed image format.
    """
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {file.content_type}. "
                f"Allowed: {', '.join(sorted(_ALLOWED_IMAGE_TYPES))}"
            ),
        )

    file_id = uuid.uuid4()
    ext = Path(file.filename).suffix.lstrip(".") if file.filename else "bin"
    relative_path = f"data/uploads/{conversation_id}/{file_id}.{ext}"
    abs_path = PROJECT_ROOT / relative_path

    # Ensure the upload directory exists.
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    abs_path.write_bytes(content)

    # Persist an attachment record (message_id linked later via WS handler).
    ctx = _ctx(request)
    async with ctx.db() as session:
        attachment = Attachment(
            id=file_id,
            filename=file.filename or f"{file_id}.{ext}",
            content_type=file.content_type or "application/octet-stream",
            file_path=relative_path,
        )
        session.add(attachment)
        await session.commit()

    logger.info(
        "Uploaded {} ({}) for conversation {}",
        file.filename,
        file.content_type,
        conversation_id,
    )

    return {
        "file_id": str(file_id),
        "url": f"/uploads/{conversation_id}/{file_id}.{ext}",
        "filename": file.filename,
        "content_type": file.content_type,
    }
