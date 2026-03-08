# O.M.N.I.A. — Orchestrated Modular Network for Intelligent Automation

> Assistente AI personale, 100% locale, modulare e estensibile.

---

## Overview

OMNIA è un assistente AI personale ispirato a Jarvis (Iron Man), costruito per funzionare interamente in locale senza dipendenze da servizi cloud a pagamento. L'architettura è modulare (plugin-based) e progettata per essere spostabile su un server dedicato in futuro.

## Hardware Target

| Componente | Spec |
|---|---|
| GPU | NVIDIA RTX 5080 16GB VRAM |
| CPU | AMD Ryzen 9 9950X3D |
| RAM | 32GB DDR5 |
| OS | Windows |

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| LLM locale | LM Studio / Ollama (OpenAI-compatible) + Qwen 3.5 9B (~6GB VRAM, vision nativo) + Thinking (QwQ, DeepSeek R1) |
| STT | faster-whisper large-v3 (~1.5GB VRAM) |
| TTS | Piper TTS (primario, CPU) + XTTS v2 (opzionale, voice cloning) |
| Backend | Python — FastAPI + uvicorn (ASGI) |
| Frontend | Electron + Vue 3 + TypeScript + Pinia (via electron-vite) |
| Comunicazione | WebSocket (streaming) + REST API (CRUD) |
| Database | SQLite + SQLModel |
| PC Automation | pywinauto + pyautogui + pywin32 |
| IoT | Home Assistant REST API + MQTT (paho-mqtt) |
| Ricerca Web | duckduckgo-search (o SearXNG self-hosted) |
| Python Deps | uv |
| Node Deps | npm |

## Architettura

```
┌─────────────────────────────────────────────────────────┐
│               ELECTRON + VUE 3 (Frontend)               │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ Voice UI │  │ Chat UI  │  │ Plugin UIs (dinamiche) │ │
│  └────┬─────┘  └────┬─────┘  └────────────┬───────────┘ │
│       │ audio        │ json                │ json       │
│       └──────────WebSocket / REST──────────┘            │
└──────────────────────┬──────────────────────────────────┘
                       │  ws://localhost:8000
┌──────────────────────┼───────────────────────────────────┐
│                      ▼      FASTAPI BACKEND              │
│  ┌─────────┐ ┌─────────────┐                             │
│  │ STT Svc │ │ LLM Svc     │──→ LMStudio (:1234)         │
│  │(whisper)│ │(es. Qwen9B) │←── streaming tokens         │
│  └────┬────┘ └────┬────────┘                             │
│       │ text      │ tool calls                           │
│       ▼           ▼                                      │
│  ┌──────────────────────────────┐   ┌─────────┐          │
│  │      Plugin Manager          │   │ TTS Svc │→Speaker  │
│  │ ┌─────┐┌─────┐┌──────┐┌───┐  │   │ (Piper) │          │
│  │ │ PC  ││ IoT ││Search││Cal│  │   └─────────┘          │
│  │ └──┬──┘└──┬──┘└──┬───┘└─┬─┘  │                        │
│  └────┼──────┼──────┼──────┼────┘                        │
└───────┼──────┼──────┼──────┼─────────────────────────────┘
        ▼      ▼      ▼      ▼
     Windows  Home   DDG/   SQLite
     OS APIs  Asst.  SearXNG
              MQTT
```

### Persistenza Conversazioni

```
data/conversations/
├── {uuid}.json          # Una conversazione completa (metadata + messaggi)
├── {uuid}.json
└── ...
```

Ogni conversazione è salvata come file JSON atomico, sincronizzato automaticamente ad ogni modifica. Questo layer fornisce:
- **Durabilità**: i dati sopravvivono a corruzione del DB SQLite
- **Portabilità**: export/import di conversazioni come singoli file JSON
- **Recovery**: ricostruzione completa del DB da file
- **Leggibilità**: formato JSON human-readable per debug e backup

## Budget VRAM/RAM

| Componente | VRAM | RAM |
|---|---|---|
| Qwen 3.5 9B (Ollama, vision nativo) | ~6 GB | ~1 GB |
| Thinking models (swap: QwQ, DeepSeek R1) | ~6-10 GB (shared) | ~1 GB |
| faster-whisper large-v3 | ~1.5 GB | ~0.5 GB |
| Piper TTS | 0 | ~0.1 GB |
| FastAPI + Plugin | 0 | ~0.5 GB |
| Electron + Vue | 0 | ~0.3 GB |
| **Totale** | **~7.5 / 16 GB** | **~2.4 / 32 GB** |

## Roadmap

### Fase 0 — Setup Progetto e Toolchain
- [x] Struttura monorepo
- [x] Backend Python (pyproject.toml, venv, deps)
- [x] Frontend Electron + Vue 3 + TS
- [x] Script di setup/dev
- [x] Git init + .gitignore

### Fase 1 — Core Backend + Chat Testuale
- [x] Config system (Pydantic Settings + YAML)
- [x] AppContext (DI container)
- [x] Event Bus asincrono
- [x] FastAPI app factory
- [x] Ollama + Qwen 3.5 9B setup (vision nativo)
- [x] LLM Service con streaming
- [x] WebSocket chat endpoint
- [x] REST chat history
- [x] Database (SQLite + SQLModel)

### Fase 1.5 — Supporto Multimodale + Thinking

- [x] Thinking model support (QwQ, DeepSeek R1) — parsing `<think>` tags + reasoning_content delta
- [x] Thinking token streaming via WebSocket (`type: "thinking"`)
- [x] Frontend thinking display (collapsible reasoning block)
- [x] Vision model support (LLaVA, Qwen2-VL) — multimodal content format
- [x] Image upload endpoint (POST /chat/upload)
- [x] Image attachment UI (paste, drag-drop, file picker)
- [x] Image display in message bubbles
- [x] Attachment DB model + file storage

### Fase 1.6 — Persistenza Conversazioni su File
- [x] ConversationFileManager service (salvataggio atomico JSON)
- [x] Struttura file: `data/conversations/{id}.json`
- [x] Auto-sync DB → file su ogni mutazione (create, message, delete, rename)
- [x] REST: `POST /api/chat/conversations` (creazione immediata)
- [x] REST: `GET /api/chat/conversations/{id}/export` (export JSON)
- [x] REST: `POST /api/chat/conversations/import` (import JSON)
- [x] Recovery DB da file JSON
- [x] Frontend: persistenza immediata conversazioni
- [x] Frontend: sync su riconnessione WebSocket
- [x] Frontend: export/import conversazioni
- [x] Edge case: backend offline, stream parziali, conversazioni orfane

### Fase 1.7 — Code Block con Syntax Highlighting e Copia
- [x] Syntax highlighting via highlight.js (25+ linguaggi: JS, TS, Python, Java, C#, C++, Go, Rust, Ruby, PHP, SQL, HTML, CSS, JSON, YAML, Bash, etc.)
- [x] Header code block con label linguaggio
- [x] Pulsante "Copia" nel header con feedback visivo ("Copiato!")
- [x] Copia raw code nella clipboard al click
- [x] Tema syntax highlighting warm-gold coerente con estetica OMNIA
- [x] Supporto in MessageBubble (messaggi completati)
- [x] Supporto in StreamingIndicator (risposte in streaming)

### Fase 2 — Frontend Base + Chat UI
- [x] Electron window frameless + custom title bar
- [x] WebSocket manager
- [x] LLM stream composable
- [x] Pinia chat store
- [x] Chat UI components (ChatView, MessageBubble, ChatInput, StreamingIndicator)

### Fase 2.5 — Hardening & Debito Tecnico Pre-Plugin

> Correzioni necessarie prima di iniziare Fase 3. Riducono debito tecnico e prevengono regressioni.

#### 2.5.1 — Backend Hardening
- [x] **Tipizzazione AppContext**: sostituire `Any` con Protocol/tipo concreto per `llm_service`, `stt_service`, `tts_service`, `plugin_manager`
- [x] **BaseService Protocol**: creare `BaseService` con `async start()`, `async stop()`, `async health_check()` — tutti i service futuri lo implementano
- [x] **Config immutabilità**: rimuovere `object.__setattr__` mutation; costruire config come frozen Pydantic model, ricreare istanza se serve
- [x] **Event bus enum**: convertire event names da magic strings (`"llm.response"`) a `enum.StrEnum` (type-safe, refactoring-safe)
- [x] **N+1 query fix**: riscrivere lista conversazioni con `SELECT COUNT(*) GROUP BY` invece di N query separate
- [x] **Connection pool config**: aggiungere `pool_size`, `max_overflow`, `pool_pre_ping` a `create_async_engine()`
- [x] **File upload security**:
  - Max file size (50 MB) in config + validazione
  - Validazione `conversation_id` come UUID (anti path-traversal)
  - Verifica magic bytes per tipo file (non solo MIME type)
  - Cleanup file orfani se transazione DB fallisce
- [x] **URL generation safe**: sostituire `str.split("data/uploads/")` con `pathlib.Path.relative_to()` + `urllib.parse.quote()`
- [x] **Timeout LLM configurabile**: spostare `httpx.AsyncClient(timeout=120.0)` in config, con override per-request
- [x] **Rate limiting minimo**: `slowapi` middleware su REST + max WS connections per IP

#### 2.5.2 — Frontend Hardening
- [x] **Memory leak blob URL**: revocare `URL.createObjectURL()` su cleanup/re-render in `ChatInput.vue`
- [x] **Race condition conversation switch**: dedup richieste, cancellare stream al cambio conversazione
- [x] **Backpressure WebSocket**: buffer check prima di send; coda con limite
- [x] **Virtualizzazione ConversationList**: `vue-virtual-scroller` o simile per 1000+ conversazioni
- [x] **Estrazione componente condiviso**: eliminare duplicazione 100+ righe tra `MessageBubble` e `StreamingIndicator`
- [x] **Error boundary**: componente Vue `<ErrorBoundary>` per isolare crash plugin UI futuri
- [x] **Accessibilità base**: ARIA labels su pulsanti, focus indicators, keyboard navigation sidebar

#### 2.5.3 — Sicurezza Electron
- [x] **Sandbox attivo**: `sandbox: true` + `nodeIntegration: false` + `contextIsolation: true` in `BrowserWindow`
- [x] **CSP header**: `Content-Security-Policy` in `index.html` — `default-src 'self'; connect-src ws://localhost:8000 http://localhost:8000; img-src 'self' blob: data: http://localhost:8000`
- [x] **CORS produzione**: rimuovere `"null"` da `cors_origins` e usare whitelist specifica per environment (dev vs prod)

#### 2.5.4 — Test Coverage Gap
- [x] Test WebSocket: connessione, invio messaggio, ricezione stream, disconnessione, riconnessione
- [x] Test file upload: validazione tipo, size limit, path traversal rejection
- [x] Test ConversationFileManager: file corrotto, disco pieno, permessi mancanti
- [x] Test concurrent: 10+ WS simultanei, race condition su stessa conversazione

---

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
  - Flag env `OMNIA_PLUGIN_DISCOVERY=dynamic` per scan `importlib` in dev
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

### Fase 4 — Voce (STT + TTS)

#### 4.1 — STT Service (faster-whisper)
- [x] `STTService` implementa `BaseService` protocol (`start`, `stop`, `health_check`)
- [x] faster-whisper large-v3 + Silero VAD per voice activity detection
- [x] Lazy VRAM allocation: carica modello STT solo quando voice è attivata (non a startup)
- [x] **Audio buffer validation**: max durata 5 minuti, max size 50 MB, formato supportato (wav, mp3, ogg, flac) con magic bytes check
- [x] **Timeout trascrizione**: `asyncio.wait_for(transcribe, timeout=durata_audio * 1.5)`
- [x] Config: `voice.stt.enabled: bool`, `voice.stt.model`, `voice.stt.language`, `voice.stt.vad_threshold`

#### 4.2 — TTS Service (Piper + opzionale XTTS v2)
- [x] `TTSService` implementa `BaseService` protocol
- [x] Piper TTS primario (CPU-only, ~0.1 GB RAM) — voci italiane
- [x] Opzionale: XTTS v2 per voice cloning (GPU, ~1-2 GB VRAM)
- [x] Config: `voice.tts.engine: Literal["piper", "xtts"]`, `voice.tts.voice`, `voice.tts.speed`
- [x] **Output audio streaming**: genera audio chunk-by-chunk, non attendere fine sintesi

#### 4.3 — WebSocket Voice Protocol
- [x] **Endpoint separato** `/ws/voice` (non mescolare con `/ws/chat` per evitare complessità multiplexing)
- [x] Protocollo binario + JSON su stesso WS:
  - Client → Server: binary frames (audio PCM/opus) + JSON `{"type": "voice_start"/"voice_stop"}`
  - Server → Client: binary frames (audio TTS) + JSON `{"type": "transcript", "text": "..."}`
- [x] **Head-of-line blocking prevention**: se arrivano audio + text simultanei, coda prioritizzata (text ha priorità sulla voice)
- [x] **Auto-cancellation**: se utente invia nuovo messaggio voice mentre LLM sta rispondendo, cancellare risposta precedente

#### 4.4 — Audio Capture Frontend
- [x] `useVoice` composable: `startListening()`, `stopListening()`, `isListening`, `transcript`
- [x] `navigator.mediaDevices.getUserMedia()` con config ottimale per Whisper (16kHz, mono)
- [x] **Push-to-talk** (default) + wake word opzionale
- [x] **Visual indicator**: icona microfono animata durante recording, badge durante processing
- [x] **Audio playback**: `AudioContext` per riproduzione risposte TTS, coda audio per chunk multipli
- [x] **Permessi**: richiesta esplicita permesso microfono con UX chiara; gestione denied gracefully

#### 4.5 — Voice + Tool Calling Interazione
- [x] Se voice input attiva tool call → TTS legge risposta finale (non i tool results intermedi)
- [x] **Confirmation vocale**: per tool `requires_confirmation`, sintetizzare domanda TTS + attendere risposta voice "sì/no"
- [x] Fallback: se TTS/STT non disponibili, degradare silenziosamente a text-only

#### 4.6 — VRAM Budget Manager
- [x] `VRAMMonitor` service: monitora VRAM usata via `nvidia-smi` o `pynvml`
- [x] **Budget tracking**: registra VRAM allocata per componente (LLM ~6GB, STT ~1.5GB, TTS ~0-2GB)
- [x] **Graceful degradation**: se VRAM > 14GB (su 16GB disponibili):
  - Disattiva STT VAD (usa solo push-to-talk)
  - Scalare modello STT a `medium` o `small`
  - Se XTTS attivo, fallback a Piper (CPU)
- [x] Alert via EventBus: `vram.warning`, `vram.critical`

#### 4.7 — Voice Data Privacy
- [x] Audio temporaneo: file WAV salvati in `tempfile.gettempdir()` con auto-delete dopo 60s
- [x] Nessun salvataggio permanente di audio (solo transcript in chat history)
- [x] UI: indicatore chiaro "microfono attivo" + facile disabilitazione

#### 4.8 — Test Suite Fase 4
- [x] Test STT: mock faster-whisper, verifica transcript, timeout, formati invalidi
- [x] Test TTS: mock Piper, verifica output audio, streaming chunk
- [x] Test WS voice: connessione, send audio, ricevi transcript + audio risposta
- [x] Test VRAM monitor: mock nvidia-smi, graceful degradation trigger
- [x] Test voice + tool calling: voice input → tool call → voice output completo

---

### Fase 5 — Plugin: PC Automation

> **Stato architettura attuale**: Il framework di base per risk level, conferme e tool execution è già funzionante (Fase 3). Il plugin `pc_automation` è implementato con security framework completo: whitelists (app, comandi, keys, path), post-screenshot lockout, FORBIDDEN enforcement, reasoning in conferma, audit trail DB + REST endpoint. 109 test dedicati.

#### 5.1 — Security Framework (PREREQUISITO — questa è la fase più critica per sicurezza)
- [x] `risk_level`: già implementato come `Literal["safe", "medium", "dangerous", "forbidden"]` in `ToolDefinition` (`plugin_models.py`)
- [x] `requires_confirmation: bool` già in `ToolDefinition` — gate nel tool loop (`_tool_loop.py`)
- [x] **Enforcement FORBIDDEN**: check esplicito in `_tool_loop.py` — tool con `risk_level="forbidden"` vengono bloccati e loggati nell'audit
- [x] **Whitelist comandi**: dizionario comandi pre-approvati in `constants.py` (ipconfig, systeminfo, tasklist, etc.)
- [x] **Subprocess sicuro**: `shell=False`, argomenti come lista, `timeout=30s`, output troncato a 500 chars (`validators.py`)
- [x] **Path validation**: file target non in directory di sistema (`C:\Windows`, `C:\Program Files`, etc.) — `security.py:validate_path()`
- [x] **Reasoning in conferma**: `thinking_content` passato nel payload WS `tool_confirmation_required` come `reasoning`
- [x] **Post-screenshot lockout**: dopo screenshot, `execute_command` bloccato per 60s (anti-exfiltration) — `ScreenshotLockout` class
- [x] **Confirmation timing attack prevention**: rimosso `asyncio.gather()` per tool con conferma pendente

#### 5.2 — Tool Definitions (plugin `pc_automation` — `backend/plugins/pc_automation/plugin.py`)
- [x] `open_application(app_name: str)` — risk: `medium`, `requires_confirmation: True`, whitelist app names
- [x] `close_application(app_name: str)` — risk: `medium`, `requires_confirmation: True`
- [x] `type_text(text: str)` — risk: `medium`, `requires_confirmation: True`
- [x] `press_keys(keys: list[str])` — risk: `medium`, `requires_confirmation: True`, whitelist combinazioni
- [x] `take_screenshot() -> base64_png` — risk: `medium`, `requires_confirmation: True`, `timeout_ms: 10000`
- [x] `get_active_window() -> str` — risk: `safe`, `requires_confirmation: False`
- [x] `get_running_apps() -> list[str]` — risk: `safe`, `requires_confirmation: False`
- [x] `execute_command(command: str)` — risk: `dangerous`, `requires_confirmation: True`, solo whitelist
- [x] `move_mouse(x, y)` / `click(x, y)` — risk: `medium`, `requires_confirmation: True`
- [x] Registrazione plugin: `PLUGIN_REGISTRY["pc_automation"] = PcAutomationPlugin` + `config/default.yaml` plugins.enabled

#### 5.3 — Executor (async wrapper)
- [x] Pattern `asyncio.to_thread()` già consolidato nel codebase (usato in `stt_service`, `tts_service`, `system_info`, `conversation_file_manager`, ecc.)
- [x] Timeout per-tool già supportato via `ToolDefinition.timeout_ms` + `asyncio.wait_for()` in `tool_registry.execute_tool()`
- [x] Output sanitization (rimozione traceback, path) + troncamento a 4096 chars già in `tool_registry.py`
- [x] Applicare `asyncio.to_thread()` a tutte le chiamate blocking nel plugin (`executor.py`)
- [x] Error handling specifico: `ValueError`/`RuntimeError`/`OSError` catturate → `ToolResult.error()` con messaggi user-friendly
- [x] **Screenshot**: downscale automatico se > 2MP, `result_type: "binary_base64"`, lockout post-screenshot

#### 5.4 — Confirmation UI (parzialmente implementata — completare gap)
- [x] Modale `ToolConfirmationDialog.vue` esistente con: tool name badge, args JSON formattato, risk level badge colorato (warning/error/error-severe), pulsanti Approva/Rifiuta
- [x] **Keyboard shortcut**: Enter = approva, Esc = rifiuta — già implementati
- [x] Auto-approve per tool `safe` senza mostrare dialog (`useChat.ts`)
- [x] Backend: `_request_confirmation()` con timeout server-side via `config.llm.confirmation_timeout_s`
- [x] **Reasoning display**: campo `reasoning` nel payload WS e tipo TS `WsToolConfirmationRequiredMessage` — sezione collassabile nel dialog
- [x] **Timer visuale 60s**: countdown live nel dialog frontend con cambio colore + auto-reject
- [x] **Log azioni (audit trail)**: DB model `ToolConfirmationAudit` + log su ogni approvazione/rifiuto + endpoint `GET /api/audit/confirmations`
- [x] **Attiva/Disattiva approvazione**: config setting + toggle in Settings UI + warning safety

#### 5.5 — Test Suite Fase 5
- [x] Test security: tool `forbidden` non eseguibile, path traversal bloccato, shell injection bloccato, whitelist comandi (33 test in `test_security_framework.py`)
- [x] Test confirmation flow: approval, rejection, timeout, reasoning nel payload (9 test in `test_confirmation_audit.py`)
- [x] Test executor: mock pyautogui/pywinauto, `asyncio.to_thread()` wrapping (23 test in `test_pc_executor.py`)
- [x] Test screenshot: downscale, post-screenshot lockout, thread safety (9 test in `test_screenshot.py`)
- [x] Test audit trail: persistenza approvazioni/rifiuti, query endpoint, model validation
- [x] Test plugin lifecycle: attributi, init, tool definitions, risk levels (18 test in `test_pc_automation.py`)
- [x] Test validators: safe subprocess, input sanitization (15 test in `test_pc_validators.py`)

---

<!-- ### Fase 6 — Plugin: Domotica / IoT

#### 6.1 — Home Assistant Client
- [ ] `HomeAssistantService`: singleton con persistent `httpx.AsyncClient` (connection pool, non nuova connessione per ogni tool call)
- [ ] REST API: `GET /api/states`, `POST /api/services/{domain}/{service}` con retry + backoff
- [ ] WebSocket HA: subscribe state changes (real-time device updates)
- [ ] **Credential management**: `SecretStr` per token HA; config attuale usa plaintext → migrare; ideale: OS keyring (`keyring` library)
- [ ] **Connectivity validation**: test connessione a startup, emit `plugin.status_changed` se offline
- [ ] **Rate limiting**: max 10 req/s verso HA API (evitare flood)

#### 6.2 — MQTT Client
- [ ] `MQTTService`: `paho-mqtt` con persistent connection + auto-reconnect (backoff esponenziale)
- [ ] **TLS obbligatorio di default**: porta 8883, verifica certificato, TLS 1.2+
- [ ] **Credenziali sicure**: `SecretStr` per password MQTT; no plaintext in config YAML
- [ ] **QoS 1** (at least once) per comandi dispositivi
- [ ] Background task per `loop_start()` — non bloccare event loop
- [ ] **Command validation whitelist**: solo comandi conosciuti per tipo dispositivo (light, switch, lock, climate, sensor)
- [ ] **IoT command sanitization**: no caratteri speciali (`;`, `|`, `&`, backtick) nei parametri

#### 6.3 — Device Registry
- [ ] DB model: `Device(id, name, device_type, area, capabilities, protocol, last_seen, state)`
- [ ] Sync automatico da Home Assistant → device registry locale
- [ ] Filtro per area/tipo → tool descriptions contestuali per LLM
- [ ] **Device access control**: lista dispositivi "protetti" non controllabili da LLM (es. serrature, telecamere di sicurezza, allarme)
- [ ] Config: `iot.protected_devices: list[str]` — nomi/ID dispositivi mai auto-controllabili

#### 6.4 — Event-Driven Updates
- [ ] **Unsolicited messages**: quando un dispositivo cambia stato, inviare al frontend:
  - `{"type": "iot_state_update", "device_id": "...", "new_state": "...", "changed_by": "external|omnia"}`
- [ ] **Notification vs message**: gli update IoT NON finiscono nella chat history; sono notifiche separate
- [ ] Frontend: notification toast per state changes (opzionale, configurabile per dispositivo)

#### 6.5 — Test Suite Fase 6
- [ ] Test HA client: mock httpx, autenticazione, retry su errore, rate limiting
- [ ] Test MQTT: mock paho-mqtt, TLS, reconnect, QoS
- [ ] Test command validation: whitelist, sanitization, device access control
- [ ] Test device registry: sync, filtro, dispositivi protetti

--- -->

### Fase 7 — Plugin: Ricerca Web + Calendario

#### 7.1 — Web Search Plugin
- [ ] DuckDuckGo search primario (`duckduckgo-search` library)
- [ ] Opzionale: SearXNG self-hosted come alternativa
- [ ] **SSRF prevention**: validare URL risultati — bloccare `localhost`, `127.0.0.1`, `10.*`, `192.168.*`, `169.254.*`, indirizzi IPv6 locali
- [ ] **Rate limiting**: max 1 req/10s verso DDG (evitare ban)
- [ ] **Proxy support** in config: `web.proxy.http`, `web.proxy.https`, `web.proxy.no_proxy`
- [ ] **Result caching**: cache resultati per 5 minuti (evitare ricerche duplicate); LRU con max 100 entries
- [ ] Tool: `web_search(query: str, max_results: int = 5) -> list[SearchResult]`
- [ ] Tool: `web_scrape(url: str) -> str` — estrai testo con `httpx` + `beautifulsoup4`; max 50KB output; timeout 10s

#### 7.2 — Calendario Plugin
- [ ] DB models plugin-specifici: `CalendarEvent(id, title, description, start_time, end_time, recurrence_rule, reminder_minutes, created_by)`
- [ ] Tool: `create_event(title, start, end, description?, recurrence?)` — risk: `SAFE`
- [ ] Tool: `list_events(from_date, to_date)` — risk: `SAFE`
- [ ] Tool: `delete_event(event_id)` — risk: `MEDIUM` (confirmation)
- [ ] **Recurring events**: RRULE format (RFC 5545) con parsing via `python-dateutil`
- [ ] **Reminder system**: background task che controlla reminder ogni minuto; emette `calendar.reminder` event
- [ ] **Timezone handling**: tutti i tempi in UTC nel DB; conversione a timezone utente (config `calendar.timezone: str`)
- [ ] **Futura integrazione esterna**: forward-compat con CalDAV/Google Calendar (non implementare ora, ma struttura DB pronta)

#### 7.3 — Plugin UI (Vue components)
- [ ] **Strategia**: plugin components bundled nel frontend (Option A — semplice per Electron; Option B con fetch remoto in Fase 8)
- [ ] `defineAsyncComponent()` per lazy loading componenti plugin
- [ ] **Plugin component registry**: `PluginManager.get_frontend_components()` → REST endpoint `GET /api/plugins/components` → frontend carica async
- [ ] **Mount points** per plugin UI: `sidebar`, `modal`, `toolbar`, `settings-panel`
- [ ] Componente `CalendarView.vue`: vista settimanale/mensile base, CRUD eventi
- [ ] Componente `SearchResultsPanel.vue`: risultati ricerca in sidebar collassabile

#### 7.4 — Test Suite Fase 7
- [ ] Test web search: mock DDG, rate limiting, SSRF blocking, caching
- [ ] Test web scrape: mock httpx, max size, timeout, URL validation
- [ ] Test calendar: CRUD, recurring events, reminder trigger, timezone
- [ ] Test plugin UI loading: async component, mount points

---

### Fase 8 — Polish e Server-readiness

#### 8.1 — System Prompt & Settings
- [ ] System prompt personalizzabile da UI Settings
- [ ] Editor system prompt con preview (markdown)
- [ ] Settings UI completa: modello LLM, temperatura, max tokens, lingua, tema, plugin on/off
- [ ] **Settings persistence**: salvare su file `config/user.yaml` (overlay su `default.yaml`)
- [ ] REST: `GET/PUT /api/config` per leggere/scrivere settings
- [ ] **Plugin settings**: auto-generate form dalla `get_config_schema()` di ogni plugin
- [ ] Global hotkey: `Ctrl+Shift+O` → attivazione finestra OMNIA (Electron `globalShortcut`)

#### 8.2 — Auth JWT per Deployment Remoto
- [ ] `AuthConfig`: `enabled: bool = False` (local: off), `jwt_secret: SecretStr`, `jwt_algorithm: str = "HS256"`, `token_expiry: int = 3600`
- [ ] Middleware FastAPI: validazione JWT su tutte le route REST quando `auth.enabled = True`
- [ ] **WebSocket auth**: dopo `accept()`, primo messaggio dev'essere `{"type": "auth", "token": "..."}` — timeout 5s, altrimenti `close(403)`
- [ ] Login endpoint: `POST /api/auth/login` → JWT token
- [ ] **Secret management per produzione**: JWT secret da env var `OMNIA_JWT_SECRET`, MAI in config file

#### 8.3 — Multi-User Isolation
- [ ] `Conversation.user_id: str | None` — nullable per backward compat (local = tutti None)
- [ ] Filtro `WHERE user_id = ?` su tutte le query quando auth attivo
- [ ] File conversazioni: `data/conversations/{user_id}/{conv_id}.json` (migrazione path da flat)
- [ ] Plugin context: `ExecutionContext.user_id` propagato a ogni tool call
- [ ] **Isolamento plugin state**: `plugin_local_state` scoped per user quando multi-user attivo
- [ ] **PC Automation + multi-user**: disabilitare se multi-user attivo (chi controlla il PC di chi?)
- [ ] **Voice + multi-user**: una sola sessione voice alla volta (chi parla?)

#### 8.4 — Database Migrations
- [ ] **Alembic** per schema migrations (non `create_all` manual)
- [ ] Script migration: v1 (pre-Fase3) → v2 (tool_calls) → v3 (user_id) → v4 (plugin tables)
- [ ] Auto-migration a startup se version mismatch detected
- [ ] Backup automatico DB prima di migration

#### 8.5 — Packaging
- [ ] **Backend**: PyInstaller con static `PLUGIN_REGISTRY` (no importlib dinamico in prod)
  - `--hidden-import` per ogni plugin
  - Data files: `config/`, `data/`, modelli Piper
  - Test: built executable funziona identico a dev
- [ ] **Frontend**: electron-builder per Windows (`nsis`), macOS (`dmg`), Linux (`appimage`)
  - Auto-update: `electron-updater` con GitHub Releases
  - **Backend spawn**: Electron spawna processo Python bundled come child process
  - Shared data directory: `%APPDATA%\OMNIA` (Win), `~/Library/Application Support/OMNIA` (macOS), `~/.config/omnia` (Linux)
- [ ] **Crash handling**: unhandled exception → salva log + notifica utente; restart automatico backend
- [ ] **Versioning coordinato**: backend version + frontend version in sync (semver, tag Git)

#### 8.6 — Observability & Logging
- [ ] Log strutturati (JSON) in produzione (loguru con JSON sink)
- [ ] **Trace ID** per ogni request/WS session: propagato attraverso tool calls, plugin, DB
- [ ] Performance metrics via EventBus: tool execution time, LLM latency, WebSocket round-trip
- [ ] Health endpoint arricchito: `GET /api/health` → `{status, plugins: {name: status}, vram_usage, db_ok, uptime}`

#### 8.7 — Test Suite Fase 8
- [ ] Test JWT: login, token validation, expiry, WS auth flow
- [ ] Test multi-user: isolation conversazioni, plugin state scoping, migration path file
- [ ] Test packaging: PyInstaller build → smoke test; electron-builder → smoke test
- [ ] Test migrations: Alembic upgrade/downgrade, backup/restore
- [ ] E2E: Electron app avviato, connessione backend, chat funzionante, plugin attivi

---

## Requisiti Cross-Cutting (Tutte le Fasi)

### Gestione VRAM
| Configurazione | Componenti | VRAM Stimata |
|---|---|---|
| Solo chat | Qwen 3.5 9B | ~6 GB |
| Chat + voice | Qwen + faster-whisper | ~7.5 GB |
| Chat + voice + XTTS | Qwen + whisper + XTTS v2 | ~9.5 GB |
| Chat + vision (screenshot) | Qwen + immagine in contesto | ~6.2 GB |
| Thinking model | QwQ / DeepSeek R1 (swap Qwen) | ~6-10 GB |
| **Massimo simultaneo** | Qwen + whisper + Piper(CPU) | **~7.5 / 16 GB** |

**Regola**: non superare 14 GB allocati (2 GB headroom per OS + driver). `VRAMMonitor` emette alert.

### Error Handling Standard
```
ToolError → { tool_name, error_type (timeout|permission|network|logic|internal), message, suggestions[] }
```
- Errori plugin: loggati con trace ID, non esposti raw all'utente
- Errori LLM: retry automatico 1 volta, poi errore user-friendly
- Errori DB: log + alert, fallback read-only se possibile
- Errori WS: riconnessione automatica con exponential backoff (max 30s, non 8+ minuti)

### WebSocket Protocol Completo (Evoluzione per Fase)
| Type | Fase | Direzione | Payload |
|---|---|---|---|
| `token` | 1 | S→C | `{content}` |
| `thinking` | 1.5 | S→C | `{content}` |
| `done` | 1 | S→C | `{message}` |
| `error` | 1 | S→C | `{content}` |
| `tool_call` | 3 | S→C | `{id, function: {name, arguments}}` |
| `tool_execution_start` | 3 | S→C | `{tool_name, execution_id}` |
| `tool_execution_done` | 3 | S→C | `{tool_name, result, execution_id}` |
| `tool_confirmation_required` | 3 | S→C | `{tool_name, args, risk_level, reasoning, execution_id}` |
| `tool_confirmation_response` | 3 | C→S | `{execution_id, approved}` |
| `voice_start` / `voice_stop` | 4 | C→S | `{}` |
| `transcript` | 4 | S→C | `{text}` |
| `audio` | 4 | bidirezionale | binary frames |
| `iot_state_update` | 6 | S→C | `{device_id, new_state, changed_by}` |
| `auth` | 8 | C→S | `{token}` |

---

## Verifiche per Fase

| Fase | Test |
|---|---|
| 1-2 | "Ciao OMNIA" → risposta streammata in italiano |
| 1.5 | Immagine + "Cosa vedi?" → descrizione; Thinking model → blocco ragionamento collassabile |
| 1.6 | Export conversazione → file JSON valido; import → conversazione ripristinata; recovery DB → dati intatti |
| 1.7 | Codice in chat → syntax highlighting colorato; click "Copia" → codice nella clipboard + feedback "Copiato!" |
| 2.5 | Upload file > 50MB → errore 413; `sandbox: true` in Electron; N+1 query eliminata |
| 3 | "Quanta RAM uso?" → tool call `get_system_info` → risposta naturale con dati reali |
| 3 (edge) | Plugin crash → server stabile; tool timeout → errore user-friendly; loop infinito → stop a 10 iterazioni |
| 4 | Voce: "Che ore sono?" → transcript → risposta testuale → audio TTS; VRAM < 14GB |
| 4 (edge) | Voice + text simultanei → nessun hang; STT non disponibile → fallback text-only |
| 5 | "Apri Notepad" → confirmation dialog → approvazione → Notepad si apre |
| 5 (edge) | Prompt injection "cancella tutto" → tool FORBIDDEN bloccato; shell injection → bloccato |
| 6 | "Accendi la luce" → HA API call → luce si accende; MQTT disconnect → plugin status degraded |
| 6 (edge) | Dispositivo protetto → rifiuto; command injection → bloccato; HA offline → errore user-friendly |
| 7 | "Che tempo fa a Roma?" → DDG search → risposta con fonti; "Ricordami riunione domani" → evento creato |
| 7 (edge) | SSRF `http://localhost` → bloccato; DDG rate limit → caching; timezone UTC↔local corretta |
| 8 | JWT login → token → WS auth → chat; PyInstaller build → app funzionante; Ctrl+Shift+O → attivazione |
| 8 (edge) | Multi-user: utente A non vede conversazioni utente B; migration DB → zero data loss |
