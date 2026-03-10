"""O.M.N.I.A. — SQLModel database models."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    """Generate a new UUID4."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class Conversation(SQLModel, table=True):
    """A single conversation thread."""

    __tablename__ = "conversations"

    id: uuid.UUID = Field(
        default_factory=_new_uuid,
        primary_key=True,
    )
    title: Optional[str] = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # -- relationships ------------------------------------------------------
    messages: list["Message"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class Message(SQLModel, table=True):
    """A single message inside a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_message_role",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=_new_uuid,
        primary_key=True,
    )
    conversation_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    role: str = Field(
        max_length=16,
        description='One of "user", "assistant", "system", or "tool".',
    )
    content: str = Field(default="")
    tool_calls: Optional[Any] = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    tool_call_id: Optional[str] = Field(default=None, max_length=64)
    thinking_content: Optional[str] = Field(
        default=None,
        description="Reasoning/thinking tokens from models that support it.",
    )
    created_at: datetime = Field(default_factory=_utcnow)

    # -- relationships ------------------------------------------------------
    conversation: Optional[Conversation] = Relationship(
        back_populates="messages"
    )
    attachments: list["Attachment"] = Relationship(
        back_populates="message",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


# ---------------------------------------------------------------------------
# Attachment
# ---------------------------------------------------------------------------


class Attachment(SQLModel, table=True):
    """A file attached to a message (e.g. images for vision models)."""

    __tablename__ = "attachments"

    id: uuid.UUID = Field(
        default_factory=_new_uuid,
        primary_key=True,
    )
    message_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        description="Linked after the user message is persisted.",
    )
    filename: str = Field(max_length=256)
    content_type: str = Field(max_length=128)
    file_path: str = Field(
        description="Relative path from the project root.",
    )
    created_at: datetime = Field(default_factory=_utcnow)

    # -- relationships ------------------------------------------------------
    message: Optional[Message] = Relationship(back_populates="attachments")


# ---------------------------------------------------------------------------
# Tool Confirmation Audit (Phase 5)
# ---------------------------------------------------------------------------


class ToolConfirmationAudit(SQLModel, table=True):
    """Audit log for tool confirmation decisions.

    Records every user approval/rejection for tools requiring confirmation,
    enabling post-hoc security review and compliance tracking.
    """

    __tablename__ = "tool_confirmation_audit"
    __table_args__ = (
        sa.Index("ix_audit_conversation_id", "conversation_id"),
        sa.Index("ix_audit_tool_name", "tool_name"),
        sa.Index("ix_audit_created_at", "created_at"),
        sa.CheckConstraint(
            "risk_level IN ('safe', 'medium', 'dangerous', 'forbidden')",
            name="ck_audit_risk_level",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=_new_uuid,
        primary_key=True,
    )
    conversation_id: uuid.UUID = Field(
        description="Conversation in which the tool was invoked.",
    )
    execution_id: str = Field(
        max_length=64,
        description="Unique execution ID for correlation with tool loop.",
    )
    tool_name: str = Field(
        max_length=128,
        description="Namespaced tool name (e.g. pc_automation_take_screenshot).",
    )
    args_json: str = Field(
        default="{}",
        description="JSON-serialized tool arguments.",
    )
    risk_level: str = Field(
        max_length=16,
        description="Risk level at time of invocation (safe/medium/dangerous/forbidden).",
    )
    user_approved: bool = Field(
        description="Whether the user approved the execution.",
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Reason for rejection: 'user_rejected', 'timeout', 'cancelled'.",
    )
    thinking_content: Optional[str] = Field(
        default=None,
        description="LLM reasoning/thinking content at time of tool invocation.",
    )
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# User Preferences
# ---------------------------------------------------------------------------


class UserPreference(SQLModel, table=True):
    """Persisted user preference (survives across restarts).

    Stores independent settings as key-value pairs, where the key
    uses dot notation (e.g. 'tts.engine', 'ui.theme').
    """

    __tablename__ = "user_preferences"

    key: str = Field(primary_key=True, max_length=128)
    value: str = Field(default="")  # JSON-encoded value
    updated_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Agent Task (Phase 10)
# ---------------------------------------------------------------------------


class AgentTask(SQLModel, table=True):
    """A scheduled or one-shot background task executed autonomously by the agent."""

    __tablename__ = "agent_tasks"
    __table_args__ = (
        sa.CheckConstraint(
            "trigger_type IN ('once_at', 'interval', 'manual')",
            name="ck_task_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_task_status",
        ),
        sa.Index("ix_agent_task_status_next_run", "status", "next_run_at"),
        sa.Index("ix_agent_task_created_at", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=_new_uuid, primary_key=True)

    prompt: str = Field(
        description="Natural language instruction for the agent to execute.",
    )

    trigger_type: str = Field(
        description="once_at | interval | manual",
    )

    # -- Trigger scheduling ------------------------------------------------
    run_at: datetime | None = Field(
        default=None,
        description="For trigger_type='once_at': absolute UTC datetime to run.",
    )
    interval_seconds: int | None = Field(
        default=None,
        description="For trigger_type='interval': repeat every N seconds.",
    )
    next_run_at: datetime | None = Field(
        default=None,
        description="UTC datetime of the next scheduled execution. NULL = not yet scheduled.",
    )
    max_runs: int | None = Field(
        default=None,
        description="Max executions for interval tasks. NULL = unlimited.",
    )

    # -- Execution state ---------------------------------------------------
    status: str = Field(default="pending")
    run_count: int = Field(default=0)
    last_run_at: datetime | None = None

    # -- Result ------------------------------------------------------------
    result_summary: str | None = Field(
        default=None,
        description="LLM-generated summary of what the task accomplished.",
    )
    error_message: str | None = None

    # -- Context -----------------------------------------------------------
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Optional: conversation from which this task was created.",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

