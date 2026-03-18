### Fase 7 — Plugin: Ricerca Web + Calendario + Meteo

> **Struttura file per ogni plugin** (pattern consolidato dal codebase):
> `backend/plugins/{name}/__init__.py` — import + `PLUGIN_REGISTRY["{name}"] = XxxPlugin`
> `backend/plugins/{name}/plugin.py` — `BasePlugin` subclass con `get_tools()` e `execute_tool()`
> File aggiuntivi (client.py, executor.py, etc.) se il plugin ha >150 righe di logica

#### 7.1 — Web Search Plugin (`backend/plugins/web_search/`)
- [x] `WebSearchPlugin(BasePlugin)` — `plugin_name = "web_search"`, `plugin_version = "1.0.0"`, `plugin_priority = 40`
- [x] `plugin_dependencies: list[str] = []` — standalone, nessun altro plugin richiesto
- [x] `WebSearchConfig(BaseSettings)` in `backend/core/config.py`:
  - `enabled: bool = False`
  - `max_results: int = 5`
  - `cache_ttl_s: int = 300` (5 min)
  - `request_timeout_s: int = 10`
  - `rate_limit_s: float = 10.0` (min secondi fra richieste DDG)
  - `proxy_http: str | None = None`, `proxy_https: str | None = None`
- [x] Entry in `config/default.yaml`: `web_search:` section + `web_search` nella lista `plugins.enabled` (disabled by default)
- [x] `backend/plugins/web_search/client.py`:
  - `WebSearchClient` — singleton su `httpx.AsyncClient` persistente (connection pool, non ricreare per ogni call, stesso pattern di HA client pianificato in Fase 6)
  - Lazy DDG import: `try: from duckduckgo_search import DDGS` con `check_dependencies()` se mancante
  - Rate limiting: `asyncio.Lock` + timestamp ultima richiesta (evita ban DDG)
  - Result caching: `functools.lru_cache` con TTL manuale (dict `{query_hash: (timestamp, results)}`)
  - `async def search(query, max_results) -> list[dict]` — `asyncio.to_thread(ddg.text, ...)` (DDG sync)
  - `async def scrape(url) -> str` — `await client.get(url, timeout=10)` → `BeautifulSoup(html, "html.parser").get_text()` → tronca a 50KB
- [x] **SSRF prevention** in `client.py` (`_validate_url(url: str) -> None`):
  - Bloccare schemi non-HTTPS/HTTP: `file://`, `ftp://`, `ssh://`, etc.
  - Risolvere hostname via `socket.getaddrinfo()` in thread (async-safe) — bloccare IP privati: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`, `fc00::/7`
  - Bloccare `localhost` e varianti (case-insensitive)
  - Stessa funzione riusata da `weather` client (7.3) e `news` reader (7.6)
- [x] Tool `web_search`: `risk_level="safe"`, `timeout_ms=15000`, `result_type="json"` — `max_results` validato: 1–20
- [x] Tool `web_scrape`: `risk_level="medium"`, `requires_confirmation=True`, `timeout_ms=15000` — URL validata con `_validate_url()` prima dell'esecuzione
- [x] Sanitizzazione output: strip tag HTML residui + normalizzazione whitespace + tronca a 4096 chars (già gestito da `ToolRegistry`)
- [x] `get_config_schema()` per auto-generazione form Settings (Fase 8)

#### 7.2 — Calendario Plugin (`backend/plugins/calendar/`)
- [x] `CalendarPlugin(BasePlugin)` — `plugin_name = "calendar"`, `plugin_priority = 30`
- [x] `plugin_dependencies: list[str] = []` — standalone
- [x] DB models via `get_db_models()` — tabella creata da `PluginManager` a startup (già supportato):
  - `CalendarEvent(SQLModel, table=True)`: `id: uuid`, `title: str`, `description: str | None`, `start_time: datetime` (UTC), `end_time: datetime` (UTC), `recurrence_rule: str | None` (RRULE RFC 5545), `reminder_minutes: int | None`, `created_by: str = "llm"`, `created_at: datetime`
- [x] `CalendarConfig(BaseSettings)` in `config.py`:
  - `enabled: bool = False`
  - `timezone: str = "Europe/Rome"` (IANA timezone)
  - `reminder_check_interval_s: int = 60`
- [x] `on_app_startup()`: avvia `asyncio.create_task(_reminder_loop())` — background task con `asyncio.sleep(reminder_check_interval_s)`, cerca eventi con `reminder_minutes` entro la finestra, emette `calendar.reminder` su EventBus
- [x] `on_app_shutdown()`: cancella il task del reminder loop
- [x] Dipendenza: `python-dateutil ≥ 2.9` in `pyproject.toml` per RRULE parsing + `pytz` per timezone
- [x] Tool `create_event`: `risk_level="safe"`, validazione start < end, parse `start`/`end` come ISO 8601 con `dateutil.parser.parse()`, converti a UTC prima di salvare
- [x] Tool `list_events`: `risk_level="safe"`, filtra per range UTC, converti risultati a timezone utente prima di restituire
- [x] Tool `update_event`: `risk_level="safe"`, stesso processo di validazione di `create_event`
- [x] Tool `delete_event`: `risk_level="medium"`, `requires_confirmation=True`
- [x] Tool `get_today_summary`: `risk_level="safe"`, restituisce eventi di oggi (da mezzanotte a mezzanotte utente timezone)
- [x] **Edge case**: se `start_time` e `end_time` sono nello stesso fuso orario passato come stringa ISO 8601 con offset (es. `2026-03-08T15:00:00+01:00`), preservare intent senza convertire a UTC e riconvertire (usare `dateutil.parser.parse()` che mantiene tzinfo)
- [x] **Futura integrazione esterna**: colonna `external_id: str | None` + `external_source: str | None` per CalDAV/Google Calendar

#### 7.3 — Weather Plugin (`backend/plugins/weather/`)
> **Dipendenza Fase 7.1**: riusa `_validate_url()` da `web_search/client.py` — importare come utility condivisa. Alternativa (più pulita): copiare la logica in un modulo `backend/core/http_security.py` condiviso tra i plugin che fanno fetch HTTP (web_search, weather, news). **Scelta consigliata**: creare `backend/core/http_security.py` con `validate_url_ssrf(url: str) -> None` usato da tutti e tre.

- [x] **Prerequisito**: creare `backend/core/http_security.py` (SSRF check centralizzato) — rimuovere logica duplicata da web_search/client.py e usare solo questo modulo
- [x] `WeatherPlugin(BasePlugin)` — `plugin_name = "weather"`, `plugin_priority = 35`, `plugin_dependencies: list[str] = []`
- [x] Backend dati: **open-meteo.com** (free, no API key, HTTPS only) — URL: `https://api.open-meteo.com/v1/forecast`
  - Zero dipendenze cloud a pagamento, conforme al vincolo di progetto
  - Geocoding: `https://geocoding-api.open-meteo.com/v1/search` per nome città → lat/lon
- [x] `WeatherConfig(BaseSettings)` in `config.py`:
  - `enabled: bool = False`
  - `default_city: str = "Rome"` (usata se tool chiamato senza `city`)
  - `units: Literal["metric", "imperial"] = "metric"`
  - `lang: str = "it"`
  - `cache_ttl_s: int = 600` (10 min — meteo non cambia al secondo)
  - `request_timeout_s: int = 8`
- [x] `backend/plugins/weather/client.py`:
  - `WeatherClient` — `httpx.AsyncClient` persistente (non ricreare per ogni call)
  - `async def get_coordinates(city: str) -> tuple[float, float]` — geocoding con caching in `plugin_local_state`
  - `async def get_current(lat, lon, units, lang) -> dict`
  - `async def get_forecast(lat, lon, days, units, lang) -> list[dict]`
  - Caching: `{(city, units, lang): (timestamp, data)}` dict in memory — invalidato dopo `cache_ttl_s`
  - `validate_url_ssrf()` da `backend/core/http_security.py` prima di ogni fetch
- [x] Tool `get_weather(city?: str)` → `risk_level="safe"`, `timeout_ms=10000`, `result_type="json"`:
  - Output: `{city, temperature, feels_like, humidity, wind_speed, condition, uv_index, timestamp}`
  - Se `city` omesso → usa `config.weather.default_city`
- [x] Tool `get_weather_forecast(city?: str, days: int = 3)` → `risk_level="safe"`, `timeout_ms=10000`:
  - `days` validato: 1–7 (limite open-meteo free tier)
  - Output: lista di `{date, temp_max, temp_min, condition, precipitation_prob}`
- [x] `initialize()`: crea `WeatherClient`, registra in `plugin_local_state["weather"]["client"]`
- [x] `cleanup()`: chiude `httpx.AsyncClient` (`await client.aclose()`)
- [x] **Edge case**: città non trovata → `ToolResult.error("City not found: ...")` (non eccezione Python raw)
- [x] **Edge case**: open-meteo offline → `ToolResult.error("Weather service unavailable")` + emit `ConnectionStatus.DISCONNECTED` via `get_connection_status()`

#### 7.4 — Plugin UI (Vue components)
- [x] **Strategia**: plugin components bundled nel frontend (Option A — semplice per Electron; Option B con fetch remoto in Fase 8)
- [x] `defineAsyncComponent()` per lazy loading componenti plugin
- [x] **Plugin component registry**: `PluginManager.get_frontend_components()` → REST endpoint `GET /api/plugins/components` → frontend carica async
- [x] **Mount points** per plugin UI: `sidebar`, `modal`, `toolbar`, `settings-panel`
- [x] Componente `CalendarView.vue`: vista settimanale/mensile base, CRUD eventi
- [x] Componente `SearchResultsPanel.vue`: risultati ricerca in sidebar collassabile
- [x] Componente `WeatherWidget.vue`: widget compatto per toolbar (temperatura + icona condizione)

#### 7.5 — Dipendenze e Config Changes per Fase 7
- [x] `pyproject.toml` — nuove dipendenze:
  - `duckduckgo-search >= 6.0` (web_search)
  - `beautifulsoup4 >= 4.12` (web_search scrape)
  - `python-dateutil >= 2.9` (calendar RRULE)
  - `pytz >= 2024.1` (calendar timezone — alternativa: `zoneinfo` stdlib Python 3.9+, preferibile)
  - Nessuna nuova dep per weather (httpx già in core)
- [x] `backend/core/config.py`:
  - Aggiungere `WebConfig`, `CalendarConfig`, `WeatherConfig` come `BaseSettings` subclass
  - Aggiungere a `OmniaConfig` come campi: `web: WebConfig`, `calendar: CalendarConfig`, `weather: WeatherConfig`
- [x] `config/default.yaml`:
  - Sezioni `web_search:`, `calendar:`, `weather:` con tutti i defaults
  - `plugins.enabled` rimane `[system_info, pc_automation]` — gli altri `enabled: false` individualmente per safety

#### 7.6 — Test Suite Fase 7
- [x] Test web_search: mock `DDGS.text()` via `asyncio.to_thread`, rate limiting (token bucket), SSRF blocking su 127.0.0.1/10.x/192.168.x, caching LRU hit/miss
- [x] Test web_scrape: mock `httpx.AsyncClient.get()`, max size truncation (>50KB), timeout, URL SSRF validation
- [x] Test calendar: CRUD eventi, RRULE parsing, reminder trigger (mock `asyncio.sleep`), conversione UTC↔timezone, edge: start > end, event non trovato
- [x] Test weather: mock httpx responses open-meteo, geocoding caching, città non trovata, servizio offline → ConnectionStatus.DISCONNECTED
- [x] Test `http_security.py`: ogni categoria IP privato bloccata, schema non-HTTP bloccato, URL pubblica valida passa
- [x] Test plugin UI loading: `defineAsyncComponent()`, mount points

---

