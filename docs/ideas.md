# OMNIA — Feature Ideas

> Idee brainstormate per estendere OMNIA con nuove funzionalità.
> Le prime cinque sono state analizzate in dettaglio con architettura, dipendenze
> e strategia di integrazione. Il resto costituisce una backlog di idee per fasi future.

---

## Idee Analizzate in Dettaglio

### 1. Note System (Obsidian-like)

**Stato**: pianificato → **Fase 13** di `PROJECT.md`

#### Descrizione

Sistema di note personali Markdown ispirato a Obsidian. Radicalmente diverso dal
`MemoryService` (Fase 9): la memoria è automatica, semantica e invisible all'utente;
le note sono documenti **intenzionalmente creati**, organizzati in cartelle e tag,
con editing diretto nell'UI e supporto a wikilinks/backlinks.

#### Architettura proposta

- **`NoteService`** — core service (pattern `MemoryService`), gestisce `data/notes.db`
  con SQLite FTS5 (full-text keyword) + sqlite-vec (ricerca semantica opzionale)
- **`NoteEntry`** — dataclass `__slots__` (non SQLModel — sqlite-vec incompatibile con SQLAlchemy)
- **`NotesPlugin`** — 6 tool LLM (`create_note`, `read_note`, `update_note`, `delete_note`,
  `search_notes`, `list_notes`)
- **REST API** `/api/notes/*` — 7 endpoint per la UI
- **Frontend** — `NotesPageView.vue`, `NotesBrowser.vue` (sidebar con folder tree + tag cloud),
  `NoteEditor.vue` (editor Markdown con preview live), `notes.ts` store Pinia

#### Schema DB proposto

```sql
CREATE TABLE note_entries (
    id          TEXT PRIMARY KEY,   -- uuid str
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,      -- Markdown
    folder_path TEXT DEFAULT '',    -- es. "lavoro/progetti"
    tags        TEXT DEFAULT '[]',  -- JSON array ["ai", "python"]
    wikilinks   TEXT DEFAULT '[]',  -- JSON array ["Nota correlata"]
    summary     TEXT,               -- AI-generated cache, nullable
    pinned      INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE VIRTUAL TABLE note_vectors USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[768] distance_metric=cosine
);

CREATE VIRTUAL TABLE note_fts USING fts5(
    title, content, content=note_entries, content_rowid=rowid
);
```

#### Dipendenze

- `sqlite-vec >= 0.1.6` (già in pyproject.toml per MemoryService)
- `fastembed >= 0.3` (già in pyproject.toml come fallback)
- Frontend: nessuna nuova dipendenza (usa Vue 3 + Pinia già presenti)

#### Distinzione da Memory Service

| Aspetto        | Memory Service (Fase 9)      | Note System (Fase 13)                   |
|----------------|------------------------------|-----------------------------------------|
| Origine        | Automatica (LLM decide)      | Intenzionale (utente/LLM su comando)    |
| Formato        | Fatti brevi (max 1000 char)  | Documenti Markdown interi               |
| Organizzazione | Categoria + scope            | Folder tree + tag + wikilinks           |
| UI             | MemoryManager.vue (gestione) | NoteEditor.vue (editing diretto)        |
| Ricerca        | Solo semantica               | Full-text + semantica                   |
| LLM context    | Iniettato automaticamente    | Recuperato solo su richiesta esplicita  |

---

### 2. Email Assistant

**Stato**: backlog (alta complessità, buon ROI)

#### Descrizione

Assistente email locale che usa IMAP/SMTP per leggere, categorizzare e rispondere alle email
senza dipendenze da API cloud. L'LLM elabora il contenuto; le credenziali rimangono locali.

#### Architettura proposta

- **`EmailService`** — wrapper async attorno a `aioimaplib` (IMAP) + `aiosmtplib` (SMTP)
- Connessione IMAP persistente con IDLE per notifiche push di nuove email
- Credenziali via OS keyring (`keyring` library) — mai in plaintext in `default.yaml`
- **Plugin `email_assistant`** con tool: `read_emails`, `search_emails`, `reply_email`,
  `compose_email`, `mark_read`, `archive_email`
- Frontend: vista inbox semplice + finestra di composizione integrata nella chat
- `EmailConfig`: `imap_host`, `imap_port`, `smtp_host`, `smtp_port`, `username`,
  `password: SecretStr`, `fetch_last_n: int = 20`, `auto_categorize: bool = False`

#### Dipendenze

- `aioimaplib >= 1.0` (IMAP async)
- `aiosmtplib >= 3.0` (SMTP async)
- `keyring >= 24.0` (credenziali OS)
- `beautifulsoup4` (già presente, per strip HTML email)

#### Considerazioni di sicurezza

- Password in `SecretStr` — mai loggata
- `email.send_email` richiede `requires_confirmation=True` + `risk_level="dangerous"` (operazione irreversibile)
- Sanitizzazione HTML nelle email prima di passarle all'LLM (anti prompt injection via email)
- Rate limit: max N email inviate per ora (anti-abuso)
- Supporto App Password per Gmail/Outlook (2FA non blocca IMAP se app password configurata)

---

### 3. Telegram/Discord Bridge

**Stato**: backlog (ROI altissimo — trasforma l'usabilità mobile)

#### Descrizione

Bot Telegram e/o Discord che funge da bridge verso OMNIA. L'utente può parlare con
OMNIA da smartphone, quando è lontano dal desktop. Il bot non è un assistente separato —
è semplicemente un front-end alternativo che invia messaggi al backend OMNIA esistente.

#### Architettura proposta (Telegram focus)

- **Plugin `telegram_bridge`** — non un bot autonomo: è un client della libreria `python-telegram-bot`
  che si integra nel lifespan FastAPI
- `TelegramBridge` avviato in `on_app_startup()`, fermato in `on_app_shutdown()`
- Il bot riceve un messaggio Telegram → crea/riusa una conversazione OMNIA → chiama
  il tool loop interno → risponde con il testo dell'LLM
- Supporto messaggi vocali: il bot riceve voice note Telegram → scarica l'audio → passa
  a `STTService` → crea messaggio testuale → flusso normale
- **Autorizzazione**: whitelist di `user_id` Telegram in config — nessun accesso a estranei
- `TelegramConfig`: `enabled: bool`, `bot_token: SecretStr`, `allowed_user_ids: list[int]`,
  `session_timeout_minutes: int = 60`

#### Dipendenze

- `python-telegram-bot >= 21.0` (async, httpx-based)
- Nessuna altra dipendenza — riusa conversazione OMNIA esistente

#### Perché massimo ROI

OMNIA è già completo: ha LLM streaming, tool loop, voce, plugin. Il bridge Telegram è
~150 LOC che collegano un'interfaccia esistente (bot API) al backend già funzionante.
Trasforma OMNIA da "applicazione desktop" a "assistente personale sempre disponibile".

---

### 4. Document Q&A

**Stato**: backlog (facilmente costruibile sulla pipeline embedding esistente)

#### Descrizione

Carica documenti locali (PDF, DOCX, XLSX, TXT, MD) e fai domande in linguaggio naturale
sul loro contenuto. La pipeline di embedding (già presente via `EmbeddingClient`) costruisce
un corpus di chunks searchable semanticamente.

#### Due modalità

1. **Corpus temporaneo (sessione)** — carica un file durante la chat, fai domande, viene
   dimenticato a fine conversazione. Implementazione: in-memory vector store con numpy.
2. **Libreria persistente** — aggiungi documenti a una libreria permanente, OMNIA può
   consultarli in qualsiasi momento. Implementazione: sqlite-vec (già presente per MemoryService).

#### Architettura proposta

- **`DocumentService`** — gestisce `data/documents.db` con schema simile a MemoryService:
  - `document_entries`: `id, filename, file_hash, total_chunks, uploaded_at`
  - `document_chunks`: `id, doc_id, chunk_index, text, page_number`
  - `chunk_vectors`: sqlite-vec virtual table
- **Chunking strategy**: sliding window (overlap=50 token, chunk=500 token), rispettando
  confini di paragrafo quando possibile
- **Parsing**: `pdfplumber` (PDF), `python-docx` (DOCX), `openpyxl` (XLSX — cells as text),
  stdlib per TXT/MD
- **Deduplication**: hash SHA-256 del file → skip se già indicizzato (`document_entries.file_hash`)
- **Plugin `document_qa`** con tool: `add_document`, `query_documents`, `list_documents`,
  `remove_document`
- Frontend: zona drag-and-drop nella sidebar + lista documenti indicizzati

#### Dipendenze

- `pdfplumber >= 0.11` (già opzionale in file_search)
- `python-docx >= 1.1` (già opzionale in file_search)
- `openpyxl >= 3.1`
- `sqlite-vec` e `fastembed` (già presenti)

---

### 5. Browser Automation via CDP

**Stato**: backlog (necessario per sostituire il plugin `web_search` in scenari avanzati)

#### Descrizione

Automatizza un browser già aperto (Chrome/Chromium) tramite Chrome DevTools Protocol (CDP),
connettendosi a una sessione esistente invece di aprire un browser headless. Risolve il
problema fondamentale dei siti che bloccano i bot: il browser usa i cookie, la sessione
di login e i profili dell'utente reale.

#### Approccio CDP (vs. alternativa headless)

| Approccio | Copertura | Cookie/login | Setup | Note |
|-----------|-----------|--------------|-------|------|
| Playwright connect_over_cdp | Alta | ✅ usa sessione reale | Chrome con `--remote-debugging-port=9222` | **Raccomandato** |
| Playwright headless | Alta | ❌ fresh session | Semplice | Fallisce su siti anti-bot |
| Selenium | Alta | ⚠️ dipende da profile | Medio | Più lento, stesso problema headless |
| browser-use (LLM nativo) | Media | ❌ | Moderato | Buono per task generici |

#### Architettura proposta

- **Plugin `browser_automation`** — usa `playwright.async_api` in modalità `connect_over_cdp`
- L'utente avvia Chrome con: `chrome.exe --remote-debugging-port=9222 --user-data-dir=%USERPROFILE%\omnia-browser`
- Il plugin si connette a `localhost:9222` (locale, non SSRF)
- Tool: `navigate(url)`, `click(selector)`, `type_text(selector, text)`,
  `get_page_text()`, `get_page_screenshot()`, `extract_table()`, `wait_for_selector()`
- `BrowserConfig`: `cdp_url: str = "http://localhost:9222"`, `default_timeout_ms: int = 30000`
- Tutti i tool con `risk_level="medium"`, `requires_confirmation=True`
  (tranne `get_page_text` e `get_page_screenshot` che sono safe)

#### Dipendenze

- `playwright >= 1.44` (async, già cross-platform)
- Nessun browser headless — riusa Chromium dell'utente

#### Limitazioni note

- Richiede Chrome avviato manualmente con `--remote-debugging-port`
- Non funziona con Firefox out-of-the-box (CDP non standard)
- Sequenze di azioni complesse possono fallire su SPA con state asincrono

---

## Backlog Idee (alta priorità)

| Idea | Categoria | ROI | Dipendenze chiave |
|------|-----------|-----|-------------------|
| Telegram/Discord Bridge | Comunicazione | ⭐⭐⭐⭐⭐ | python-telegram-bot |
| Document Q&A | Conoscenza | ⭐⭐⭐⭐ | pdfplumber, openpyxl |
| Note System | Produttività | ⭐⭐⭐⭐ | sqlite-vec (già presente) |
| Web Clipper | Produttività | ⭐⭐⭐ | Browser extension / CDP |
| Daily Report | Produttività | ⭐⭐⭐ | Calendar + News (già presenti) |
| Email Assistant | Comunicazione | ⭐⭐⭐ | aioimaplib, aiosmtplib |
| Browser Automation | Automazione | ⭐⭐⭐ | playwright |
| Pomodoro Timer | Produttività | ⭐⭐ | Notifications (già presenti) |
| Code Interpreter | Sviluppo | ⭐⭐ | subprocess sandbox |
| Git Assistant | Sviluppo | ⭐⭐ | gitpython / MCP git |
| Local Dashboard | Monitoring | ⭐⭐ | SQLite queries + charts |

---

## Backlog Idee (media priorità)

| Idea | Categoria | Note |
|------|-----------|------|
| Voice Journal | Creativo | STT → trascrizione + NoteService |
| Recipe Manager | Produttività | Note System + web scrape |
| Habit Tracker | Produttività | Calendar + Notifications |
| LAN Device Discovery | Monitoring | nmap / socket scan |
| App Usage Stats | Monitoring | psutil (già presente) |
| Network Monitor | Monitoring | psutil + ping |
| Local Wiki | Conoscenza | Note System + backlinks |
| Cooking Timer Voce | Produttività | TTS + Notifications |
| Screenshot OCR | Automazione | Tesseract / Windows OCR |
| Wallet/Budget Tracker | Produttività | SQLite + chart frontend |

---

## Backlog Idee (sperimentale)

| Idea | Categoria | Note |
|------|-----------|------|
| Proactive Context Injection | Sperimentale | EventBus trigger → LLM spontaneo |
| Multi-Agent Orchestration | Sperimentale | Task Runner (Fase 10) come base |
| Real-Time Translation | Comunicazione | STT → translate → TTS |
| Local RAG su Codebase | Sviluppo | Document Q&A applicato al codice |
| Sentiment Analysis Diary | Creativo | Note System + embedding cluster |
| Sleep Tracker | Monitoring | Integrazione wearable via HA |
