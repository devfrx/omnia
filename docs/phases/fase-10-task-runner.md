### Fase 10 — Autonomous Task Runner (Agente Proattivo)

> **Obiettivo**: trasformare AL\CE da assistente reattivo a agente proattivo capace di eseguire
> task in background — schedulati o event-driven — senza input utente in tempo reale.
> Con Fase 9 (memoria) + Fase 10 (autonomia) AL\CE diventa un agente vero.

- [x] AgentTask DB model — §10.1
- [x] TaskSchedulerConfig in config.py + default.yaml — §10.2
- [x] TaskScheduler service (asyncio loop) — §10.3
- [x] run_agent_task() headless runner — §10.4
- [x] AgentTaskPlugin (4 tool: schedule/cancel/list/get_result) — §10.5
- [x] WSConnectionManager service — §10.6
- [x] Endpoint /api/ws/events — §10.7
- [x] REST API /api/tasks — §10.8
- [x] AliceEvent TASK_* events — §10.9
- [x] System prompt updates — §10.11
- [x] Frontend types/tasks.ts + stores/tasks.ts + useEventsWebSocket.ts + TaskManager.vue — §10.12
- [x] Wiring in app.py (WSConnectionManager + TaskScheduler + EventBus bridge) — §10.3/10.6
- [x] Routes registration (events + tasks) — §10.7/10.8
- [x] Protocols (TaskSchedulerProtocol + WSConnectionManagerProtocol) + AppContext fields — §10.6
- [ ] Test suite completa — §10.15

---

#### 10.0 — Analisi Vincoli e Scelte Architetturali

**Perché NON usare APScheduler, Celery o altri task runner esterni:**
- Il progetto usa esclusivamente `asyncio` low-level (VRAMMonitor, calendar reminder loop, TimerManager)
- APScheduler introduce dipendenze pesanti, processo separato con Celery, complessità di serializzazione
- **Soluzione scelta**: `TaskScheduler` service con `asyncio.create_task(_scheduler_loop())` — identico al pattern `VRAMMonitor` già nel codebase. Zero nuove dipendenze.

**Perché NON riusare il WebSocket di chat per il push background:**
- Il WS `/api/ws/chat` è per-messaggio: aperto durante una conversazione, non persistente
- Un task che finisce alle 3:00 non ha nessun WS di chat aperto a cui pushare
- **Soluzione scelta**: endpoint `/api/ws/events` — canale push persistente separato, connesso da frontend all'avvio. Completamente separato dal flusso chat. Pattern: server emette eventi `EventBus → WSConnectionManager.broadcast()`.

**Perché NON riadattare `run_tool_loop()` per i task:**
- `run_tool_loop()` richiede `websocket: WebSocket` — non ha senso creare un WebSocket fittizio
- Farlo violerebbe il contratto della funzione e introdurrebbe coupling nascosto
- **Soluzione scelta**: `run_agent_task()` — funzione dedicata, senza WebSocket, che esegue il tool loop LLM in modo headless e salva il risultato nel DB. Chiama direttamente `llm.chat()` e `tool_registry.execute_tool()` (che sono già standalone asyncio).

**Strategia trigger (senza dependency esterna):**
- `once_at: datetime` — una tantum, run al momento specificato
- `interval_seconds: int` — ricorrente, `next_run_at = last_run_at + timedelta(seconds=interval_seconds)`
- Nessuna espressione cron per v1 (evitare `croniter` per ora)
- Il `_scheduler_loop()` sveglia ogni `poll_interval_s` (default 30s) e controlla `WHERE status='pending' AND next_run_at <= NOW()`

**Concorrenza task:**
- `max_concurrent_tasks: int = 2` — non saturare LLM con richieste parallele
- `asyncio.Semaphore(max_concurrent_tasks)` nel loop di esecuzione
- Task che supera `task_timeout_s` viene cancellato con `asyncio.wait_for`

---

#### 10.1 — AgentTask DB Model (`backend/db/models.py`)

Aggiunta pura a `models.py`, zero modifica ai modelli esistenti. Pattern: `uuid.UUID` PK, `_new_uuid()`/`_utcnow()` factories, `CheckConstraint`, indici per query frequenti.

```python
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
    """What the agent must do when this task fires."""

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
```

**Indice composito `(status, next_run_at)`**: la query del scheduler è `WHERE status='pending' AND next_run_at <= :now` — questo indice la rende O(log n).

---

#### 10.2 — TaskSchedulerConfig (`backend/core/config.py`)

```python
class TaskSchedulerConfig(BaseSettings):
    """Background task scheduler configuration."""

    model_config = SettingsConfigDict(env_prefix="ALICE_TASK_SCHEDULER__")

    enabled: bool = False
    """Abilita il TaskScheduler. False di default (opt-in)."""

    poll_interval_s: float = 30.0
    """Secondi tra ogni check DB per task da eseguire."""

    max_concurrent_tasks: int = 2
    """Task eseguibili contemporaneamente. Limita la pressione sull'LLM."""

    task_timeout_s: int = 300
    """Timeout massimo per singolo task (5 minuti). Superato: status → 'failed'."""

    max_task_prompt_chars: int = 2000
    """Lunghezza massima del prompt di un task (sicurezza)."""

    max_runs_safety_cap: int = 1000
    """Cap di sicurezza per max_runs su task interval (evita loop infiniti)."""

    result_retention_days: int = 30
    """Giorni di retention per task completati/falliti prima della pulizia."""
```

Aggiunta a `AliceConfig`:
```python
task_scheduler: TaskSchedulerConfig = Field(default_factory=TaskSchedulerConfig)
```

Config YAML (`config/default.yaml`):
```yaml
task_scheduler:
  enabled: false
  poll_interval_s: 30.0
  max_concurrent_tasks: 2
  task_timeout_s: 300

# In plugins.enabled, aggiungere (commentato per default-off):
# - agent_task  # abilitare con task_scheduler.enabled: true
```

---

#### 10.3 — TaskScheduler Service (`backend/services/task_scheduler.py`)

**Ruolo**: service core che gira in background, trova task pronti e li esegue. Pattern identico a `VRAMMonitor` (start/stop + `_poll_task: asyncio.Task | None`).

```
TaskScheduler
├── __init__(config)     — solo config; NESSUNA I/O (pattern VRAMMonitor)
├── start(ctx)           — salva ctx, inizializza Semaphore + _queued_ids, avvia loop
├── stop()               — cancella il task, raccoglie errori (contextlib.suppress)
├── _scheduler_loop()    — asyncio.sleep(poll_interval_s) → _tick()
├── _tick()              — query DB → filtra _queued_ids → asyncio.create_task
├── _execute_task(task)  — Semaphore + wait_for + run_agent_task() + discard _queued_ids
├── _mark_done(task)     — aggiorna status/result/next_run_at in DB
└── _queued_ids          — set[uuid.UUID]: guard anti-doppio-dispatch tra tick consecutivi
```

**`TaskSchedulerProtocol` e costruttore** (da aggiungere a `protocols.py` e `task_scheduler.py`):

```python
# backend/core/protocols.py
class TaskSchedulerProtocol(Protocol):
    """Protocol for the background autonomous task scheduler."""
    async def start(self, ctx: Any) -> None: ...
    async def stop(self) -> None: ...
    async def schedule(self, task: Any) -> str: ...  # returns task_id str
    async def cancel(self, task_id: str) -> bool: ...

# backend/services/task_scheduler.py — costruttore
class TaskScheduler:
    def __init__(self, config: TaskSchedulerConfig) -> None:
        self._config = config
        self._ctx: Any = None                        # set lazily in start()
        self._poll_task: asyncio.Task[None] | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._queued_ids: set[uuid.UUID] = set()     # anti-double-dispatch

    async def start(self, ctx: Any) -> None:
        self._ctx = ctx
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_tasks)
        self._poll_task = asyncio.create_task(
            self._scheduler_loop(), name="task-scheduler",
        )

    async def stop(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None
```

**Implementazione `_scheduler_loop()`** (segue esattamente il pattern VRAMMonitor):

```python
async def _scheduler_loop(self) -> None:
    """Check for due tasks and execute them, forever."""
    while True:
        try:
            await self._tick()
        except asyncio.CancelledError:
            raise  # SEMPRE propagare CancelledError — regola del progetto
        except Exception:
            logger.opt(exception=True).error("TaskScheduler tick error")
        await asyncio.sleep(self._config.poll_interval_s)

async def _tick(self) -> None:
    """Find all pending tasks due <= now and dispatch them."""
    now = datetime.now(timezone.utc)
    async with self._ctx.db() as session:
        result = await session.exec(
            select(AgentTask)
            .where(AgentTask.status == "pending")
            .where(AgentTask.next_run_at <= now)
            .order_by(AgentTask.next_run_at)
            .limit(self._config.max_concurrent_tasks * 2)
        )
        due_tasks = result.all()

    for task in due_tasks:
        if task.id in self._queued_ids:
            continue  # guard: previene doppio-dispatch tra tick consecutivi
        self._queued_ids.add(task.id)
        asyncio.create_task(
            self._execute_task(task),
            name=f"agent-task-{task.id}",
        )
```

**`_execute_task()`** — usa `asyncio.Semaphore` per concorrenza + `asyncio.wait_for` per timeout:

```python
async def _execute_task(self, task: AgentTask) -> None:
    async with self._semaphore:  # max_concurrent_tasks
        # Mark as running
        await self._update_status(task.id, "running")

        _final_status = "failed"  # track real outcome for finally (task.status is stale)
        try:
            summary = await asyncio.wait_for(
                run_agent_task(self._ctx, task),
                timeout=self._config.task_timeout_s,
            )
            _final_status = "completed"
            await self._mark_done(task, success=True, summary=summary)
        except asyncio.TimeoutError:
            await self._mark_done(task, success=False,
                                  error=f"Task timed out after {self._config.task_timeout_s}s")
        except asyncio.CancelledError:
            _final_status = "cancelled"
            await self._mark_done(task, success=False, error="Task cancelled")
            raise
        except Exception as exc:
            await self._mark_done(task, success=False, error=str(exc))
        finally:
            self._queued_ids.discard(task.id)  # libera il guard
            # Emit EventBus event → WSConnectionManager broadcasts to /ws/events clients
            await self._ctx.event_bus.emit(
                AliceEvent.TASK_COMPLETED,
                task_id=str(task.id),
                status=_final_status,
            )
```

**`_mark_done()`** — aggiorna DB e calcola `next_run_at` per task interval:

```python
async def _mark_done(self, task: AgentTask, success: bool, summary: str = "", error: str = "") -> None:
    async with self._ctx.db() as session:
        db_task = await session.get(AgentTask, task.id)
        db_task.status = "completed" if success else "failed"
        db_task.result_summary = summary
        db_task.error_message = error if not success else None
        db_task.last_run_at = datetime.now(timezone.utc)
        db_task.run_count += 1
        db_task.updated_at = datetime.now(timezone.utc)

        if task.trigger_type == "interval" and success and task.interval_seconds is not None:
            # Check max_runs cap (interval_seconds must not be None here — guard defensivo)
            if task.max_runs is None or db_task.run_count < task.max_runs:
                db_task.status = "pending"
                db_task.next_run_at = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=task.interval_seconds)
                )

        await session.commit()
```

**Startup in `app.py`** (dopo `plugin_manager.startup()` — il task scheduler ha bisogno del tool_registry):

```python
if config.task_scheduler.enabled:
    from backend.services.task_scheduler import TaskScheduler
    task_scheduler = TaskScheduler(config.task_scheduler)
    try:
        await task_scheduler.start(ctx)
        ctx.task_scheduler = task_scheduler
        logger.info("Task scheduler started (poll={}s)", config.task_scheduler.poll_interval_s)
    except Exception as exc:
        logger.warning("Task scheduler failed to start: {}", exc)

# Aggiunto in shutdown:
if ctx.task_scheduler:
    try:
        await ctx.task_scheduler.stop()
    except Exception as exc:
        logger.error("Task scheduler shutdown error: {}", exc)
```

---

#### 10.4 — run_agent_task() (`backend/services/task_runner.py`)

**Ruolo**: esegue un singolo `AgentTask` in modo headless (senza WebSocket). Funzione standalone, non un metodo del service, per facilitare i test unitari.

```python
async def run_agent_task(ctx: AppContext, task: AgentTask) -> str:
    """Execute an agent task headlessly and return a result summary.

    Runs a full LLM + tool loop without a WebSocket. Results are
    returned as a natural-language summary string.

    Args:
        ctx: Application context with llm_service and tool_registry.
        task: The AgentTask to execute.

    Returns:
        Natural language summary of what the agent accomplished.

    Raises:
        RuntimeError: If LLM service is unavailable.
        asyncio.TimeoutError: Propagated from caller (TaskScheduler).
        asyncio.CancelledError: Propagated — never swallowed.
    """
    if ctx.llm_service is None:
        raise RuntimeError("LLM service not available")

    tools = await ctx.tool_registry.get_available_tools() if ctx.tool_registry else []

    messages = ctx.llm_service.build_messages(
        user_content=task.prompt,
        history=None,
    )

    conversation_buf: list[dict[str, Any]] = list(messages)
    final_content = ""
    max_iterations = ctx.config.llm.max_tool_iterations

    for iteration in range(max_iterations):
        tool_calls: list[dict[str, Any]] = []
        content_parts: list[str] = []

        async for event in ctx.llm_service.chat(
            conversation_buf,
            tools=tools if tools else None,
        ):
            if event["type"] == "token":
                content_parts.append(event["content"])
            elif event["type"] == "tool_call":
                tool_calls.append(event)
            elif event["type"] == "done":
                break

        final_content = "".join(content_parts)

        if not tool_calls:
            break  # LLM non ha richiesto tool → risposta finale

        # Append assistant message with tool_calls
        conversation_buf.append({
            "role": "assistant",
            "content": final_content,
            "tool_calls": [tc["tool_call"] for tc in tool_calls],
        })

        # Execute all tool calls
        for tc in tool_calls:
            tc_id = tc["tool_call"]["id"]
            name = tc["tool_call"]["function"]["name"]
            args = json.loads(tc["tool_call"]["function"].get("arguments", "{}"))

            execution_ctx = ExecutionContext(
                session_id=f"task-{task.id}",
                conversation_id=str(task.id),
                execution_id=str(uuid.uuid4()),
            )

            try:
                result = await ctx.tool_registry.execute_tool(name, args, execution_ctx)
                tool_content = result.content if isinstance(result.content, str) else json.dumps(result.content)
            except Exception as exc:
                tool_content = f"Error: {exc}"

            conversation_buf.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_content,
            })
    else:
        logger.warning("Task {} hit max_iterations={}", task.id, max_iterations)

    return final_content or "(no output)"
```

**Nota sicurezza**: `run_agent_task` NON supporta tool con `requires_confirmation=True` — i tool richiedenti conferma vengono saltati con un messaggio di errore nel risultato. I task autonomi devono usare solo tool `risk_level="safe"` o `"low"`. Questo è enforced nel plugin (vedi §10.5).

---

#### 10.5 — AgentTask Plugin (`backend/plugins/agent_task/`)

**Ruolo**: espone 4 tool LLM per creare/gestire task autonomi. Pattern identico a tutti gli altri plugin.

```
backend/plugins/agent_task/
├── __init__.py   — import + PLUGIN_REGISTRY["agent_task"] = AgentTaskPlugin
└── plugin.py     — AgentTaskPlugin(BasePlugin)
```

**Tool definitions**:

| Tool | risk_level | requires_confirmation | Descrizione |
|---|---|---|---|
| `schedule_task` | `safe` | `False` | Crea un task autonomo da eseguire in background |
| `cancel_task` | `medium` | `True` | Cancella un task attivo o pianificato |
| `list_tasks` | `safe` | `False` | Elenca i task con filtri opzionali |
| `get_task_result` | `safe` | `False` | Recupera il risultato di un task completato |

> **Nota**: `"low"` non è un valore valido per `ToolDefinition.risk_level` (valori: `"safe"`, `"medium"`, `"dangerous"`, `"forbidden"`). `schedule_task` è `"safe"` perché crea solo un record DB — nessun side effect esterno immediato.

**Schema `schedule_task`**:
```json
{
  "type": "object",
  "properties": {
    "prompt": {
      "type": "string",
      "description": "Istruzione completa per il task. Deve essere auto-esplicativa (l'agente non avrà contesto aggiuntivo al momento dell'esecuzione).",
      "maxLength": 2000
    },
    "trigger_type": {
      "type": "string",
      "enum": ["once_at", "interval", "manual"],
      "description": "once_at: esegui una volta a una data/ora precisa. interval: ripeti ogni N secondi. manual: esegui solo su richiesta esplicita."
    },
    "run_at": {
      "type": "string",
      "description": "ISO 8601 UTC datetime. Obbligatorio se trigger_type='once_at'.",
      "format": "date-time"
    },
    "interval_seconds": {
      "type": "integer",
      "description": "Intervallo in secondi. Obbligatorio se trigger_type='interval'. Min: 60 (1 minuto).",
      "minimum": 60
    },
    "max_runs": {
      "type": "integer",
      "description": "Numero massimo di esecuzioni per task interval. Null = illimitato.",
      "minimum": 1
    }
  },
  "required": ["prompt", "trigger_type"]
}
```

**Validazione in `execute_tool`**:
- `trigger_type='once_at'` senza `run_at` → errore descrittivo
- `trigger_type='interval'` senza `interval_seconds` → errore descrittivo
- `interval_seconds < 60` → errore: "Intervallo minimo: 60 secondi"
- `prompt` > `max_task_prompt_chars` → errore: "Prompt troppo lungo"
- `task_scheduler.enabled=False` → errore: "Task scheduler non attivo"

---

#### 10.6 — WSConnectionManager (`backend/services/ws_connection_manager.py`)

**Ruolo**: mantiene i client connessi a `/api/ws/events` e consente `broadcast()`. Separato dal chat WS. Usato da `TaskScheduler` per fare push dei task completati.

```python
class WSConnectionManager:
    """Manages persistent event WebSocket connections for background push."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}  # session_id → ws
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[session_id] = ws

    async def disconnect(self, session_id: str) -> None:
        async with self._lock:
            self._connections.pop(session_id, None)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Send event to all connected clients. Silently drops disconnected ones.

        Snapshots connections under the lock, then sends OUTSIDE it — holding
        an asyncio.Lock during `await send_json()` would cause starvation if
        any client is slow to receive.
        """
        async with self._lock:
            snapshot = list(self._connections.items())  # O(n) snapshot, lock released
        dead: list[str] = []
        for sid, ws in snapshot:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(sid)
        if dead:
            async with self._lock:
                for sid in dead:
                    self._connections.pop(sid, None)

    async def send_to(self, session_id: str, event: dict[str, Any]) -> None:
        """Send event to a specific session. No-op if disconnected."""
        async with self._lock:
            ws = self._connections.get(session_id)  # read under lock
        if ws:
            try:
                await ws.send_json(event)
            except Exception:
                async with self._lock:  # cleanup under lock
                    self._connections.pop(session_id, None)
```

`WSConnectionManager` viene creato UNA VOLTA nel lifespan di `app.py` e assegnato a `ctx.ws_connection_manager`. Il `TaskScheduler` riceve `ctx` nel costruttore e chiama `ctx.ws_connection_manager.broadcast(...)` dopo ogni task.

**Registrazione in `AppContext`** (nuovo campo):
```python
ws_connection_manager: WSConnectionManagerProtocol | None = None
```

Aggiunto anche in `protocols.py` (`WSConnectionManagerProtocol`).

**EventBus bridge** (in `app.py` lifespan, dopo la creazione del `ws_connection_manager`):
```python
async def _on_task_completed(**kwargs):
    if ctx.ws_connection_manager:
        await ctx.ws_connection_manager.broadcast({
            "type": "task_completed",
            "task_id": kwargs["task_id"],
            "status": kwargs["status"],
        })
ctx.event_bus.subscribe(AliceEvent.TASK_COMPLETED, _on_task_completed)
```

---

#### 10.7 — Endpoint `/api/ws/events` (`backend/api/routes/events.py`)

Router con prefix e tag coerenti col resto del progetto (pattern di `audit.py`):

```python
router = APIRouter(prefix="/events", tags=["events"])

@router.websocket("/ws")
async def ws_events(websocket: WebSocket) -> None:
    """Persistent push channel for background task events.

    Clients connect once at startup and receive push events whenever
    a background task completes, fails, or changes status.
    """
    # Pattern coerente con chat.py: ctx via websocket.app.state.context
    ctx: AppContext = websocket.app.state.context
    if ctx.ws_connection_manager is None:
        await websocket.close(code=1011, reason="Events service not available")
        return

    session_id = f"events-{uuid.uuid4().hex[:12]}"
    await ctx.ws_connection_manager.connect(session_id, websocket)

    try:
        # Keep connection alive; client sends ping {"type": "ping"}
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send keep-alive
                await websocket.send_json({"type": "heartbeat"})
            except WebSocketDisconnect:
                break
    finally:
        await ctx.ws_connection_manager.disconnect(session_id)
```

**URL effettivo** (per il frontend): `/api/events/ws` — derivato da prefix `/api` (root) + `/events` (router) + `/ws` (endpoint).

**Registrazione in `routes/__init__.py`**:
```python
from backend.api.routes import audit, calendar, chat, config, events, models, plugins, settings, tasks, voice

router.include_router(events.router)
router.include_router(tasks.router)
```

Router di `tasks.py`:
```python
router = APIRouter(prefix="/tasks", tags=["tasks"])
```

---

#### 10.8 — REST API (`backend/api/routes/tasks.py`)

Pattern identico a `audit.py` (già noto nel progetto):

```
GET    /api/tasks                     — lista task (filtri: status, trigger_type, limit, offset)
GET    /api/tasks/{task_id}           — dettaglio singolo task
POST   /api/tasks                     — crea task manuale (bypass tool loop)
DELETE /api/tasks/{task_id}           — cancella task
PATCH  /api/tasks/{task_id}/run       — trigger manuale immediato (task manual)
GET    /api/tasks/stats               — count per status
```

**Request body `POST /api/tasks`** (`TaskCreateRequest` Pydantic model):
```python
class TaskCreateRequest(BaseModel):
    prompt: str = Field(max_length=2000)
    trigger_type: Literal["once_at", "interval", "manual"]
    run_at: datetime | None = None
    interval_seconds: int | None = Field(default=None, ge=60)
    max_runs: int | None = Field(default=None, ge=1)
```

---

#### 10.9 — AliceEvent Updates (`backend/core/event_bus.py`)

Aggiunta dei nuovi event al `AliceEvent` StrEnum (senza modificare quelli esistenti):

```python
# Task events (Phase 10)
TASK_SCHEDULED = "task.scheduled"
TASK_STARTED = "task.started"
TASK_COMPLETED = "task.completed"
TASK_FAILED = "task.failed"
TASK_CANCELLED = "task.cancelled"
```

---

#### 10.10 — WebSocket Protocol Updates

Nuovi messaggi S→C su `/api/events/ws` (URL derivato da prefix `/api` + `/events` + `/ws`):

> **Frontend**: il composable `useEventsWebSocket.ts` si connette a `ws://localhost:8000/api/events/ws`.
> All'opposte, la chat WS è su `ws://localhost:8000/api/ws/chat` (definita in `chat.py` con `@router.websocket("/ws/chat")` senza prefix).

Nuovi messaggi S→C su `/api/events/ws`:

| Type | Struttura | Quando |
|---|---|---|
| `task_scheduled` | `{task_id, trigger_type, next_run_at, prompt_preview}` | Task creato/pianificato |
| `task_started` | `{task_id, started_at}` | Inizio esecuzione |
| `task_completed` | `{task_id, status, result_summary, duration_ms}` | Fine esecuzione (ok o fail) |
| `task_failed` | `{task_id, error_message}` | Esecuzione fallita |
| `task_cancelled` | `{task_id}` | Cancellato da utente |
| `heartbeat` | `{}` | Keep-alive ogni 60s |
| `pong` | `{}` | Risposta a `ping` |

Nuovi messaggi **su `/api/ws/chat`** (già esistente) — aggiunta minima:
```json
{"type": "task_created", "task_id": "uuid", "trigger_type": "once_at", "next_run_at": "ISO"}
```
Inviato da `chat.py` quando l'LLM chiama lo strumento `schedule_task` durante una conversazione, così l'utente vede feedback immediato.

---

#### 10.11 — System Prompt Updates (`config/system_prompt.md`)

Aggiungere sezione dedicata nella sezione `tools`:

```yaml
agent_task:
  use: usa SOLO per compiti che l'utente vuole eseguire in modo autonomo in futuro o ricorrente. MAI per compiti one-shot immediati (eseguili subito invece).
  rules:
    - il prompt del task deve essere completamente auto-esplicativo: l'agente non avrà contesto aggiuntivo al momento dell'esecuzione
    - specifica sempre trigger_type in modo esplicito ('once_at', 'interval', 'manual')
    - per 'once_at': usa sempre ISO 8601 UTC, converti l'orario locale dell'utente
    - per 'interval': intervallo minimo 60 secondi; usa valori ragionevoli (es. 3600 per ogni ora)
    - MAI creare task che creano altri task (ricorsione vietata)
    - MAI schedulare task per ambienti non disponibili (es. Home Assistant se offline)
    - CONFERMA sempre orario e frequenza prima di schedulare: "Vuoi che lo esegua ogni giorno alle 8:00?"
    - i task autonomi possono usare SOLO tool non-distruttivi (risk_level='safe')
```

---

#### 10.12 — Frontend

**Nuovo Pinia store `tasks.ts`**:

```typescript
interface AgentTask {
  id: string
  prompt: string
  triggerType: 'once_at' | 'interval' | 'manual'
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  runAt: string | null
  intervalSeconds: number | null
  nextRunAt: string | null
  runCount: number
  resultSummary: string | null
  errorMessage: string | null
  createdAt: string
}

interface TasksState {
  tasks: AgentTask[]
  total: number
  loading: boolean
  recentActivity: TaskActivityEvent[]  // push events da /ws/events
}

// actions:
loadTasks(filters?)       // GET /api/tasks
cancelTask(id)            // DELETE /api/tasks/{id}
triggerManual(id)         // PATCH /api/tasks/{id}/run
createTask(req)           // POST /api/tasks
onTaskEvent(event)        // handler per push events da WSEventsManager
```

**Nuovo composable `useEventsWebSocket.ts`**:

```typescript
// Connessione persistente a /api/ws/events, avviata in App.vue
// Gestisce reconnect (stesso pattern di WebSocketManager per /ws/chat)
// Distribuisce eventi al tasks store via tasksStore.onTaskEvent()
// Heartbeat ogni 30s per mantenere connessione viva
```

**Componente `TaskManager.vue`** (in `components/settings/`):
- Lista task attivi/pianificati con countdown a `next_run_at`
- Badge "in esecuzione" animato
- Pulsante "Esegui ora" per task manual
- Pulsante "Cancella" (con confirm dialog)
- Log degli ultimi N task completati con risultato espandibile

**Notifica toast** (in `App.vue`) quando arriva evento `task_completed` via `/ws/events` — non-invasiva, angolo bottom-right, scompare dopo 5s.

---

#### 10.13 — Dipendenze e Compatibilità

**Nessuna nuova dipendenza** — tutto usa librerie già nel progetto:
- `asyncio` (già usato ovunque)
- `sqlmodel` + `aiosqlite` (già usato)
- `fastapi` WebSocket (già usato)

**VRAM impact**: zero — il `TaskScheduler` non carica modelli. Usa `ctx.llm_service` già in memoria. Se LM Studio è offline durante l'esecuzione del task, `run_agent_task()` solleva `RuntimeError` e il task va in `status='failed'` con messaggio chiaro.

**Sicurezza**:
- Tool con `requires_confirmation=True` vengono bloccati in `run_agent_task()` (nessuna conferma utente possibile in background) con messaggio nel risultato: `"Tool '{name}' richiede conferma utente — non eseguibile in task autonomi"`
- Tool con `risk_level='dangerous'` o `'forbidden'` vengono bloccati allo stesso modo
- `max_task_prompt_chars` previene prompt injection eccessivamente elaborati
- Il prompt del task è salvato in DB as-is e mostrato nella UI prima dell'esecuzione

---

#### 10.14 — File Structure Fase 10

```
backend/
├── services/
│   ├── task_scheduler.py           ← TaskScheduler (asyncio loop, VRAMMonitor pattern)
│   ├── task_runner.py              ← run_agent_task() headless function
│   └── ws_connection_manager.py   ← WSConnectionManager (broadcast + per-session send)
├── plugins/
│   └── agent_task/
│       ├── __init__.py             ← PLUGIN_REGISTRY["agent_task"] = AgentTaskPlugin
│       └── plugin.py              ← AgentTaskPlugin con 4 tool
├── api/
│   └── routes/
│       ├── events.py              ← /api/ws/events WebSocket endpoint
│       └── tasks.py               ← REST /api/tasks/*
├── core/
│   ├── config.py                  ← + TaskSchedulerConfig + AliceConfig.task_scheduler
│   ├── protocols.py               ← + TaskSchedulerProtocol + WSConnectionManagerProtocol
│   ├── context.py                 ← + task_scheduler + ws_connection_manager fields
│   ├── event_bus.py               ← + TASK_* events in AliceEvent
│   └── app.py                     ← + wiring TaskScheduler + WSConnectionManager
├── db/
│   └── models.py                  ← + AgentTask SQLModel
└── tests/
    ├── test_task_scheduler.py
    ├── test_task_runner.py
    ├── test_agent_task_plugin.py
    ├── test_tasks_api.py
    └── test_ws_events.py

frontend/src/renderer/src/
├── stores/
│   └── tasks.ts
├── composables/
│   └── useEventsWebSocket.ts
├── types/
│   └── tasks.ts                   ← AgentTask, TaskActivityEvent TypeScript types
└── components/settings/
    └── TaskManager.vue
```

---

#### 10.15 — Test Suite Fase 10

- **`test_task_runner.py`**:
  - `test_run_agent_task_no_tools`: LLM risponde senza tool call → `result_summary` contiene la risposta
  - `test_run_agent_task_with_tool_call`: mock tool registry + mock LLM con tool_call → tool eseguito, risultato in conversazione
  - `test_run_agent_task_llm_unavailable`: `ctx.llm_service = None` → `RuntimeError` propagato
  - `test_run_agent_task_blocks_dangerous_tools`: tool con `risk_level='dangerous'` → bloccato con messaggio nel risultato
  - `test_run_agent_task_cancelled`: `asyncio.CancelledError` propagato correttamente
  - `test_run_agent_task_max_iterations`: loop LLM con tool calls continui → stop a `max_iterations`

- **`test_task_scheduler.py`** (pattern identico a `test_vram_monitor.py`):
  - `test_start_creates_background_task`: `scheduler.start(ctx)` → `scheduler._poll_task` non è None
  - `test_stop_cancels_background_task`: `start()` → `stop()` → `_poll_task is None`
  - `test_tick_finds_due_tasks`: DB con task pending + `next_run_at = past` → `_tick()` lo trova
  - `test_tick_ignores_future_tasks`: `next_run_at = future` → non eseguito
  - `test_interval_task_rescheduled`: task interval completato → `next_run_at` aggiornato, `status = 'pending'`
  - `test_once_task_not_rescheduled`: task `once_at` completato → `status = 'completed'`, nessun `next_run_at`
  - `test_max_concurrent_semaphore`: `max_concurrent_tasks=1` + 3 task simultanei → al più 1 in running
  - `test_task_timeout`: `task_timeout_s=1` + `run_agent_task` che dura 5s → `asyncio.TimeoutError → status='failed'`
  - `test_scheduler_disabled`: `task_scheduler.enabled=False` → non avviato, zero impatto

- **`test_agent_task_plugin.py`**:
  - `test_schedule_once_at`: chiama `schedule_task` con `trigger_type='once_at'` → `AgentTask` in DB
  - `test_schedule_interval_min_60s`: `interval_seconds=30` → errore descrittivo
  - `test_cancel_task_requires_confirmation`: `cancel_task` ha `requires_confirmation=True`
  - `test_list_tasks`: `list_tasks()` → query DB → risultati formattati
  - `test_schedule_without_required_field`: `once_at` senza `run_at` → errore chiaro

- **`test_ws_events.py`**:
  - `test_ws_events_connect_keepalive`: connect → ping → pong ricevuto
  - `test_ws_events_broadcast`: `manager.broadcast(event)` → tutti i client connessi ricevono
  - `test_ws_events_dead_connection_removed`: client la cui WS fallisce → rimosso da `_connections`

- **`test_tasks_api.py`** (pattern identico a `test_confirmation_audit.py`):
  - CRUD completo via `AsyncClient`
  - Filtri per status
  - `PATCH /tasks/{id}/run` su task manual

- **Verifica no-regression** (pre-PR): tutta la suite esistente deve passare invariata

---

#### 10.16 — Ordine di Implementazione Consigliato

1. **`AgentTask` DB model** — aggiunta pura a `models.py`
2. **`TaskSchedulerConfig`** — aggiunta a `config.py` + `default.yaml`
3. **`AliceEvent` task events** — aggiunta a `event_bus.py`
4. **`WSConnectionManager`** — nuovo file, zero dipendenze
5. **`WSConnectionManagerProtocol`** + campo `AppContext` + wiring in `app.py`
6. **`/api/ws/events` endpoint** — `events.py` route
7. **`run_agent_task()`** — `task_runner.py`, unit testabile in isolamento
8. **`TaskScheduler`** + `TaskSchedulerProtocol` + campo `AppContext` + wiring in `app.py`
9. **`AgentTaskPlugin`** — dipende da `TaskScheduler` tramite `AppContext`
10. **REST `/api/tasks`** — `tasks.py` route
11. **Frontend `tasks.ts` store + `useEventsWebSocket.ts` + `TaskManager.vue`**
12. **Test suite completa**

---

#### 10.17 — Verifiche Fase 10

| Scenario | Comportamento atteso |
|---|---|
| "Ogni mattina alle 8:00 mandami un briefing meteo + notizie" | LLM chiama `schedule_task(trigger_type='interval', interval_seconds=86400, run_at='...')` → task in DB → alle 8:00 `run_agent_task` esegue news + weather tool → risultato push via `/ws/events` |
| "Cancella il briefing mattutino" | LLM chiama `list_tasks` → trova task → chiama `cancel_task(task_id)` con confirm → status='cancelled' |
| Task fallisce (LM Studio offline) | status='failed', `error_message="LLM service not available"`, push event al frontend, task interval resta in pending per il prossimo ciclo |
| Task tenta tool con `requires_confirmation=True` | Bloccato da `run_agent_task()` con messaggio nel risultato, non crashato |
| `task_scheduler.enabled=False` (default) | Backend avvia normalmente, tool `schedule_task` restituisce errore chiaro, zero impatto su test esistenti |
| 3 task in DB tutti in scadenza contemporaneamente con `max_concurrent_tasks=2` | Solo 2 vengono eseguiti in parallelo; il terzo attende che si liberi un slot |
| Task interval con `max_runs=5` che ha già girato 5 volte | `status='completed'`, non rischedulato, stop definitivo |
| Frontend disconnesso quando task termina | `broadcast()` fallisce silenziosamente per quella sessione, rimossa da `_connections`, nessun crash |
| Restart backend con task interval in pending | Al riavvio `_tick()` trova `next_run_at <= NOW()` → esegue immediatamente |

---

