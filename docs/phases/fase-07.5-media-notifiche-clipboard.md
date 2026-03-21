### Fase 7.5 — Plugin: Media Control + Notifiche + Clipboard

> **Ordine di implementazione consigliato**: clipboard (più semplice, zero nuove dep) → notifications (timer stateful) → media_control (COM/Windows = più complesso). Tutti e tre sono standalone senza dipendenze da altri plugin.

#### 7.5.1 — Clipboard Plugin (`backend/plugins/clipboard/`)
- [x] `ClipboardPlugin(BasePlugin)` — `plugin_name = "clipboard"`, `plugin_priority = 20`, `plugin_dependencies: list[str] = []`
- [x] Dipendenza: **`pyperclip >= 1.9`** in `pyproject.toml` (cross-platform; su Windows usa `win32clipboard` da pywin32 già presente come dep di pc_automation — ma `pyperclip` è più semplice come api)
- [x] Lazy import: `try: import pyperclip` con `check_dependencies()` se mancante
- [x] `ClipboardConfig(BaseSettings)` in `config.py`:
  - `enabled: bool = False`
  - `max_content_chars: int = 4000` (tronca prima di inviare a LLM — evita context flooding)
- [x] Tool `get_clipboard()` → `risk_level="safe"`, `timeout_ms=3000`:
  - `asyncio.to_thread(pyperclip.paste)` — API sync, sempre thread
  - Output: `{content: str, truncated: bool, length: int}`
  - **Edge case**: clipboard contiene binario (immagine/file) → `pyperclip.PyperclipException` → `ToolResult.error("Clipboard contains non-text content")`
  - **Edge case**: clipboard vuota → `{content: "", truncated: false, length: 0}`
- [x] Tool `set_clipboard(text: str)` → `risk_level="medium"`, `requires_confirmation=True`, `timeout_ms=3000`:
  - `asyncio.to_thread(pyperclip.copy, text)`
  - Validazione: `len(text) <= 1_000_000` (anti–memory bomb se LLM genera testo enorme)
  - **Edge case**: `pyperclip` non disponibile (headless server senza display) → `ToolResult.error("Clipboard not available in headless environment")`
- [x] File structure: solo `__init__.py` + `plugin.py` (plugin < 80 righe, nessun executor separato)
- [x] Test: mock pyperclip.paste/copy, testo binario → errore, testo lungo > max → truncated flag, pyperclip non disponibile

#### 7.5.2 — Notifications Plugin (`backend/plugins/notifications/`)
- [x] `NotificationsPlugin(BasePlugin)` — `plugin_name = "notifications"`, `plugin_priority = 25`, `plugin_dependencies: list[str] = []`
- [x] Dipendenza Windows: **`winotify >= 1.1`** in `pyproject.toml` per Windows 10/11 toast native
  - Fallback headless (no display): log warning + `ToolResult.ok("Notification queued (no display)")` — non crashare
  - Lazy import: `try: from winotify import Notification, audio as WinAudio`
- [x] `NotificationsConfig(BaseSettings)` in `config.py`:
  - `enabled: bool = False`
  - `app_id: str = "AL\\CE"` (nome app nelle notifiche Windows)
  - `sound_enabled: bool = True`
  - `default_timeout_s: int = 5`
  - `max_active_timers: int = 20` (anti DoS per richieste timer dal LLM)
- [x] `backend/plugins/notifications/timer_manager.py`:
  - `TimerManager` (non singleton — istanziato in `NotificationsPlugin.initialize()`)
  - `_timers: dict[str, asyncio.Task]` — mapping `timer_id → Task`
  - `async def create_timer(timer_id: str, label: str, duration_s: int, callback: Callable) -> None`
  - `def cancel_timer(timer_id: str) -> bool` — `task.cancel()` + rimozione dal dict
  - `async def shutdown()` — cancella tutti i task attivi (chiamato da `cleanup()`)
  - **Persistenza timers**: DB model `ActiveTimer(SQLModel, table=True)`: `id: str (uuid)`, `label: str`, `fires_at: datetime`, `created_at: datetime`, `status: Literal["pending", "fired", "cancelled"]`
  - `on_app_startup()`: carica timers `status="pending"` con `fires_at > now()` dal DB, ri-crea i task `asyncio` corrispondenti (sopravvivono a restart del backend)
  - **Edge case**: se `fires_at` è nel passato al reload → inviare notifica immediately + aggiornare status a "fired"
- [x] Tool `send_notification(title: str, message: str, timeout_s?: int)` → `risk_level="safe"`, `timeout_ms=5000`:
  - `asyncio.to_thread(_send_win_notification, title, message, timeout_s)`
  - Fallback: se winotify non disponibile → solo log (non errore)
- [x] Tool `set_timer(label: str, duration_seconds: int)` → `risk_level="safe"`, `timeout_ms=3000`:
  - Valida `1 <= duration_seconds <= 86400` (max 24h)
  - Valida `len(active_timers) < max_active_timers`
  - Genera `timer_id = uuid4()`, crea task + salva in DB
  - Return: `{timer_id, label, fires_at_iso}`
- [x] Tool `cancel_timer(timer_id: str)` → `risk_level="safe"`, `timeout_ms=3000`
- [x] Tool `list_active_timers()` → `risk_level="safe"`, `timeout_ms=3000`:
  - Legge dal DB (source of truth), non da dict in-memory
- [x] EventBus: `timer.fired` event con `{timer_id, label}` quando scatta
- [x] **Integrazione calendar**: se `calendar` plugin è attivo e `calendar.reminder` EventBus event arriva, `notifications` può iscriversi a quell'evento per inviare toast — ma NON dichiara `plugin_dependencies=["calendar"]` (soft coupling via EventBus, non hard dep)
- [x] Test: mock winotify, timer create/fire/cancel, persistence/reload su restart, max_active_timers limit, duration fuori range, winotify non disponibile

#### 7.5.3 — Media Control Plugin (`backend/plugins/media_control/`)
- [x] `MediaControlPlugin(BasePlugin)` — `plugin_name = "media_control"`, `plugin_priority = 30`, `plugin_dependencies: list[str] = []`
- [x] **Windows-only** — `check_dependencies()` verifica OS + disponibilità COM:
  - `import sys; sys.platform == "win32"` — se non Windows → tutti i tool restituiscono `ToolResult.error("Media control is Windows-only")`
  - Lazy import: `try: from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume` (COM interface)
- [x] Dipendenze in `pyproject.toml`:
  - **`pycaw >= 20230407`** (Windows Core Audio API wrapper via `comtypes`)
  - `comtypes >= 1.4` (già installato come dep di pycaw, COM interop)
  - `pywin32 >= 306` — già presente come dep di pc_automation (Windows media key simulation)
  - Nessuna collisione: pywin32 è già in pyproject.toml
- [x] `MediaControlConfig(BaseSettings)` in `config.py`:
  - `enabled: bool = False`
  - `volume_step: int = 10` (% per increment/decrement)
  - `brightness_step: int = 10`
- [x] `backend/plugins/media_control/executor.py`:
  - Tutte le funzioni **DEVONO** usare `asyncio.to_thread()` — le API COM sono blocking e non thread-safe sull'event loop
  - `_get_volume_interface()` — inizializza `IAudioEndpointVolume` via `pycaw.pycaw.AudioUtilities.GetSpeakers()`; cache in modulo (reinizializzare se COM disconnessa)
  - `async def exec_get_volume() -> int` — range 0–100 (normalizza da 0.0–1.0 della COM API)
  - `async def exec_set_volume(level: int) -> str` — valida `0 <= level <= 100`, `SetMasterVolumeLevelScalar(level/100)`
  - `async def exec_media_play_pause()` — `win32api.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)` via pywin32
  - `async def exec_media_next() / exec_media_prev()` — idem con `VK_MEDIA_NEXT_TRACK / VK_MEDIA_PREV_TRACK`
  - `async def exec_get_current_media() -> dict` — legge Windows SMTC via `winrt` (opzionale, fallback: `GetForegroundWindow()` + titolo finestra come approssimazione)
  - `async def exec_set_brightness(level: int) -> str` — WMI query `SELECT * FROM WmiMonitorBrightnessMethods`; `asyncio.to_thread` obbligatorio
- [x] Tool `get_volume()` → `risk_level="safe"`, `timeout_ms=3000`
- [x] Tool `set_volume(level: int)` → `risk_level="medium"`, `requires_confirmation=False` (non distruttivo, invertibile), `timeout_ms=3000`
  - **Nota design**: volume NON richiede confirmation per esperienza Jarvis fluida (come abbassare volume fisicamente)
- [x] Tool `volume_up() / volume_down()` → `risk_level="safe"`, usa `volume_step` da config
- [x] Tool `mute() / unmute()` → `risk_level="safe"`
- [x] Tool `media_play_pause() / media_next() / media_previous()` → `risk_level="safe"` (controllo media non distruttivo)
- [x] Tool `get_current_media()` → `risk_level="safe"`, `timeout_ms=3000` — output: `{title?, artist?, album?, app?}`
- [x] Tool `set_brightness(level: int)` → `risk_level="medium"`, `requires_confirmation=False`, `timeout_ms=5000`
  - WMI blocking → sempre `asyncio.to_thread`
  - **Edge case**: monitor non supporta WMI brightness (monitor esterno) → `ToolResult.error("Brightness control not supported for this display")`
- [x] `get_connection_status()`: verifica se COM disponibile → `CONNECTED` / `ERROR`
- [x] **Edge case**: COM interface invalida (es. device audio rimosso) → reinizializza `_get_volume_interface()` al prossimo call invece di crashare
- [x] Test: mock pycaw COM via `unittest.mock`, mock win32api keybd_event, non-Windows → error graceful, COM device rimosso → reinit

#### 7.5.4 — Config e Dipendenze Fase 7.5
- [x] `pyproject.toml` nuove dipendenze:
  - `pyperclip >= 1.9` (clipboard)
  - `winotify >= 1.1` (notifications, Windows only)
  - `pycaw >= 20230407` (media_control, Windows only)
  - `comtypes >= 1.4` (media_control, transitiva di pycaw)
- [x] `config/default.yaml`: sezioni `clipboard:`, `notifications:`, `media_control:` con tutti i defaults
- [x] `backend/core/config.py`: `ClipboardConfig`, `NotificationsConfig`, `MediaControlConfig` + aggiunta a `AliceConfig`

#### 7.5.5 — Test Suite Fase 7.5
- [x] Test clipboard: get/set successo, clipboard binaria → errore, testo > max → truncated, pyperclip assente → errore graceful
- [x] Test notifications (winotify): mock `Notification.show()`, timer create→fire→callback, timer cancel, list_active, max_active_timers exceeded, persistence al restart, `fires_at` nel passato al reload
- [x] Test media_control: mock pycaw `IAudioEndpointVolume`, mock win32api `keybd_event`, non-Windows → errori graceful, volume bounds (0–100), COM device rimosso → reinit
- [x] Test config: env var override (`ALICE_MEDIA_CONTROL__ENABLED=true`), defaults

---

