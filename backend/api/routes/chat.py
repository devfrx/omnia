"""O.M.N.I.A. — Chat endpoints (WebSocket streaming + REST history)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy import func as sa_func
from sqlmodel import select

from backend.core.context import AppContext
from backend.db.models import Conversation, Message
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

            async with session_factory() as session:
                # --- resolve or create conversation -----------------------
                if conv_id_raw:
                    conv_id = uuid.UUID(conv_id_raw)
                    conv = await session.get(Conversation, conv_id)
                    if conv is None:
                        conv = Conversation(id=conv_id)
                        session.add(conv)
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
                    user_content, history=history[:-1]  # history already has user msg
                )

                full_content = ""
                try:
                    async for event in llm.chat(messages):
                        if event["type"] == "token":
                            full_content += event["content"]
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
                asst_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_content,
                )
                session.add(asst_msg)

                # --- update conversation timestamp -------------------------
                conv.updated_at = _utcnow()
                if conv.title is None and full_content:
                    conv.title = user_content[:100]

                await session.commit()

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
                    "tool_calls": m.tool_calls,
                    "tool_call_id": m.tool_call_id,
                    "created_at": m.created_at.isoformat(),
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
        for msg in results.all():
            await session.delete(msg)

        await session.delete(conv)
        await session.commit()
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
