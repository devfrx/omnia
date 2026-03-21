### Fase 3 — Plugin System

#### 3.1 — BasePlugin ABC + PluginManager
- [x] `BasePlugin` ABC con interfaccia completa:
  - `plugin_name: str` — nome univoco del plugin (match chiave `PLUGIN_REGISTRY`)
  - `plugin_version: str` — semver (es. `"1.0.0"`)
  - `PLUGIN_API_VERSION: str` — semver API contract (per compatibilità retroattiva)
  - `plugin_dependencies: list[str]` — nomi plugin da cui dipende (per load order)
  - `plugin_priority: int = 50` — ordine esecuzione 0-100 (più alto = priorità maggiore)
  - `requires_user_confirmation: bool = False` — override in plugin distruttivi (Fase 5)
  - `async def initialize(ctx: AppContext)` / `async def cleanup()` (I/O deferred, no side-effects in `__init__`)
  - `async def on_app_startup()` / `async def on_app_shutdown()` (per plugin stateful: MQTT, HA)
  - `def get_tools() -> list[ToolDefinition]` — restituisce le definizioni tool (può essere vuoto)
  - `async def execute_tool(tool_name: str, args: dict, context: ExecutionContext) -> ToolResult`
  - `async def cancel_tool(tool_name: str, execution_id: str)` — default no-op
  - `async def pre_execution_hook(tool_name, args) -> bool` (canary per conferma utente)
  - `def check_dependencies() -> list[str]` (segnala dipendenze opzionali mancanti senza crash)
  - `async def get_connection_status() -> ConnectionStatus` — `connected|disconnected|degraded|error` (default `UNKNOWN`)
  - `async def on_dependency_status_change(plugin_name: str, status: ConnectionStatus)` — notifica cambio stato dipendenza
  - `@classmethod def get_config_schema() -> dict` — JSON Schema per config plugin-specifica (UI auto-generata Fase 8)
  - `@classmethod def get_db_models() -> list[type[SQLModel]]` — modelli DB plugin-specifici (tabelle create a startup)
  - `@classmethod async def migrate_config(from_version, old_config, to_version) -> dict` — migrazione config tra versioni
  - `@property def logger` — logger pre-configurato con `bind(plugin=self.plugin_name)`
- [x] `ToolDefinition` dataclass:
  - `name: str` — nome tool (`^[a-zA-Z0-9_-]{1,64}$`)
  - `description: str` — max 1024 caratteri
  - `parameters: dict` — JSON Schema per argomenti
  - `result_type: Literal["string", "json", "binary_base64"]` — tipo risultato
  - `supports_cancellation: bool = False`
  - `timeout_ms: int = 30000` — timeout esecuzione
  - `requires_confirmation: bool = False` — richiede approvazione utente (Fase 5)
  - `risk_level: Literal["safe", "medium", "dangerous", "forbidden"] = "safe"`
- [x] `ToolResult` dataclass:
  - `success: bool`
  - `content: str | dict | None` — risultato principale (string per OpenAI compat)
  - `content_type: str` — `"text/plain"`, `"application/json"`, `"image/png"`, etc.
  - `execution_time_ms: float`
  - `truncated: bool = False` — True se risultato tagliato per dimensione
  - `error_message: str | None`
- [x] `ExecutionContext` dataclass:
  - `user_id: str | None = None` — forward-compat Fase 8 JWT
  - `session_id: str`
  - `conversation_id: str`
  - `execution_id: str` — UUID per tracciamento/audit
- [x] `ConnectionStatus` enum: `UNKNOWN`, `CONNECTED`, `DISCONNECTED`, `DEGRADED`, `ERROR`
- [x] `PluginManager` con:
  - Registro **statico** (`PLUGIN_REGISTRY` dict) per compatibilità PyInstaller (Fase 8)
  - Flag env `ALICE_PLUGIN_DISCOVERY=dynamic` per scan `importlib` in dev
  - **Risoluzione dipendenze**: topological sort (algoritmo di Kahn) con cycle detection
  - **Load order deterministico**: dipendenze prima, poi per `plugin_priority`
  - Isolamento crash per ogni plugin: `ImportError`, `SyntaxError`, `AttributeError` non abbattono il server
  - Gestione stub vuoti (`__init__.py` privi di classe `BasePlugin`) senza eccezioni
  - `asyncio.Lock` per thread-safety su registry (accesso concorrente da più WS)
  - Deduplicazione nomi plugin (collision detection al load)
  - `startup()` / `shutdown()` che chiamano i lifecycle hooks su tutti i plugin attivi (in ordine dipendenze)
  - `reload_plugin(name)`: freeze new calls → wait in-flight → cleanup → re-import → re-init → update registry
  - Creazione tabelle DB plugin-specifiche a startup (`get_db_models()` → `SQLModel.metadata.create_all`)
  - Health aggregation: `get_all_status() -> dict[str, ConnectionStatus]`
  - Emissione eventi EventBus: `plugin.loaded`, `plugin.failed`, `plugin.status_changed`
- [x] `AppContext` esteso: `plugin_manager: PluginManager | None = None`, `tool_registry: ToolRegistry | None = None` (opzionali, backward-compat con test pre-Fase 3)
- [x] FastAPI lifespan: wrap PluginManager init con `try/except` + flag `app.state.healthy` se plugin critici falliscono

#### 3.2 — ToolRegistry
- [x] Aggregazione tool descriptions (OpenAI format) da tutti i plugin attivi
- [x] Validazione nome: regex `^[a-zA-Z0-9_-]{1,64}$` (compatibilità OpenAI/Ollama)
- [x] **Namespacing opzionale**: nomi tool salvati come `plugin_name + "_" + tool_name` per evitare collisioni (escape dot in underscore)
- [x] Validazione description: max 1024 caratteri (warning se > 512)
- [x] Validazione `parameters`: JSON Schema valido (fallback a schema vuoto `{"type": "object"}`, non crash)
- [x] Collision detection: tool con stesso nome da plugin diversi → errore esplicito al load
- [x] Lookup `O(1)` per tool_call dispatch (dict)
- [x] Thread-safe read (RW-compatible con `asyncio.Lock`)
- [x] **Tool availability dinamica**: `get_available_tools()` filtra per `plugin.get_connection_status() != ERROR`
- [x] **Tool timeout enforcement**: `asyncio.wait_for()` wrapper su ogni `execute_tool()` con `tool.timeout_ms`
- [x] **Tool result truncation**: se `content` > 4096 chars, troncare + `truncated=True` + log warning
- [x] **Tool result sanitization**: strip eccezioni Python, path interni, PII prima di inviare a LLM
- [x] **Errore strutturato** per tool non trovato: `ToolResult(success=False, error_message="Tool 'X' not available: plugin Y disabled")"

#### 3.3 — Tool Calling Loop + History Fix
- [x] **Refactor `build_messages()`**: normalizza `Message` DB → OpenAI-compatible includendo `tool_calls` (per `role:"assistant"`) e `tool_call_id` (per `role:"tool"`)
- [x] **Refactor history fetch** in `ws_chat`: usare normalizzatore invece di `{"role", "content"}` solo
- [x] Tool calling loop in `ws_chat`:
  - `MAX_TOOL_ITERATIONS = 10` (anti-loop-infinito, configurabile)
  - `asyncio.gather` per parallel tool_calls nella stessa risposta LLM
  - **Ogni tool_call**: `asyncio.wait_for(execute, timeout=tool.timeout_ms/1000)` con `TimeoutError` handling
  - Error handling per tool execution: errori formattati come `{"role": "tool", "content": "Error: ..."}` — l'LLM riceve errori strutturati, non eccezioni Python
  - Salvataggio in DB di messaggi `role:"tool"` con `tool_call_id` dopo ogni esecuzione
  - Sync file JSON dopo ogni round di tool execution
  - **Recovery**: se WS si chiude mid-loop, cleanup tool in-flight + salva stato parziale
  - **Dedup**: se LLM chiama stesso tool con stessi args nella stessa iterazione, skip e log warning
- [x] **Confirmation flow (async)**: se `tool.requires_confirmation`:
  1. Invia `{"type": "tool_confirmation_required", "tool_name": ..., "args": ..., "execution_id": ...}` al client
  2. Attendi risposta `{"type": "tool_confirmation_response", "execution_id": ..., "approved": bool}` con timeout 60s
  3. Se approvato → esegui; se rifiutato o timeout → `ToolResult(success=False, error_message="User rejected")`
- [x] `ExecutionContext` dataclass: `user_id=None`, `session_id`, `conversation_id`, `execution_id` — forward-compat con Fase 8 JWT multi-user
- [x] **Audit trail**: emetti `EVENT_TOOL_EXECUTION_START`, `EVENT_TOOL_EXECUTION_SUCCEEDED`, `EVENT_TOOL_EXECUTION_FAILED` su EventBus

#### 3.4 — Plugin system_info (esempio)
- [x] `psutil` con lazy import (`try/except ImportError` + `check_dependencies()`)
- [x] Tool: `get_system_info()` → CPU%, RAM%, disco, OS — output whitelist (no path utente, no processi privati)
- [x] Tool: `get_process_list()` → lista processi (filtrata, no PID sensibili)
- [x] Schema JSON Schema per parametri e validazione argomenti prima dell'esecuzione
- [x] `risk_level: "safe"` per entrambi i tool (nessuna conferma richiesta)
- [x] Test unitari: mock psutil, verifica output schema, verifica whitelist campi

#### 3.5 — ConversationFileManager: schema versioning
- [x] `schema_version: int` nei file JSON (v1 = pre-Fase 3, v2 = con tool_calls)
- [x] Migration v1→v2 al caricamento (aggiunge `tool_calls: null`, `tool_call_id: null` ai messaggi legacy)
- [x] Serializzazione corretta di `role:"tool"` e `tool_calls` array nei nuovi file
- [x] **Sharding futuro**: preparare struttura `data/conversations/` per eventuale sotto-directory per user (`data/conversations/{user_id}/`)

#### 3.6 — Frontend: tool call UI
- [x] Nuovi tipi WS protocol:
  - `{"type": "tool_execution_start", "tool_name": "...", "execution_id": "..."}`
  - `{"type": "tool_execution_done", "tool_name": "...", "result": "...", "execution_id": "..."}`
  - `{"type": "tool_confirmation_required", "tool_name": "...", "args": {...}, "execution_id": "..."}`
  - `{"type": "tool_confirmation_response", "execution_id": "...", "approved": bool}` (client → server)
- [x] Loading state intermedio visibile (spinner/badge tra token LLM e risposta finale)
- [x] `MessageBubble`: visualizzazione tool calls eseguiti (collapsible, come il thinking block)
- [x] **ToolConfirmationDialog**: modale per approvazione/rifiuto azioni con risk_level ≥ medium
- [x] **Chat store**: gestione stato `pendingConfirmations: Map<execution_id, ConfirmationRequest>`

#### 3.7 — Inter-Plugin Communication + EventBus Extension
- [x] Nuovi eventi standard:
  - `plugin.loaded`, `plugin.failed`, `plugin.status_changed`
  - `tool.execution_start`, `tool.execution_succeeded`, `tool.execution_failed`
- [x] **Plugin local state**: `AppContext.plugin_local_state: dict[str, dict]` — ogni plugin aggiorna il proprio stato, read-only per gli altri via `ctx.get_plugin_state(name)`
- [x] **Circuit breaker** su EventBus: se handler fallisce N volte consecutive, disabilitare temporaneamente (evita log flood)

#### 3.8 — Test Suite Fase 3
- [x] Test BasePlugin: lifecycle (init → startup → tool_call → shutdown → cleanup)
- [x] Test PluginManager: load order, collision, crash isolation, reload
- [x] Test ToolRegistry: validazione nome, collision, lookup, thread-safety, timeout
- [x] Test tool calling loop: max iterations, parallel calls, error recovery, confirmation flow
- [x] Test system_info plugin: mock psutil, output schema
- [x] Test ConversationFileManager: migration v1→v2, serializzazione tool_calls

---

