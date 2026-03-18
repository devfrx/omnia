### Fase 9 — Memory Service (Agente con Memoria Persistente)

- [x] EmbeddingClient (OpenAI + fastembed fallback) — §9.2
- [x] MemoryConfig in config.py + default.yaml — §9.3
- [x] MemoryServiceProtocol in protocols.py — §9.1
- [x] AppContext.memory_service field — §9.1
- [x] MemoryService (sqlite-vec CRUD + vector search) — §9.1
- [x] App lifespan (startup init + shutdown close) — §9.1
- [x] MemoryPlugin (5 tools: remember/recall/forget/list/clear) — §9.4
- [x] LLM context injection (build_messages + chat.py) — §9.5
- [x] Tool loop memory_context passthrough — §9.5
- [x] REST API /api/memory (5 endpoints) — §9.7
- [x] System prompt memory guidelines — §9.9
- [x] Frontend types + Pinia store + MemoryManager.vue — §9.8
- [x] Test suite (4 files, 46+ test cases) — §9.11
- [x] Dependencies (sqlite-vec, fastembed optional) — §9.10

> **Obiettivo**: trasformare OMNIA da assistente reattivo a agente con memoria semantica persistente.
> Ogni informazione rilevante può essere salvata esplicitamente (tool call) o recuperata
> automaticamente al momento opportuno, senza che l'utente debba ripetersi tra sessioni.

---

#### 9.0 — Analisi Vincoli e Scelte Architetturali

**Perché NON usare ChromaDB o altri vector store esterni:**
- ChromaDB richiede un processo server separato o embedding model dedicato (VRAM extra)
- Su RTX 5080 con Qwen 3.5 9B + Whisper già in esecuzione, ogni GB di VRAM conta
- Dipendenza esterna → possibile rottura a upgrade, setup complesso per packaging PyInstaller
- **Soluzione scelta**: `sqlite-vec` — estensione SQLite (già in uso come DB principale) per ricerca vettoriale.
  - Zero processi extra, zero VRAM dedicata, compatibile con PyInstaller, file unico in `data/`
  - Embedding generati localmente da un modello leggero CPU-only (vedi §9.2)

**Perché NON usare sentence-transformers direttamente:**
- `sentence-transformers` importa PyTorch (~2 GB disco) — inutile se Ollama/LM Studio già gestisce embedding
- **Soluzione scelta**: embedding via LM Studio/Ollama OpenAI-compatible `/v1/embeddings` endpoint
  - Stesso backend già useato per chat → zero overhead aggiuntivo
  - Modello embedding: `nomic-embed-text` (~274 MB VRAM, piccolo) o qualsiasi modello già caricato
  - Fallback CPU: se LM Studio offline → `fastembed` (pure Python, ~50 MB, CPU-only, nessun PyTorch)

**Perché il Memory Service è un `BaseService`, NON un plugin:**
- La memoria è infrastruttura del core (come `LLMService`, `STTService`), non una feature opzionale
- Va iniettata in `AppContext` e usata dal tool loop e dal prompt builder
- I tool `remember`/`recall`/`forget` vengono esposti tramite un **plugin dedicato** (`memory` plugin)
  che si appoggia al service — separazione responsabilità pulita

**Strategia contesto LLM (nessuna regressione):**
- La memoria viene iniettata come blocco `[MEMORIA RILEVANTE]` nel system prompt rebuild,
  **PRIMA** della chiamata LLM ma **DOPO** la costruzione del contesto esistente
- Zero modifica a `LLMService.build_messages()` — la memoria è solo un parametro opzionale
  aggiuntivo passato dalla route WebSocket
- Il prompt inject è parametrico e disattivabile per test

---

#### 9.1 — MemoryService (`backend/services/memory_service.py`)

**Ruolo**: layer di accesso ai ricordi. Non conosce tool, LLM o plugin — solo CRUD vettoriale.

```
MemoryService
├── initialize(ctx)         — apre DB, crea tabella, carica embedding client
├── add(content, metadata)  — embed + insert in sqlite-vec
├── search(query, k, filter) — embed query + cosine similarity search
├── delete(memory_id)       — rimozione per ID
├── list(filter, limit)     — listing con filtri (scope, category, created_after)
└── close()                 — chiude connessione DB e embedding client
```

- `MemoryService` implementa il Protocol `MemoryServiceProtocol` (aggiunto a `protocols.py`)
- Registrato in `AppContext` come `memory_service: MemoryServiceProtocol | None = None`
- Creato in `core/app.py` lifespan, **dopo** DB init e **prima** dei plugin (i plugin possono usarlo)
- `initialize()` è idempotente (safe da chiamare su restart hot-reload)

**Startup** (aggiunta in `app.py` lifespan, dopo `await init_db(engine)` e prima di `PluginManager`):
```python
if config.memory.enabled:
    from backend.services.memory_service import MemoryService
    memory_service = MemoryService(config.memory)
    try:
        await memory_service.initialize()
        ctx.memory_service = memory_service
        logger.info("Memory service started")
    except Exception as exc:
        logger.warning("Memory service failed to start: {}", exc)
```

**Shutdown** (aggiunta in `app.py` lifespan, nella sezione `# -- Shutdown --`, accanto agli altri servizi):
```python
if ctx.memory_service:
    try:
        await ctx.memory_service.close()
    except Exception as exc:
        logger.error("Memory service shutdown error: {}", exc)
```

**DB Model** (`backend/db/models.py`, tabella nativa SQLite, non SQLModel — sqlite-vec usa sintassi custom):

```sql
-- Tabella metadati (SQLModel normale)
CREATE TABLE memory_entries (
    id          TEXT    PRIMARY KEY,   -- uuid4 stringa
    content     TEXT    NOT NULL,      -- testo originale (per display)
    scope       TEXT    NOT NULL DEFAULT 'long_term',  -- 'long_term' | 'session'
    category    TEXT,                  -- tag libero ('preference','fact','skill',...)
    source      TEXT    NOT NULL DEFAULT 'llm',        -- 'llm' | 'user' | 'system'
    created_at  TEXT    NOT NULL,      -- ISO 8601 UTC
    expires_at  TEXT,                  -- ISO 8601 UTC, NULL = permanente
    conversation_id TEXT,             -- UUID conversazione origine (nullable)
    embedding_model TEXT NOT NULL     -- nome modello usato per l'embedding
);

-- Tabella vettori (sqlite-vec sintassi virtuale)
CREATE VIRTUAL TABLE memory_vectors USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[768]              -- dimensione vettore del modello scelto
);
```

`MemoryEntry` SQLModel model — usa `uuid.UUID` come PK con `_new_uuid` factory, **coerentemente con `Conversation`, `Message`, `Attachment` e `ToolConfirmationAudit`**:

```python
class MemoryEntry(SQLModel, table=True):
    __tablename__ = "memory_entries"
    id: uuid.UUID = Field(default_factory=_new_uuid, primary_key=True)  # ← uuid.UUID, come tutti gli altri modelli
    content: str
    scope: str = Field(default="long_term")
    category: str | None = None
    source: str = Field(default="llm")
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
    conversation_id: uuid.UUID | None = None  # ← UUID, non str
    embedding_model: str
```

**Nota JOIN sqlite-vec**: il service layer converte `str(entry.id)` quando inserisce e legge dalla tabella virtuale `memory_vectors`, il cui schema usa `TEXT PRIMARY KEY`. La DDL SQL sopra riflette il tipo fisico SQLite (UUID serializzato come text); il SQLModel Python usa `uuid.UUID` per uniformità con gli altri modelli.

**Nota `memory_vectors` (tabella virtuale)**: creata da `MemoryService.initialize()` via `conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS ...")` dopo aver caricato l'estensione `sqlite-vec`. Non è un SQLModel model perché le tabelle virtuali non sono compatibili con SQLAlchemy reflection.

---

#### 9.2 — EmbeddingClient (`backend/services/embedding_client.py`)

**Ruolo**: genera embedding vettoriali. Astratto con due implementazioni concrete.

```python
class EmbeddingClientProtocol(Protocol):
    async def encode(self, text: str) -> list[float]: ...
    async def encode_batch(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimensions(self) -> int: ...
    async def close(self) -> None: ...
```

**Implementazioni**:

1. **`OpenAIEmbeddingClient`** (primario):
   - Chiama `POST /v1/embeddings` sullo stesso backend LM Studio/Ollama già configurato
   - Modello configurabile: `memory.embedding_model = "nomic-embed-text"` (default)
   - Usa `httpx.AsyncClient` persistente (pool condiviso — non crea nuove connessioni per ogni embed)
   - Timeout: 10s (embedding è veloce — non attendere oltre)
   - **Nessuna dipendenza aggiuntiva** — stessa URL di `LLMConfig.base_url`

2. **`FastEmbedClient`** (fallback CPU-only):
   - `fastembed.TextEmbedding` — pure Python, CPU, nessun PyTorch
   - Lazy import: `try: from fastembed import TextEmbedding`
   - Usato automaticamente se `OpenAIEmbeddingClient.encode()` fallisce con `ConnectError`
   - Modello default: `"BAAI/bge-small-en-v1.5"` (33 MB, 384 dim)
   - Caching in-process del modello (non ricaricare ad ogni chiamata)

**Selezione automatica**:

```python
class EmbeddingClient:
    """Facade con fallback automatico OpenAI → fastembed."""
    async def encode(self, text: str) -> list[float]:
        try:
            return await self._openai.encode(text)
        except (ConnectError, TimeoutError):
            logger.warning("Embedding API unreachable, falling back to fastembed")
            return await self._fastembed.encode(text)
```

**Coerenza dimensioni**: quando il modello embedding cambia (es. switch da 768 a 384 dim), il `MemoryService` rileva la mismatch alla creazione della tabella vettoriale e lancia `MemoryDimensionMismatchError` con istruzione chiara: `"Run: omnia memory migrate --reembed"` (script futuro).

---

#### 9.3 — MemoryConfig (`backend/core/config.py`)

```python
class MemoryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OMNIA_MEMORY__")

    enabled: bool = False
    """Abilita il Memory Service. False di default (opt-in esplicito)."""

    db_path: str = "data/memory.db"
    """Path del file SQLite dedicato alla memoria (separato da omnia.db)."""

    embedding_model: str = "nomic-embed-text"
    """Nome modello embedding per LM Studio/Ollama /v1/embeddings."""

    embedding_dim: int = 768
    """Dimensione vettori embedding del modello scelto."""

    embedding_fallback: bool = True
    """Se True, usa fastembed CPU se LLM embedding API non disponibile."""

    top_k: int = 5
    """Numero massimo di ricordi recuperati per injection nel contesto."""

    similarity_threshold: float = 0.75
    """Score minimo coseno per includere un ricordo (0.0–1.0)."""

    inject_in_context: bool = True
    """Se True, ricordi rilevanti vengono iniettati nel system prompt."""

    context_max_chars: int = 2000
    """Massimo caratteri iniettati dal memory context nel prompt."""

    session_ttl_hours: int = 24
    """TTL per ricordi di scope 'session'. Dopo scadenza vengono ignorati."""

    auto_cleanup_days: int = 90
    """Rimuovi automaticamente ricordi non acceduti da N giorni (0 = disabilitato)."""
```

Aggiunta a `OmniaConfig`:
```python
memory: MemoryConfig = Field(default_factory=MemoryConfig)
```

Config YAML entry (`config/default.yaml`) — due sezioni da aggiungere:

```yaml
# In plugins.enabled, aggiungere (commentato per default-off, come home_automation):
plugins:
  enabled:
    # ...lista esistente...
    # - memory  # abilitare con memory.enabled: true

# Nuova sezione memory:
memory:
  enabled: false
  embedding_model: "nomic-embed-text"
  embedding_dim: 768
  top_k: 5
  similarity_threshold: 0.75
  inject_in_context: true
  context_max_chars: 2000
  session_ttl_hours: 24
  auto_cleanup_days: 90
```

---

#### 9.4 — Memory Plugin (`backend/plugins/memory/`)

**Ruolo**: espone i tool LLM per interagire con la memoria. Non contiene logica vettoriale — delega tutto a `MemoryService` tramite `AppContext`.

```
backend/plugins/memory/
├── __init__.py          — import + PLUGIN_REGISTRY["memory"] = MemoryPlugin
└── plugin.py            — MemoryPlugin(BasePlugin)
```

Pattern `__init__.py` identico a tutti gli altri plugin (es. `web_search/__init__.py`):

```python
"""O.M.N.I.A. — Memory plugin package.

Importing this module registers MemoryPlugin in the static PLUGIN_REGISTRY.
"""
from backend.core.plugin_manager import PLUGIN_REGISTRY
from backend.plugins.memory.plugin import MemoryPlugin  # noqa: F401

PLUGIN_REGISTRY["memory"] = MemoryPlugin
```

**Pattern**: identico agli altri plugin esistenti — `BasePlugin` con `get_tools()` e `execute_tool()`.

```python
class MemoryPlugin(BasePlugin):
    plugin_name = "memory"
    plugin_version = "1.0.0"
    plugin_description = (
        "Persist and retrieve long-term memories. "
        "Use remember() to save facts and recall() to search them."
    )
    plugin_dependencies: list[str] = []
    plugin_priority: int = 90  # Si inizializza prima degli altri (Kahn's algo, reverse=True — ordine caricamento, non disponibilità)

    async def initialize(self, ctx: AppContext) -> None:
        await super().initialize(ctx)
        if ctx.memory_service is None:
            logger.warning("MemoryPlugin: memory_service not available in context")
```

**Tool definitions**:

| Tool | risk_level | requires_confirmation | Descrizione |
|---|---|---|---|
| `remember` | `safe` | `False` | Salva un fatto/preferenza nella memoria a lungo termine |
| `recall` | `safe` | `False` | Cerca ricordi rilevanti tramite similarità semantica |
| `forget` | `medium` | `True` | Cancella un ricordo specifico per ID |
| `list_memories` | `safe` | `False` | Elenca ricordi con filtri opzionali |
| `clear_session_memory` | `medium` | `True` | Cancella tutti i ricordi di scope `session` |

**Schema tool `remember`**:
```json
{
  "type": "object",
  "properties": {
    "content": {"type": "string", "description": "Il fatto o preferenza da memorizzare. Sii conciso e preciso.", "maxLength": 1000},
    "category": {"type": "string", "description": "Categoria opzionale ('preference', 'fact', 'skill', 'context')", "enum": ["preference", "fact", "skill", "context"]},
    "scope": {"type": "string", "description": "Durata: 'long_term' (permanente) o 'session' (solo questa sessione)", "enum": ["long_term", "session"], "default": "long_term"},
    "expires_hours": {"type": "integer", "description": "Ore di validità (opzionale, null = permanente)", "minimum": 1, "maximum": 8760}
  },
  "required": ["content"]
}
```

**Schema tool `recall`**:
```json
{
  "type": "object",
  "properties": {
    "query": {"type": "string", "description": "Cosa cercare nella memoria", "maxLength": 500},
    "category": {"type": "string", "description": "Filtra per categoria (opzionale)"},
    "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20}
  },
  "required": ["query"]
}
```

**Regola `requires_confirmation=False` per `remember`/`recall`**: entrambi sono operazioni non distruttive e frequenti — richiedere conferma ogni volta renderebbe l'esperienza utente insopportabile. `forget` richiede conferma perché è irreversibile.

---

#### 9.5 — Context Injection (modifica `backend/api/routes/chat.py`)

**Dove**: nella route WebSocket in `backend/api/routes/chat.py`, PRIMA della chiamata `llm.build_messages()` (attualmente a riga ~363), DOPO il pre-load degli attachment. Il file corretto è `chat.py` — non esiste `ws_chat.py`.

**Pattern**: aggiunta di un parametro opzionale `memory_context: str | None` a `LLMService.build_messages()` **e al corrispondente** `LLMServiceProtocol.build_messages()` in `protocols.py` — zero breaking change (default `None`).

```python
# In chat.py, prima di llm.build_messages(...)
memory_context: str | None = None
if ctx.memory_service and ctx.config.memory.inject_in_context:
    relevant = await ctx.memory_service.search(
        query=user_content,
        k=ctx.config.memory.top_k,
        filter={"scope": "long_term"},  # solo memoria permanente nel contesto
    )
    if relevant:
        memory_context = _format_memory_context(relevant, ctx.config.memory.context_max_chars)

messages = llm.build_messages(
    user_content,
    history=history[:-1],  # invariato rispetto al codice attuale
    attachments=attachment_info or None,
    memory_context=memory_context,  # nuovo parametro opzionale
)
```

**`_format_memory_context()`** (funzione modulo-level in `chat.py`):

```python
def _format_memory_context(memories: list[MemoryEntry], max_chars: int) -> str:
    """Serializza i ricordi rilevanti in un blocco testo per il system prompt."""
    lines = ["[RICORDI RILEVANTI]"]
    total = 0
    for m in memories:
        line = f"- [{m.category or 'generale'}] {m.content}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)
```

**Modifica `LLMService.build_messages()` e `LLMServiceProtocol.build_messages()`**:

L'attuale signature in `llm_service.py` usa la variabile locale `sys_prompt = self._get_dynamic_system_prompt()`. La modifica corretta è:

```python
def build_messages(
    self,
    user_content: str,
    history: list[dict[str, Any]] | None = None,
    attachments: list[dict[str, str]] | None = None,
    memory_context: str | None = None,   # ← nuovo, default None
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    sys_prompt = self._get_dynamic_system_prompt()  # ← variabile locale, non self._system_prompt
    if memory_context and sys_prompt:
        # Appendi DOPO il prompt dinamico (con data/ora), come sezione separata
        sys_prompt = f"{sys_prompt}\n\n{memory_context}"
    elif memory_context:
        sys_prompt = memory_context
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt})
    ...
```

**Aggiornare anche `LLMServiceProtocol`** in `backend/core/protocols.py` con lo stesso parametro `memory_context: str | None = None` per mantenere il contratto di tipo coerente con `AppContext`.

**Garanzia no-regression**: `memory_context=None` (default) → comportamento identico a prima. Tutti i test esistenti passano invariati.

---

#### 9.6 — Session Memory e Cleanup

**Session memory**: ricordi con `scope="session"` vengono creati automaticamente dal plugin con `expires_at = now() + timedelta(hours=session_ttl_hours)`. Alla ricerca, `MemoryService.search()` filtra via `WHERE expires_at IS NULL OR expires_at > NOW()`.

**Cleanup automatico**: `MemoryService` schedula un task background asincrono `_cleanup_loop()` che gira ogni 6 ore:

```python
async def _cleanup_loop(self) -> None:
    while True:
        await asyncio.sleep(6 * 3600)
        expired = await self._delete_expired()
        if expired > 0:
            logger.info("Memory cleanup: removed {} expired entries", expired)
        if self._config.auto_cleanup_days > 0:
            old = await self._delete_old_unaccessed(self._config.auto_cleanup_days)
            if old > 0:
                logger.info("Memory cleanup: removed {} stale entries", old)
```

Il task viene creato in `MemoryService.initialize()` via `asyncio.create_task()` e cancellato in `MemoryService.close()` — identico al pattern `TimerManager` in Fase 7.5.2.

---

#### 9.7 — REST API (`backend/api/routes/memory.py`)

Endpoint per la UI di gestione memoria (Fase 9 frontend):

```
GET  /api/memory                        — lista ricordi (paginazione + filtri)
POST /api/memory/search                 — ricerca semantica manuale (per UI)
DELETE /api/memory/{memory_id}          — cancella ricordo singolo
DELETE /api/memory/session              — cancella tutta la session memory
GET  /api/memory/stats                  — conteggio per scope/categoria, dimensione DB
```

Pattern identico agli endpoint esistenti (`/api/audit/confirmations`, `/api/chat/conversations`).

---

#### 9.8 — Frontend: Memory Manager UI

**Componente**: `MemoryManager.vue` — accessibile da Settings panel.

- Lista ricordi (paginata, filtrabile per categoria/scope)
- Pulsante "Dimentica" per cancellazione singola (con confirm dialog)
- Pulsante "Cancella sessione" per pulizia session memory
- Stats: N ricordi totali, dimensione DB, ultimo cleanup
- **Badge in ChatView**: piccola indicazione visiva quando ricordi rilevanti sono stati iniettati (opzionale, configurabile)

**Stato Pinia** (`memory` store):
```typescript
interface MemoryState {
  entries: MemoryEntry[]
  total: number
  stats: MemoryStats | null
  loading: boolean
}
```

**Nessuna modifica a store Pinia esistenti** — `memory` è uno store nuovo, standalone.

---

#### 9.9 — System Prompt Update (`config/system_prompt.md`)

Aggiungere regola di utilizzo memoria nella sezione `tools`:

```yaml
memory:
  remember: usa quando l'utente esprime preferenze, fornisce fatti su sé stesso, o chiede esplicitamente di ricordare qualcosa. NON salvare dati transitori (comandi singoli, risultati di ricerca).
  recall: usa SOLO se il contesto iniettato automaticamente non è sufficiente e hai bisogno di cercare qualcosa di specifico. Non chiamare recall per ogni messaggio.
  forget: usa SOLO su richiesta esplicita dell'utente.
  scope: usa 'session' per informazioni valide solo nella conversazione corrente; 'long_term' per tutto il resto.
```

---

#### 9.10 — Dipendenze e Compatibilità

**Nuove dipendenze** in `pyproject.toml`:

```toml
"sqlite-vec >= 0.1.6",       # SQLite vector extension (wheel per Windows incluso)
"fastembed >= 0.3",          # Fallback CPU embedding, no PyTorch
```

**Compatibilità PyInstaller** (Fase 8): `sqlite-vec` distribuisce wheel precompilati per Windows (`.dll`). L'estensione viene caricata con `sqlite3.load_extension(path)`. Il path dell'estensione deve essere risolto correttamente sia in dev (`importlib.resources`) che in PyInstaller bundle (`sys._MEIPASS`). Questo è documentato nel `MemoryService` code come `_resolve_vec_extension_path()`.

**Requisito Windows — `enable_load_extension`**: il modulo `sqlite3` standard di Python su Windows richiede una chiamata esplicita prima del load:
```python
conn.enable_load_extension(True)
conn.load_extension(str(_resolve_vec_extension_path()))
conn.enable_load_extension(False)  # re-disable per sicurezza
```
Se Python è compilato senza `SQLITE_ENABLE_LOAD_EXTENSION` (es. distributori che lo rimuovono per sicurezza), `MemoryService.initialize()` cattura `AttributeError` e fallisce con un errore diagnostico chiaro: `"sqlite-vec non caricabile: ricompilare Python con SQLITE_ENABLE_LOAD_EXTENSION=1 o usare il wheel uv/conda"`. Il wheel Python distribuito con `uv` (usato nel progetto) include il flag — nessun problema in pratica.

**DB separato**: `MemoryService` apre la propria connessione `aiosqlite` su `data/memory.db` (vedi `MemoryConfig.db_path`), separata da `data/omnia.db` (DB principale). Questo evita contaminazione delle migration SQLAlchemy con le tabelle virtuali sqlite-vec e permette di cancellare/ricreare la memoria senza toccare il DB principale.

**VRAM impact**:

| Configurazione | VRAM aggiuntiva |
|---|---|
| OpenAI embedding via LM Studio | 0 MB (modello già caricato o ~274 MB per nomic-embed-text) |
| fastembed fallback CPU | 0 MB VRAM (CPU-only) |
| sqlite-vec operazioni | 0 MB VRAM (SQLite CPU) |

**Budget VRAM aggiornato** (aggiornare tabella §VRAM):

| Componente | VRAM |
|---|---|
| ... (invariato) | ... |
| MemoryService (embedding via LM Studio) | ~0–274 MB (condiviso con LLM server) |

---

#### 9.11 — Test Suite Fase 9

- **Test `MemoryService`** (`tests/test_memory_service.py`):
  - `test_add_and_search`: add entry → search con query semantica → risultato trovato
  - `test_similarity_threshold`: entry poco rilevante → non restituita sotto threshold
  - `test_session_expiry`: entry session con `expires_at` passato → non restituita
  - `test_cleanup_expired`: mock clock → cleanup rimuove expired entries
  - `test_dimension_mismatch`: cambio `embedding_dim` → `MemoryDimensionMismatchError` chiaro
  - `test_disabled_service`: `memory.enabled=False` → service non inizializzato → nessun crash nel tool loop

- **Test `EmbeddingClient`** (`tests/test_embedding_client.py`):
  - `test_openai_success`: mock httpx → embedding restituito correttamente
  - `test_openai_failure_fastembed_fallback`: mock httpx `ConnectError` → fallback fastembed
  - `test_dimensions_consistent`: tutti i call sullo stesso modello restituiscono stessa dim

- **Test `MemoryPlugin`** (`tests/test_memory_plugin.py`):
  - `test_remember_tool`: chiama `remember` → `MemoryService.add()` chiamato con dati corretti
  - `test_recall_tool`: chiama `recall` → `MemoryService.search()` → risultati restituiti
  - `test_forget_requires_confirmation`: `forget` tool ha `requires_confirmation=True`
  - `test_memory_service_unavailable`: `ctx.memory_service = None` → tool restituisce errore graceful

- **Test context injection** (`tests/test_websocket.py` — estensione del file esistente):
  - `test_memory_injected_in_prompt`: memory_service con risultati → system prompt contiene `[RICORDI RILEVANTI]`
  - `test_no_injection_when_disabled`: `inject_in_context=False` → prompt invariato
  - `test_no_injection_when_no_results`: ricerca senza risultati → prompt invariato

- **Test REST API** (`tests/test_memory_api.py`):
  - List, search, delete, stats — pattern identico a `test_confirmation_audit.py`

- **Verifica no-regression** (eseguita PRIMA di ogni PR sulla fase 9):
  - tutta la suite esistente deve passare invariata (38 web_search + 24 pc_automation + 15 confirmation + ...)

---

#### 9.12 — File Structure Fase 9

```
backend/
├── services/
│   ├── memory_service.py      ← MemoryService (layer DB vettoriale)
│   └── embedding_client.py   ← EmbeddingClient (OpenAI + fastembed fallback)
├── plugins/
│   └── memory/
│       ├── __init__.py        ← import + PLUGIN_REGISTRY["memory"] = MemoryPlugin
│       └── plugin.py          ← MemoryPlugin con 5 tool
├── api/
│   └── routes/
│       └── memory.py          ← REST /api/memory/*
├── core/
│   ├── config.py              ← + MemoryConfig + OmniaConfig.memory field
│   ├── protocols.py           ← + MemoryServiceProtocol
│   └── app.py                 ← + MemoryService init nel lifespan
├── db/
│   └── models.py              ← + MemoryEntry SQLModel
└── tests/
    ├── test_memory_service.py
    ├── test_embedding_client.py
    ├── test_memory_plugin.py
    └── test_memory_api.py

frontend/src/renderer/src/
├── components/settings/
│   └── MemoryManager.vue
└── stores/
    └── memory.ts
```

---

#### 9.13 — Ordine di Implementazione Consigliato

1. **`EmbeddingClient`** — unit testabile in isolamento, zero dipendenze da resto
2. **`MemoryEntry` DB model** — aggiunta pura a `models.py`, zero modifica all'esistente
3. **`MemoryConfig`** — aggiunta a `config.py` e `default.yaml`
4. **`MemoryService`** — dipende da `EmbeddingClient` + DB
5. **Registrazione in `AppContext` e `app.py`** — wiring (dopo tutto il resto è pronto)
6. **`MemoryPlugin`** — dipende da `MemoryService` tramite context
7. **Context injection in `chat.py`** — modifica minimale, parametro opzionale in `build_messages()` + `LLMServiceProtocol`
8. **REST `/api/memory`** — endpoint CRUD (pattern già consolidato)
9. **Frontend `MemoryManager.vue`** — UI (indipendente dal backend)
10. **Test suite completa** — scritti in parallelo ai passi 1–9

---

#### 9.14 — Verifiche Fase 9

| Scenario | Comportamento atteso |
|---|---|
| "Ricorda che preferisco il terminale a Powershell" | LLM chiama `remember(content="...", category="preference")` → salvato |
| Sessione successiva: "Apri il terminale" | Context injection include preferenza → LLM apre correttamente senza ripetere la preferenza |
| "Dimentica le mie preferenze" | LLM chiama `recall(query="preferenze")` → trova le voci → chiama `forget()` per ognuna con conferma → rimosse |
| `memory.enabled=False` (default) | MemoryService non avviato (`ctx.memory_service = None`); i tool del plugin restituiscono `"Memory Service non attivo"` se il plugin è caricato, context injection saltata automaticamente; zero impatto su tutti i test esistenti |
| `memory` non in `plugins.enabled` | Tool LLM non disponibili; MemoryService può comunque girare (es. per future UI dirette); i due flag sono indipendenti |
| LM Studio offline durante embed | Fallback fastembed automatico, log warning, nessun crash |
| Cambio modello embedding (768→384 dim) | `MemoryDimensionMismatchError` con messaggio chiaro, nessuna corruzione dati |
| Conversazione di test senza `remember` | Nessun dato in memoria, zero inquinamento |

---

---

