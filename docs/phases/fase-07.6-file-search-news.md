### Fase 7.6 — Plugin: Ricerca File + Notizie/Briefing

> **Ordine di implementazione consigliato**: file_search (zero nuove dep obbligatorie) → news (richiede feedparser + soft dep su weather/calendar). `file_search` non dipende da nessun altro plugin. `news.get_daily_briefing()` ha soft dependency su weather e calendar (via `ctx.plugin_manager`, non hard dep).

#### 7.6.1 — File Search Plugin (`backend/plugins/file_search/`)
- [x] `FileSearchPlugin(BasePlugin)` — `plugin_name = "file_search"`, `plugin_priority = 25`, `plugin_dependencies: list[str] = []`
- [x] **Zero nuove dipendenze obbligatorie** — usa stdlib: `os`, `pathlib`, `mimetypes`, `stat`
  - Dipendenze opzionali per lettura file avanzata (lazy import con `check_dependencies()`):
    - `pdfplumber >= 0.11` per lettura PDF
    - `python-docx >= 1.1` per lettura DOCX
    - Se mancanti: `read_text_file` restituisce errore specifico (`"PDF reading requires: pip install pdfplumber"`)
- [x] `FileSearchConfig(BaseSettings)` in `config.py`:
  - `enabled: bool = False`
  - `allowed_paths: list[str] = []` — default calcolato dinamicamente in `initialize()`: `[Path.home(), Path.home()/"Desktop", Path.home()/"Documents", Path.home()/"Downloads"]`
  - `forbidden_paths: list[str]` — PATH di sistema bloccati: `["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)", "C:\\ProgramData"]` (Windows); `/etc`, `/sys`, `/proc`, `/dev` (Linux/macOS)
  - `max_results: int = 50`
  - `max_file_size_read_bytes: int = 1_048_576` (1 MB — limite lettura file)
  - `max_content_chars: int = 8000` (tronca testo prima di inviare a LLM)
  - `follow_symlinks: bool = False` (anti path-traversal via symlink)
- [x] `backend/plugins/file_search/searcher.py`:
  - `async def search_files(query, roots, extensions, max_results, forbidden) -> list[dict]`:
    - `asyncio.to_thread(_sync_walk, ...)` — `os.walk()` è blocking
    - `_sync_walk`: case-insensitive `query in filename.lower()`, filtra per estensione se specificato
    - Ogni risultato: `{path, name, size_bytes, modified_iso, extension}`
    - `_validate_path(path, allowed, forbidden)`: controlla che il path reale (risolto, no symlink if `follow_symlinks=False`) stia dentro un allowed root e non in un forbidden path
    - Timeout di sicurezza: max 5 secondi per walk (anti-freeze su directory enormi) via `asyncio.wait_for`
    - **Edge case**: `PermissionError` su singola directory → log warning + continua (non interrompe l'intera ricerca)
- [x] `backend/plugins/file_search/readers.py`:
  - `async def read_text_file(path: str, max_bytes: int) -> str`
  - Dispatcher per estensione: `.txt/.md/.py/.js/.ts/.json/.yaml/.csv` → `open(encoding="utf-8", errors="replace")`
  - `.pdf` → `pdfplumber.open(path)` + `asyncio.to_thread`
  - `.docx` → `python-docx` + `asyncio.to_thread`
  - Resto → `ToolResult.error("Unsupported file type for reading: .{ext}")`
  - Rispetta `max_bytes` — legge solo i primi N bytes
- [x] Tool `search_files(query: str, path?: str, extensions?: list[str], max_results?: int = 20)` → `risk_level="safe"`, `timeout_ms=10000`:
  - `path` opzionale: se fornito, validato contro `allowed_paths`; se omesso → cerca in tutti gli `allowed_paths`
  - `extensions` opzionale: `[".pdf", ".docx"]` — normalizzate a lowercase con punto
- [x] Tool `get_file_info(path: str)` → `risk_level="safe"`, `timeout_ms=3000`:
  - Solo metadata: `{name, size_bytes, modified_iso, created_iso, extension, mime_type}`
  - **NO** contenuto file — metadata è sempre safe
  - Valida path contro `allowed_paths`
- [x] Tool `read_text_file(path: str, max_chars?: int)` → `risk_level="medium"`, `requires_confirmation=True`, `timeout_ms=15000`:
  - Il contenuto di file personali è sensibile → confirmation obbligatoria
  - Valida path + legge tramite `readers.py`
  - Output include `{content, truncated, chars_read, path}`
- [x] Tool `open_file(path: str)` → `risk_level="medium"`, `requires_confirmation=True`, `timeout_ms=5000`:
  - `asyncio.to_thread(os.startfile, path)` — apre con app associata di Windows
  - Valida path contro `allowed_paths` + forbidden antes
  - **Edge case**: file non esiste → `ToolResult.error("File not found: ...")`
  - **Edge case**: `os.startfile` non disponibile (non-Windows) → fallback a `subprocess.Popen(["xdg-open", path])` (Linux) o `subprocess.Popen(["open", path])` (macOS)
- [x] **Edge case generale**: UNC paths (`\\server\share`) → bloccare (potenziale SSRF-equivalente su reti condivise)
- [x] Test: mock os.walk, file trovato/non trovato, PermissionError continua, UNC path bloccato, symlink con follow=False, timeout 5s walk, read PDF senza pdfplumber → errore, path fuori allowed_paths, forbidden path bloccato

#### 7.6.2 — News / Briefing Plugin (`backend/plugins/news/`)
- [x] `NewsPlugin(BasePlugin)` — `plugin_name = "news"`, `plugin_priority = 15`, `plugin_dependencies: list[str] = []`
  - **Soft dependency** (non hard) su `weather` e `calendar`: in `get_daily_briefing()`, controllare `ctx.plugin_manager.get_plugin("weather")` — se disponibile e connected → aggiungere dati meteo al briefing; se no → procedere senza
- [x] Dipendenza: **`feedparser >= 6.0`** in `pyproject.toml` (RSS/Atom parsing — puro Python, zero dep native)
- [x] `NewsConfig(BaseSettings)` in `config.py`:
  - `enabled: bool = False`
  - `feeds: list[str]` — default: feed RSS pubblici selezionati (BBC World, ANSA, Repubblica):
    ```
    - "https://feeds.bbci.co.uk/news/world/rss.xml"
    - "https://www.ansa.it/sito/notizie/tecnologia/rss.xml"
    - "https://www.repubblica.it/rss/homepage/rss2.0.xml"
    ```
  - `max_articles: int = 10` (per feed)
  - `cache_ttl_minutes: int = 15`
  - `request_timeout_s: int = 10`
  - `default_lang: str = "it"`
- [x] `backend/plugins/news/feed_reader.py`:
  - `FeedReader` — `httpx.AsyncClient` persistente (pattern shared con weather/web_search)
  - `async def fetch_feed(url: str) -> list[dict]`:
    - `validate_url_ssrf(url)` da `backend/core/http_security.py` — **stessa utility di weather e web_search**
    - `response = await client.get(url, timeout=config.request_timeout_s)`
    - `asyncio.to_thread(feedparser.parse, response.text)` (feedparser è CPU-bound, non async)
    - Ogni articolo normalizzato: `{title, summary, link, published_iso, source}`
  - Cache: `{url: (timestamp, articles)}` in memory — TTL `cache_ttl_minutes`
  - `async def fetch_all_feeds(urls, max_per_feed) -> list[dict]`: `asyncio.gather(*[fetch_feed(u) for u in urls])` — fetch paralleli
- [x] Tool `get_news(topic?: str, lang?: str, max_results?: int = 10)` → `risk_level="safe"`, `timeout_ms=20000`:
  - Fetch tutti i feed configurati in parallelo
  - Se `topic`: filtra titoli/sommari contenenenti il termine (case-insensitive)
  - Output: `{articles: [{title, summary, link, published_iso, source}], total, cached: bool}`
- [x] Tool `get_daily_briefing()` → `risk_level="safe"`, `timeout_ms=30000`:
  - Aggrega sincronicamente:
    1. **Data e ora corrente** (sempre disponibile)
    2. **Top news** (da `fetch_all_feeds`) — prime 5 notizie
    3. **Meteo** (soft dep): se `weather` plugin disponibile e `ConnectionStatus.CONNECTED` → chiama `ctx.tool_registry.execute_tool("weather_get_weather", {}, context)` — non import diretto (evita accoppiamento)
    4. **Agenda del giorno** (soft dep): se `calendar` plugin disponibile → chiama `ctx.tool_registry.execute_tool("calendar_get_today_summary", {}, context)`
  - Output strutturato: `{date_iso, weather?: {...}, today_events?: [...], top_news: [...]}`
  - **Edge case**: se uno dei servizi soft-dep fallisce → includi solo i dati disponibili, non fail tutto il briefing
- [x] `initialize()`: crea `FeedReader`, registra in `plugin_local_state["news"]["reader"]`
- [x] `cleanup()`: chiude `httpx.AsyncClient`
- [x] Test: mock httpx.AsyncClient + feedparser, parallel fetch, caching hit/miss, SSRF blocking su feed URL custom, topic filter, daily briefing con weather/calendar assenti (graceful), weather online → incluso nel briefing

#### 7.6.3 — Config e Dipendenze Fase 7.6
- [x] `pyproject.toml` nuove dipendenze:
  - `feedparser >= 6.0` (news)
  - `pdfplumber >= 0.11` (file_search, optional — lazy import)
  - `python-docx >= 1.1` (file_search, optional — lazy import)
  - Nessuna nuova dep per file_search base (stdlib)
- [x] `backend/core/config.py`: `FileSearchConfig`, `NewsConfig` + aggiunta a `AliceConfig`
- [x] `config/default.yaml`: sezioni `file_search:`, `news:` con defaults

#### 7.6.4 — Test Suite Fase 7.6
- [x] Test file_search: mock os.walk, path validation (allowed/forbidden/UNC/symlink), PermissionError continuazione, timeout walk, read_text_file con mock pdfplumber/docx, open_file cross-platform (Windows startfile, Linux xdg-open)
- [x] Test news: mock httpx + feedparser, parallel fetch, cache TTL, SSRF su URL feed custom, filtro topic, daily briefing con/senza weather/calendar, soft dep non disponibile → partial result
- [x] Test `backend/core/http_security.py` (riusato da weather + web_search + news): copertura completa IP privati RFC 1918 + loopback + link-local + IPv6 private

---

### Riepilogo Dipendenze tra Fasi 7, 7.5, 7.6

```
backend/core/http_security.py   ← creato in Fase 7.3 (weather)
     ↑ usato da: web_search (7.1), weather (7.3), news (7.6.2)

calendar (7.2) ── soft dep ──→ notifications (7.5.2) [EventBus: calendar.reminder]
weather  (7.3) ── soft dep ──→ news briefing (7.6.2) [ctx.tool_registry call]
calendar (7.2) ── soft dep ──→ news briefing (7.6.2) [ctx.tool_registry call]

Ordine implementazione consigliato:
  1. http_security.py (utility condivisa, richiesta da weather + news)
  2. web_search (7.1) + calendar (7.2) [parallelo, no inter-dep]
  3. weather (7.3) [dopo http_security.py]
  4. clipboard (7.5.1) [standalone, più semplice]
  5. notifications (7.5.2) [standalone + EventBus subscription opzionale]
  6. media_control (7.5.3) [standalone, più complesso per COM Windows]
  7. file_search (7.6.1) [standalone]
  8. news (7.6.2) [dopo weather + calendar per briefing completo]
```

---

