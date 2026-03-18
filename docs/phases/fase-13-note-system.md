### Fase 13 — Note System (Obsidian-like)

> **Obiettivo**: aggiungere a OMNIA un sistema di note personali ispirato a Obsidian.
> Radicalmente distinto dal Memory Service (Fase 9): la memoria è automatica, semantica
> e invisibile all'utente (accumulata in background, iniettata nell'LLM context). Le
> **note** sono documenti Markdown intenzionalmente creati dall'utente o dall'LLM su
> esplicita istruzione, organizzati in cartelle e tag, con wikilinks ed editing diretto
> nella UI. Con Fase 13 OMNIA diventa anche un **vault di conoscenza personale** al
> fianco dell'assistente conversazionale.

- [x] NotesConfig in config.py + default.yaml — §13.1
- [x] NoteServiceProtocol in protocols.py — §13.2
- [x] AppContext.note_service field — §13.2
- [x] NoteService (aiosqlite + FTS5 + sqlite-vec CRUD) — §13.3
- [x] App lifespan wiring (startup init + shutdown close) — §13.3
- [x] NotesPlugin (6 tool, schemi JSON completi) — §13.4
- [x] REST API /api/notes (7 endpoint) — §13.5
- [x] OmniaEvent NOTE_* events in event_bus.py — §13.6
- [x] System prompt guidelines — §13.7
- [x] Frontend types/notes.ts + stores/notes.ts — §13.8
- [x] services/api.ts aggiornato (metodi notes) — §13.8
- [x] NotesPageView.vue + NotesBrowser.vue + NoteEditor.vue + NotesBacklinks.vue — §13.8
- [x] Router entry /notes + sidebar link (AppSidebar.vue) — §13.8
- [ ] Test suite (4 file, 40+ test case) — §13.9
- [x] Dependencies (sqlite-vec + fastembed già in pyproject.toml) — §13.10

---

#### 13.0 — Analisi Vincoli e Scelte Architetturali

**Perché il Note System è un `BaseService` e NON un plugin standalone:**
- Le note sono infrastruttura di conoscenza personale, con REST API indipendente e UI
  dedicata — esattamente come `MemoryService` o `TaskScheduler`
- Il service gestisce il DB direttamente, viene iniettato in `AppContext` e può essere
  consumato sia dal plugin che dagli endpoint REST
- Il plugin `notes` delega tutta la logica a `ctx.note_service` senza conoscere SQL o
  embedding — separazione responsabilità pulita, identica al pattern Fase 9

**Perché DB separato `data/notes.db` e non `data/omnia.db`:**
- La tabella virtuale FTS5 (`note_fts`) usa `content=note_entries` (external content FTS5),
  che richiede trigger DDL per il sync; SQLAlchemy non gestisce trigger né tabelle virtuali
- Le tabelle sqlite-vec (`note_vectors`) sono incompatibili con `SQLModel.metadata.create_all`
- Identica motivazione di `data/memory.db` — nessuna contaminazione delle migration Alembic
- `NoteService` apre la propria connessione `aiosqlite` su `data/notes.db` separata

**Perché `NoteEntry` è un `__slots__` dataclass e non un SQLModel:**
- Identica motivazione a `MemoryEntry` (Fase 9): il service usa raw `aiosqlite` + SQL,
  la rappresentazione Python è separata dallo schema SQLite (che include tabelle virtuali)
- SQLModel su DB separato richiederebbe un secondo engine SQLAlchemy — overhead inutile
- `NoteEntry` è usata solo come return type del service — nessuna feature ORM necessaria

**Perché sia FTS5 (full-text) sia sqlite-vec (semantico):**
- FTS5: ricerche precise (titolo, parole chiave esatte, filtri tag) — zero latency, zero embedding
- sqlite-vec: ricerche concettuali ("trova note su machine learning" anche senza la parola esatta)
  — richiede embedding, ma è opzionale (`embedding_enabled: bool` in config)
- Le due ricerche si fondono: FTS results first (più precisi), poi vec (più ampi),
  con dedup per ID — massima coverage senza duplicati

**Distinzione note vs memoria:**

| Aspetto          | Memory Service (Fase 9)       | Note System (Fase 13)                |
|------------------|-------------------------------|--------------------------------------|
| Origine          | Automatica (LLM decide)       | Intenzionale (utente/LLM su comando) |
| Formato          | Fatti brevi (≤ 1000 char)     | Documenti Markdown lunghi            |
| Organizzazione   | Categoria + scope             | Folder + tag + wikilinks             |
| UI               | MemoryManager (gestione)      | NoteEditor (editing Markdown diretto)|
| Ricerca          | Solo semantica                | Full-text + semantica                |
| LLM context      | Iniettato automaticamente     | Mai iniettato (solo su esplicit tool)|
| Lifecycle        | Auto-cleanup (TTL + days)     | Permanente fino a delete esplicito   |

---

#### 13.1 — NotesConfig (`backend/core/config.py`)

```python
class NotesConfig(BaseSettings):
    """Note system (Obsidian-like vault) configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_NOTES__")

    enabled: bool = False
    """Abilita il Note System. False di default (opt-in esplicito)."""

    db_path: str = "data/notes.db"
    """Path del file SQLite dedicato alle note (separato da omnia.db e memory.db)."""

    embedding_enabled: bool = True
    """Abilita ricerca semantica tramite EmbeddingClient (richiede LM Studio online
    o fastembed installato). Se False, solo FTS5 full-text search."""

    embedding_model: str = "nomic-embed-text"
    """Nome modello embedding per /v1/embeddings (stessa logica di MemoryConfig)."""

    embedding_dim: int = 768
    """Dimensione vettori embedding. Deve corrispondere al modello scelto."""

    embedding_fallback: bool = True
    """Se True, usa fastembed (CPU) come fallback se l'API embedding LM Studio non è disponibile
    (identico al campo `embedding_fallback` in `MemoryConfig`)."""

    max_content_chars_llm: int = 8000
    """Massimo caratteri del contenuto di una nota inviato all'LLM."""

    semantic_threshold: float = 0.70
    """Score minimo coseno per includere un risultato semantico (0.0–1.0)."""

    max_search_results: int = 20
    """Massimo risultati per query di ricerca (FTS + semantica combinata)."""
```

Aggiunta a `OmniaConfig` (dopo il campo `memory`):
```python
notes: NotesConfig = Field(default_factory=NotesConfig)
```

Config YAML entry (`config/default.yaml`):
```yaml
# Nuova sezione notes (dopo memory:):
notes:
  enabled: false
  db_path: "data/notes.db"
  embedding_enabled: true
  embedding_model: "nomic-embed-text"
  embedding_dim: 768
  embedding_fallback: true
  max_content_chars_llm: 8000
  semantic_threshold: 0.70
  max_search_results: 20

# In plugins.enabled, aggiungere (commentato per default-off):
# - notes  # abilitare con notes.enabled: true
```

---

#### 13.2 — NoteServiceProtocol + AppContext

Aggiunta in `backend/core/protocols.py` (dopo `MemoryServiceProtocol`):

```python
@runtime_checkable
class NoteServiceProtocol(Protocol):
    """Protocol for the Note Service (Obsidian-like note vault)."""

    async def initialize(self) -> None: ...
    async def create(
        self,
        title: str,
        content: str,
        folder_path: str = "",
        tags: list[str] | None = None,
    ) -> "NoteEntry": ...
    async def get(self, note_id: str) -> "NoteEntry | None": ...
    async def update(
        self,
        note_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        folder_path: str | None = None,
        tags: list[str] | None = None,
        pinned: bool | None = None,
    ) -> "NoteEntry | None": ...
    async def delete(self, note_id: str) -> bool: ...
    async def search(
        self,
        query: str,
        folder: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list["NoteEntry"]: ...
    async def list(
        self,
        folder: str | None = None,
        tags: list[str] | None = None,
        pinned_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> "tuple[list[NoteEntry], int]": ...
    async def close(self) -> None: ...
```

Aggiunta in `backend/core/context.py` (campo opzionale, dopo `memory_service`):
```python
note_service: NoteServiceProtocol | None = None
```

---

#### 13.3 — NoteService (`backend/services/note_service.py`)

**Ruolo**: layer di accesso alle note. Non conosce tool, LLM o plugin — solo CRUD con
FTS5 + sqlite-vec. Pattern identico a `MemoryService` (Fase 9).

**`NoteEntry` dataclass**:
```python
@dataclasses.dataclass(slots=True)
class NoteEntry:
    """In-memory representation of a single note. NOT a SQLModel table."""
    id: str               # uuid str
    title: str
    content: str          # Markdown
    folder_path: str      # es. "lavoro/progetti" (default "")
    tags: list[str]       # es. ["python", "ai"]
    wikilinks: list[str]  # estratti automaticamente da [[Titolo]] nel content
    pinned: bool
    created_at: str       # ISO 8601 UTC
    updated_at: str       # ISO 8601 UTC
```

**Estrazione wikilinks**: `NoteService` include un metodo privato
`_extract_wikilinks(content: str) -> list[str]` che usa regex `\[\[(.+?)\]\]`
per estrarre i titoli referenziati. Viene chiamato automaticamente in `create()` e
`update()` ogni volta che il contenuto cambia — nessuna interazione LLM richiesta.
I wikilinks estratti vengono salvati nella colonna `wikilinks` come JSON array.

> **Nota v1**: `wikilinks` sono estratti e persistiti ma non risolti in link navigabili
> nell'editor. La navigazione via click su `[[Titolo]]` e il pannello backlinks
> appartengono alla UI (§13.8). La Graph View è §13.14 (v2 feature).

**Schema DB** (creato da `NoteService.initialize()` via raw SQL — non SQLAlchemy):

```sql
-- Tabella principale
CREATE TABLE IF NOT EXISTS note_entries (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    folder_path TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',     -- JSON array
    wikilinks   TEXT NOT NULL DEFAULT '[]',     -- JSON array, auto-extracted via regex
    pinned      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_note_folder  ON note_entries(folder_path);
CREATE INDEX IF NOT EXISTS ix_note_pinned  ON note_entries(pinned);
CREATE INDEX IF NOT EXISTS ix_note_updated ON note_entries(updated_at);

-- Tabella vettori (sqlite-vec, creata solo se embedding_enabled)
CREATE VIRTUAL TABLE IF NOT EXISTS note_vectors USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[768] distance_metric=cosine
);

-- FTS5 external content (keyword search)
CREATE VIRTUAL TABLE IF NOT EXISTS note_fts USING fts5(
    title, content,
    content=note_entries,
    content_rowid=rowid
);
-- Trigger per sync automatico FTS ↔ note_entries
CREATE TRIGGER IF NOT EXISTS note_fts_insert AFTER INSERT ON note_entries BEGIN
    INSERT INTO note_fts(rowid, title, content)
    VALUES (NEW.rowid, NEW.title, NEW.content);
END;
CREATE TRIGGER IF NOT EXISTS note_fts_update AFTER UPDATE ON note_entries BEGIN
    INSERT INTO note_fts(note_fts, rowid, title, content)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.content);
    INSERT INTO note_fts(rowid, title, content)
    VALUES (NEW.rowid, NEW.title, NEW.content);
END;
CREATE TRIGGER IF NOT EXISTS note_fts_delete AFTER DELETE ON note_entries BEGIN
    INSERT INTO note_fts(note_fts, rowid, title, content)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.content);
END;
```

**Struttura `NoteService`**:
```
NoteService
├── __init__(config, llm_base_url)  — config + LLM base URL; NESSUNA I/O (identico a MemoryService)
├── initialize()                — carica sqlite-vec se enabled, crea tabelle e indici,
│                                 crea EmbeddingClient (OpenAI + fastembed fallback)
├── create(title, content, ...) → NoteEntry — insert + embed + FTS auto (trigger)
├── get(note_id)                → NoteEntry | None
├── update(note_id, **fields)   → NoteEntry | None — UPDATE + RE-embed se content cambia
├── delete(note_id)             → bool — DELETE cascades a note_vectors e FTS (trigger)
├── search(query, folder, tags, limit) → list[NoteEntry]
│   ├── _fts_search(query)      → list[str]          — IDs da FTS5 MATCH
│   └── _vec_search(query, k)   → list[str]          — IDs da note_vectors MATCH
│   ─── merge(fts_ids, vec_ids) → list[NoteEntry]    — union + dedup (FTS first) + filter
├── list(folder, tags, pinned_only, limit, offset) → (list[NoteEntry], int)
└── close()                     — chiude connessione aiosqlite
```

**`NoteService.search()` — fusione FTS + semantico (identico al pattern MemoryService.search)**:

```python
async def search(
    self,
    query: str,
    folder: str | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
) -> list[NoteEntry]:
    seen_ids: set[str] = set()
    merged: list[NoteEntry] = []

    # 1. FTS5 full-text search (preciso, zero latency)
    fts_ids = await self._fts_search(query, limit)
    for note_id in fts_ids:
        entry = await self.get(note_id)
        if entry and self._matches_filters(entry, folder, tags):
            seen_ids.add(note_id)
            merged.append(entry)

    # 2. Semantic search (opzionale, se embedding disponibile)
    if self._embedding and len(merged) < limit:
        try:
            vec = await self._embedding.encode(query)
            vec_ids = await self._vec_search(vec, limit * 2)
            for note_id in vec_ids:
                if note_id in seen_ids:
                    continue
                entry = await self.get(note_id)
                if entry and self._matches_filters(entry, folder, tags):
                    seen_ids.add(note_id)
                    merged.append(entry)
                    if len(merged) >= limit:
                        break
        except Exception as exc:
            logger.warning("NoteService semantic search failed: {}", exc)

    return merged[:limit]
```

**`_resolve_vec_extension_path()`**: identica a `MemoryService` — gestisce dev vs PyInstaller bundle.

**`initialize()`** — abilita e carica sqlite-vec (solo se `embedding_enabled`):
```python
async def initialize(self) -> None:
    async with aiosqlite.connect(self._db_path) as conn:
        if self._config.embedding_enabled:
            conn.enable_load_extension(True)
            conn.load_extension(str(_resolve_vec_extension_path()))
            conn.enable_load_extension(False)
        # Create tables, indexes, triggers
        await conn.executescript(_SCHEMA_SQL)
        await conn.commit()
    # EmbeddingClient: same pattern as MemoryService (OpenAI + fastembed fallback)
    if self._config.embedding_enabled:
        self._embedding = EmbeddingClient(
            base_url=self._llm_base_url,  # stored in __init__(config, llm_base_url)
            model=self._config.embedding_model,
            dim=self._config.embedding_dim,
        )
```

**Startup in `app.py`** (dopo `MemoryService` init, prima di `PluginManager`):
```python
if config.notes.enabled:
    from backend.services.note_service import NoteService
    note_service = NoteService(config.notes, config.llm.base_url)
    try:
        await note_service.initialize()
        ctx.note_service = note_service
        logger.info("Note service started")
    except Exception as exc:
        logger.warning("Note service failed to start: {}", exc)
        await note_service.close()  # cleanup parziale (identico a MemoryService)
```

**Shutdown** (nella sezione shutdown, accanto a `memory_service`):
```python
if ctx.note_service:
    try:
        await ctx.note_service.close()
    except Exception as exc:
        logger.error("Note service shutdown error: {}", exc)
```

---

#### 13.4 — NotesPlugin (`backend/plugins/notes/`)

**Ruolo**: espone 6 tool LLM per interagire con le note. Non contiene logica DB — delega
tutto a `ctx.note_service`. Pattern identico a `MemoryPlugin` (Fase 9).

```
backend/plugins/notes/
├── __init__.py    — import + PLUGIN_REGISTRY["notes"] = NotesPlugin
└── plugin.py      — NotesPlugin(BasePlugin)
```

`__init__.py`:
```python
"""O.M.N.I.A. — Notes plugin package.

Importing this module registers NotesPlugin in the static PLUGIN_REGISTRY.
"""
from backend.core.plugin_manager import PLUGIN_REGISTRY
from backend.plugins.notes.plugin import NotesPlugin  # noqa: F401

PLUGIN_REGISTRY["notes"] = NotesPlugin
```

**Tool definitions**:

| Tool | risk_level | requires_confirmation | Descrizione |
|---|---|---|---|
| `create_note` | `safe` | `False` | Crea una nuova nota Markdown con titolo, contenuto, cartella e tag |
| `read_note` | `safe` | `False` | Legge il contenuto completo di una nota per ID |
| `update_note` | `safe` | `False` | Aggiorna titolo, contenuto, cartella, tag o stato pinned di una nota |
| `delete_note` | `medium` | `True` | Elimina una nota in modo permanente (irreversibile) |
| `search_notes` | `safe` | `False` | Ricerca FTS5 + semantica nelle note |
| `list_notes` | `safe` | `False` | Elenca note con filtri opzionali per cartella, tag, pinned |

**Schema tool `create_note`**:
```json
{
  "type": "object",
  "properties": {
    "title": {
      "type": "string",
      "description": "Titolo conciso della nota.",
      "maxLength": 255
    },
    "content": {
      "type": "string",
      "description": "Corpo della nota in formato Markdown.",
      "maxLength": 50000
    },
    "folder_path": {
      "type": "string",
      "description": "Cartella di destinazione (es. 'lavoro/progetti'). Default: root.",
      "default": ""
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Lista tag per categorizzare la nota.",
      "default": []
    }
  },
  "required": ["title", "content"]
}
```

**Schema tool `search_notes`**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Testo da cercare nelle note (full-text e semantico).",
      "maxLength": 500
    },
    "folder": {
      "type": "string",
      "description": "Filtra per cartella (opzionale)."
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filtra per tag (opzionale, AND logic)."
    },
    "limit": {
      "type": "integer",
      "default": 10,
      "minimum": 1,
      "maximum": 20
    }
  },
  "required": ["query"]
}
```

**Schema tool `read_note`**:
```json
{
  "type": "object",
  "properties": {
    "note_id": {
      "type": "string",
      "description": "UUID della nota da leggere (ottenuto tramite search_notes o list_notes)."
    }
  },
  "required": ["note_id"]
}
```

**Schema tool `update_note`**:
```json
{
  "type": "object",
  "properties": {
    "note_id": {
      "type": "string",
      "description": "UUID della nota da aggiornare."
    },
    "title": {
      "type": "string",
      "description": "Nuovo titolo (opzionale, invariato se omesso).",
      "maxLength": 255
    },
    "content": {
      "type": "string",
      "description": "Nuovo corpo Markdown (opzionale, invariato se omesso).",
      "maxLength": 50000
    },
    "folder_path": {
      "type": "string",
      "description": "Nuova cartella di destinazione (opzionale)."
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Nuova lista tag completa, sostituisce quella esistente (opzionale)."
    },
    "pinned": {
      "type": "boolean",
      "description": "Nuovo stato pinned (opzionale)."
    }
  },
  "required": ["note_id"]
}
```

**Schema tool `delete_note`**:
```json
{
  "type": "object",
  "properties": {
    "note_id": {
      "type": "string",
      "description": "UUID della nota da eliminare definitivamente."
    }
  },
  "required": ["note_id"]
}
```

**Schema tool `list_notes`**:
```json
{
  "type": "object",
  "properties": {
    "folder": {
      "type": "string",
      "description": "Filtra per cartella (opzionale, es. 'lavoro/progetti')."
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filtra per tag (opzionale, AND logic — deve avere TUTTI i tag)."
    },
    "pinned_only": {
      "type": "boolean",
      "description": "Se true, restituisce solo le note pinnate.",
      "default": false
    },
    "limit": {
      "type": "integer",
      "description": "Massimo risultati (1–50). Default: 20.",
      "default": 20,
      "minimum": 1,
      "maximum": 50
    }
  }
}
```

**Regola `requires_confirmation=False` per operazioni non distruttive**: `create_note`,
`read_note`, `update_note`, `search_notes`, `list_notes` sono tutte reversibili o
read-only — richiedere conferma ogni volta renderebbe l'esperienza insopportabile.
`delete_note` è irreversibile → `requires_confirmation=True`, `risk_level="medium"`.

**Edge case**: se `ctx.note_service is None` (servizio non avviato o `notes.enabled=False`) →
tutti i tool restituiscono `ToolResult(success=False, error_message="Note Service non attivo.
Abilitare notes.enabled: true in config.")`.

---

#### 13.5 — REST API (`backend/api/routes/notes.py`)

Endpoint per la UI di gestione note (pattern identico a `/api/memory`):

```
GET    /api/notes                  — lista note (filtri query string: folder, tags, pinned, q, limit, offset)
POST   /api/notes                  — crea nota
GET    /api/notes/{note_id}        — dettaglio nota singola
PUT    /api/notes/{note_id}        — aggiorna nota
DELETE /api/notes/{note_id}        — elimina nota
POST   /api/notes/search           — ricerca semantica + FTS (body JSON)
GET    /api/notes/folders          — lista cartelle con conteggio note
```

```python
router = APIRouter(prefix="/notes", tags=["notes"])
```

Registrazione in `backend/api/routes/__init__.py`:
```python
# 1. Aggiungere 'notes' all'import esistente (unica riga con tutti i moduli):
from backend.api.routes import audit, cad, calendar, chat, config, events, mcp, mcp_memory, memory, models, notes, plugins, settings, voice

# 2. Aggiungere include_router dopo memory.router:
router.include_router(notes.router)  # dopo: router.include_router(memory.router)
```

> **⚠️ Ordine definizione endpoint critico**: in FastAPI, `GET /api/notes/folders`
> (path statico) **deve essere definito prima** di `GET /api/notes/{note_id}` (path dinamico)
> nel file `notes.py`, altrimenti FastAPI matcha `"folders"` come `note_id`.

Ogni endpoint usa `ctx: AppContext = Depends(get_context)` e restituisce `503` se
`ctx.note_service is None`. Valida `note_id` come stringa UUID (anti-IDOR).

---

#### 13.6 — OmniaEvent Updates (`backend/core/event_bus.py`)

Tre nuovi eventi aggiunti al `OmniaEvent` StrEnum (senza modificare quelli esistenti):

```python
# Note events (Phase 13)
NOTE_CREATED = "note.created"
"""Emesso con note_id=str, title=str alla creazione di una nota."""

NOTE_UPDATED = "note.updated"
"""Emesso con note_id=str, title=str all'aggiornamento di una nota."""

NOTE_DELETED = "note.deleted"
"""Emesso con note_id=str alla cancellazione di una nota."""
```

Gli eventi vengono emessi dal plugin `notes` dopo ogni tool call write (come il pattern
`calendar.reminder` in `CalendarPlugin`). Il plugin non ha dipendenze dirette sull'EventBus —
li emette tramite `ctx.event_bus.emit(OmniaEvent.NOTE_CREATED, note_id=entry.id, ...)`.

---

#### 13.7 — System Prompt Update (`config/system_prompt.md`)

Aggiungere sezione nella sezione `tools`:

```yaml
notes:
  distinction: "Le NOTE sono documenti Markdown intenzionali creati su richiesta esplicita.
    DIVERSO dal remember() che salva fatti brevi automaticamente. Usa le note per contenuti
    lunghi, strutturati, che l'utente vorrà rivedere e modificare direttamente nell'UI."
  create_note: "usa quando l'utente vuole creare un documento (ricetta, riassunto, schema,
    piano di progetto, ecc.). Scegli titolo chiaro e folder_path coerente con il contenuto."
  read_note: "usa per leggere/riepilogare una nota specifica. Prima usa search_notes per
    trovare l'ID corretto se non lo conosci."
  update_note: "usa per aggiornare contenuto di una nota esistente. MAI creare una nota
    duplicata se la nota già esiste — usa update_note invece."
  search_notes: "usa prima di read o update per trovare note per tema. Restituisce titoli
    e ID — poi leggi con read_note solo se serve il contenuto completo."
  delete_note: "usa SOLO su richiesta esplicita dell'utente. Richiede conferma utente."
  list_notes: "usa per mostrare l'organizzazione del vault (cartelle, tag, note pinnate)."
```

---

#### 13.8 — Frontend

**Nuovi tipi TypeScript** (`frontend/src/renderer/src/types/notes.ts`):

```typescript
/** A single note in the vault. Mirrors backend NoteEntry. */
export interface Note {
  id: string
  title: string
  content: string       // Markdown
  folder_path: string
  tags: string[]
  wikilinks: string[]   // titoli estratti da [[...]], usati per backlinks panel
  pinned: boolean
  created_at: string    // ISO 8601
  updated_at: string
}

export interface NoteSearchResult {
  notes: Note[]
  total: number
  query: string
}

export interface NoteFolder {
  path: string
  count: number
  children: NoteFolder[]
}
```

**Pinia store** (`frontend/src/renderer/src/stores/notes.ts`):

Usa **Setup API** (`defineStore('notes', () => {...})`), identico a `stores/memory.ts`.
Nessuna Options API. Stato tramite `ref<T>()`, azioni come `async function`.

```typescript
// Pattern Setup API (come stores/memory.ts):
export const useNotesStore = defineStore('notes', () => {
  // state — tutti ref()
  const notes = ref<Note[]>([])
  const total = ref<number>(0)
  const currentNote = ref<Note | null>(null)
  const folders = ref<NoteFolder[]>([])
  const activeFolder = ref<string | null>(null)
  const activeTags = ref<string[]>([])
  const searchQuery = ref<string>('')
  const loading = ref(false)
  const error = ref<string | null>(null)

  // actions — async functions con try/catch + finally { loading.value = false }
  // Tutte chiamano api.ts (mai fetch diretta) — stesso pattern di useMemoryStore:
  // loadNotes(filters?)     — GET /api/notes      (via api.getNotes)
  // loadNote(id)            — GET /api/notes/{id} (via api.getNote)
  // createNote(req)         — POST /api/notes     (via api.createNote)
  // updateNote(id, changes) — PUT /api/notes/{id} (via api.updateNote)
  // deleteNote(id)          — DELETE /api/notes/{id} (via api.deleteNote)
  // searchNotes(q, filters) — POST /api/notes/search (via api.searchNotes)
  // loadFolders()           — GET /api/notes/folders (via api.getNoteFolders)

  return { notes, total, currentNote, folders, activeFolder, activeTags,
           searchQuery, loading, error, loadNotes, loadNote, createNote,
           updateNote, deleteNote, searchNotes, loadFolders }
})
```

> **`services/api.ts` — aggiornamento richiesto**: aggiungere i metodi notes al client
> centralizzato (`api.getNotes`, `api.getNote`, `api.createNote`, `api.updateNote`,
> `api.deleteNote`, `api.searchNotes`, `api.getNoteFolders`) seguendo esattamente
> il pattern dei metodi memory (`api.getMemories`, `api.searchMemories`, ecc.).
> Il store non chiama mai `fetch()` direttamente.

**Componenti Vue** (in `frontend/src/renderer/src/`):

1. **`views/NotesPageView.vue`** — vista principale a tre colonne
   - Stesso contenitore minimale di `CalendarPageView.vue` (lazy-load sub-componenti)
   - Layout flex-row: `NotesBrowser.vue` (280px, fisso) + `NoteEditor.vue` (flex-1) +
     `NotesBacklinks.vue` (240px, collassabile, visibile solo quando una nota è aperta)

2. **`components/notes/NotesBrowser.vue`**:
   - Folder tree navigabile (click → filtra per cartella; cartelle annidate con indent)
   - Tag cloud cliccabili (filtro per tag, multiple selection con toggle)
   - Lista note con titolo + anteprima 2 righe del contenuto + timestamp relativo
   - Note pinnate in cima con indicatore visivo (icona 📌)
   - Input ricerca con debounce 300ms → `store.searchNotes(query)` → lista reagisce live
   - Pulsante "Nuova nota" → `store.createNote({ title: 'Senza titolo', content: '', folder_path: activeFolder })` → apre la nota nel NoteEditor
   - Nessuno stato locale: tutto da `useNotesStore()` (cartella attiva, tag attivi, note filtrate)

3. **`components/notes/NoteEditor.vue`**:
   - `<textarea>` monospace per editing Markdown raw (v1 — nessun rich editor WYSIWYG)
   - Toggle preview (pulsante nel header) → mostra rendered HTML via `useMarkdown(content)`
     (composable già esistente in `composables/useMarkdown.ts`)
   - Header: input titolo inline editabile, folder selector `<select>`, tag chips con
     aggiunta/rimozione inline (Enter per aggiungere, × per rimuovere)
   - Autosave: `watch(content, debounce(() => store.updateNote(id, { content }), 800))`
   - Indicatore stato: `"Salvato ✓"` / `"Salvataggio…"` nel header (stato locale reattivo)
   - Pulsante pin/unpin + pulsante elimina (apre `useModal` confirm dialog — composable già esistente)
   - I wikilinks `[[Titolo]]` nel testo sono **non-cliccabili in v1** (testo puro nella textarea)

4. **`components/notes/NotesBacklinks.vue`** *(nuovo, collassabile)*:
   - Mostra le note che contengono `[[Titolo della nota corrente]]` nei loro `wikilinks[]`
   - Dati: `store.notes.filter(n => n.wikilinks.includes(currentNote.title))` — zero chiamate API extra
   - Lista cliccabile → click → `store.loadNote(id)` → apre la nota referenziante
   - Visibile solo quando `currentNote !== null`; collassabile con toggle (titolo: "Backlinks")
   - In assenza di backlinks: placeholder "Nessuna nota fa riferimento a questa"

4. **Router entry** (`frontend/src/renderer/src/router/index.ts`):
   ```typescript
   {
     path: '/notes',
     name: 'notes',
     component: () => import('../views/NotesPageView.vue')
   }
   ```
   Aggiungere alla lista `routes[]` dopo la voce `calendar`.

5. **Sidebar link** (`components/sidebar/AppSidebar.vue`): aggiungere nella sezione `<nav>`
   della sidebar, che contiene già i link per `/settings`, `/assistant` e `/hybrid`.
   Il calendario **non** ha un link diretto nella nav (usa `CalendarWidget` con
   `router.push()` interno) — le note invece usano un link esplicito nella nav:
   ```vue
   <router-link to="/notes" class="sidebar__link" active-class="sidebar__link--active">
     <span class="sidebar__link-icon">📝</span>
     <span class="sidebar__link-label">Note</span>
   </router-link>
   ```

---

#### 13.9 — Test Suite Fase 13

**`backend/tests/test_note_service.py`**:
- `test_create_and_get`: crea nota → get per ID → tutti i campi corretti
- `test_update_note_fields`: crea → update titolo + tags → get → valori aggiornati
- `test_wikilinks_extracted_on_create`: crea nota con `[[Link A]]` nel content → wikilinks==["Link A"]
- `test_wikilinks_updated_on_content_change`: update content con nuovo `[[Link B]]` → wikilinks aggiornati
- `test_delete_note`: crea → delete → get restituisce `None`
- `test_fts_search_finds_match`: crea nota con keyword → search query → trovata
- `test_fts_search_no_match`: search query irrilevante → lista vuota
- `test_semantic_search_mock`: mock EmbeddingClient → search → risultato sopra threshold
- `test_semantic_threshold_filtered`: score coseno < threshold → non restituito
- `test_list_folder_filter`: 3 note in cartelle diverse → `list(folder="lavoro")` → solo 1
- `test_list_tag_filter`: note con tag diversi → filtro tag → solo matching
- `test_list_pinned_only`: pin nota → `list(pinned_only=True)` → solo pinnate
- `test_embedding_disabled_no_vec`: `embedding_enabled=False` → init senza sqlite-vec load
- `test_service_disabled_no_crash`: `notes.enabled=False` → service non inizializzato, zero crash

**`backend/tests/test_note_plugin.py`**:
- `test_create_note_tool`: chiama `create_note` → `NoteService.create()` → `ToolResult(success=True)`
- `test_read_note_existing`: chiama `read_note` con ID valido → contenuto nel result
- `test_read_note_not_found`: ID inesistente → `ToolResult(success=False)` con error_message
- `test_update_note_tool`: `update_note` con nuovi campi → `NoteService.update()` chiamato
- `test_delete_note_requires_confirmation`: `delete_note` ha `requires_confirmation=True`
- `test_search_notes_delegates`: `search_notes` → `NoteService.search()` → risultati JSON
- `test_list_notes_delegates`: `list_notes` → `NoteService.list()` → lista JSON
- `test_service_unavailable_all_tools`: `ctx.note_service = None` → tutti i tool errore graceful

**`backend/tests/test_notes_api.py`**:
- CRUD completo via `AsyncClient` (pattern identico a `test_memory_api.py`)
- `test_list_with_folder_filter`: `GET /api/notes?folder=lavoro` → solo note in quella cartella
- `test_search_endpoint`: `POST /api/notes/search` con `{"query": "python"}` → risultati
- `test_get_folders`: `GET /api/notes/folders` → struttura ad albero cartelle
- `test_note_id_invalid`: UUID non valido → `422 Unprocessable Entity`
- `test_service_unavailable_503`: `ctx.note_service = None` → `503 Service Unavailable`

**`backend/tests/test_note_events.py`** (integrazione EventBus):
- `test_note_created_event`: `create_note` tool → evento `NOTE_CREATED` emesso sul bus
- `test_note_updated_event`: `update_note` tool → evento `NOTE_UPDATED` emesso
- `test_note_deleted_event`: `delete_note` tool → evento `NOTE_DELETED` emesso

**Verifica no-regression** (pre-PR): tutta la suite esistente deve passare invariata.

---

#### 13.10 — Dipendenze e Compatibilità

**Nessuna nuova dipendenza** — tutto già presente in `pyproject.toml`:
- `sqlite-vec >= 0.1.6` — già installato per `MemoryService` (Fase 9)
- `fastembed >= 0.3` — già installato come fallback embedding (Fase 9)
- `aiosqlite` — già presente (usato da `MemoryService` e da `MemoryService`)

**Compatibilità PyInstaller**: identica a `MemoryService` — `_resolve_vec_extension_path()`
gestisce dev (`importlib.resources`) e bundle PyInstaller (`sys._MEIPASS`).

**VRAM impact**:
| Configurazione | VRAM aggiuntiva |
|---|---|
| Note FTS5 search only | 0 MB — SQLite CPU puro |
| Note semantic search via LM Studio | 0 MB (condiviso con MemoryService se embedding già caricato) |
| Note semantic search via fastembed | 0 MB VRAM (CPU-only) |

---

#### 13.11 — File Structure Fase 13

```
backend/
├── services/
│   └── note_service.py              ← NoteService (aiosqlite + FTS5 + sqlite-vec)
├── plugins/
│   └── notes/
│       ├── __init__.py              ← import + PLUGIN_REGISTRY["notes"] = NotesPlugin
│       └── plugin.py               ← NotesPlugin con 6 tool
├── api/
│   └── routes/
│       └── notes.py                ← REST /api/notes/*
├── core/
│   ├── config.py                   ← + NotesConfig + OmniaConfig.notes field
│   ├── protocols.py                ← + NoteServiceProtocol
│   ├── context.py                  ← + note_service: NoteServiceProtocol | None = None
│   ├── event_bus.py                ← + NOTE_CREATED / NOTE_UPDATED / NOTE_DELETED
│   └── app.py                      ← + NoteService init nel lifespan
└── tests/
    ├── test_note_service.py
    ├── test_note_plugin.py
    ├── test_notes_api.py
    └── test_note_events.py

frontend/src/renderer/src/
├── services/
│   └── api.ts                      ← + metodi notes (getNotes, getNote, createNote, updateNote,
│                                       deleteNote, searchNotes, getNoteFolders)
├── types/
│   └── notes.ts                    ← Note, NoteSearchResult, NoteFolder types
├── stores/
│   └── notes.ts                    ← Pinia notes store (Setup API)
├── views/
│   └── NotesPageView.vue           ← Vista split (browser + editor)
├── components/
│   ├── sidebar/
│   │   └── AppSidebar.vue          ← + router-link /notes nella sezione <nav>
│   └── notes/
│       ├── NotesBrowser.vue        ← Lista note: folder tree + tag cloud + ricerca
│       ├── NoteEditor.vue          ← Editor Markdown + preview + autosave + header
│       └── NotesBacklinks.vue      ← Pannello backlinks (note che puntano alla corrente)

config/
├── default.yaml                    ← + sezione notes: + entry commentata plugins.enabled
└── system_prompt.md                ← + sezione tools.notes con guidelines
```

---

#### 13.14 — Graph View (v2 feature — non implementata in Fase 13)

> **Nota**: la Graph View è una funzionalità v2 pianificata, descritta qui per chiarire
> il perché `wikilinks` è già persistito nel DB fin dalla v1.

**Obiettivo**: visualizzare le note come nodi in un grafo interattivo, con archi che
rappresentano i wikilinks `[[Titolo]]`. Ispirato alla Graph View di Obsidian.

**Architettura v2** (quando implementata):
- **Nuovo endpoint REST**: `GET /api/notes/graph` → restituisce
  `{ nodes: [{id, title, folder_path}], edges: [{source_id, target_id}] }`
  Il backend risolve `wikilinks[]` (titoli) in ID reali con una query SQLite.
- **Nuovo componente**: `components/notes/NotesGraphView.vue`
  — usa `cytoscape.js` o `d3-force` per rendering
  — nodi colorati per cartella, dimensione proporzionale al numero di backlinks in entrata
  — click su nodo → `store.loadNote(id)` → apre la nota nel NoteEditor
- **Nuovo tab** in `NotesPageView.vue`: toggle tra lista (`NotesBrowser`) e grafo
  (`NotesGraphView`) — stesso pattern del toggle preview in `NoteEditor`

**Perché non in Fase 13**: richiede dipendenza JS aggiuntiva (cytoscape/d3) e logica
di risoluzione titoli→ID nel backend. Il DB è già pronto (`wikilinks` persistiti) —
il costo aggiuntivo è solo UI, adottabile come pull request autonomo.

---

#### 13.12 — Ordine di Implementazione Consigliato

1. **`NotesConfig`** in `config.py` + `default.yaml` — aggiunta pura, zero dipendenze
2. **`OmniaEvent` note events** in `event_bus.py` — aggiunta pura all'enum
3. **`NoteEntry` dataclass** in `note_service.py` — zero dipendenze dal resto
4. **`NoteService`** completo — dipende da `aiosqlite` + `EmbeddingClient` (già presente)
5. **`NoteServiceProtocol`** in `protocols.py` + campo `AppContext.note_service`
6. **Wiring in `app.py`** — init `NoteService` nel lifespan
7. **`NotesPlugin`** — dipende da `NoteService` tramite context
8. **Route `notes.py`** + registrazione in `routes/__init__.py`
9. **Frontend `types/notes.ts` + `stores/notes.ts`** — tipi e store Pinia
10. **Aggiornamento `services/api.ts`** — metodi notes (getNotes, getNote, createNote, updateNote, deleteNote, searchNotes, getNoteFolders)
11. **`NotesBrowser.vue` + `NoteEditor.vue` + `NotesBacklinks.vue`** — componenti standalone
12. **`NotesPageView.vue`** — assembla browser + editor + backlinks
13. **Router entry + sidebar link** — aggiunta route `/notes`
14. **`config/system_prompt.md`** — guidelines tool notes
15. **Test suite completa** — scritti in parallelo ai passi 1–14

---

#### 13.13 — Verifiche Fase 13

| Scenario | Comportamento atteso |
|---|---|
| "Crea una nota con la ricetta della carbonara" | LLM chiama `create_note(title="Ricetta Carbonara", content="...", folder_path="cucina", tags=["ricette"])` → nota creata → ID restituito |
| "Trova le mie note su Python" | LLM chiama `search_notes(query="Python")` → lista titoli + ID → riassume risultati |
| "Leggi la nota sulla carbonara" | LLM: `search_notes("carbonara")` → trova ID → `read_note(id)` → contenuto troncato a `max_content_chars_llm` |
| "Aggiorna la ricetta: aggiungi guanciale 150g" | `read_note` → `update_note(id, content="...aggiornato...")` → salvato |
| "Elimina la nota sulla carbonara" | `delete_note` → `requires_confirmation=True` → dialog frontend → approvazione → eliminata |
| UI: click nota in NotesBrowser | Nota si apre in NoteEditor; modifica → autosave dopo 800ms → indicatore "Salvato ✓" |
| UI: nuova nota da pulsante | Nota vuota creata nella cartella attiva → focus su campo titolo |
| UI: ricerca "pasta" | Debounce 300ms → `searchNotes("pasta")` → lista aggiornata in tempo reale |
| `notes.enabled=False` (default) | NoteService non avviato; tool restituiscono errore graceful; REST → 503; zero impatto test esistenti |
| `notes` non in `plugins.enabled` | Tool LLM non disponibili; NoteService puede funzionare (REST attiva); i due flag sono indipendenti |
| `embedding_enabled=False` | Solo FTS5 search; nessun sqlite-vec caricato; funziona senza LM Studio |
| LM Studio offline durante creazione | Nota creata senza embedding vector; search semantica non disponibile; log warning; FTS funziona |
| 1000+ note nel vault | Paginazione via `limit/offset`; indici SQLite → query O(log n); frontend scroll virtuale futuro v2 |

---

