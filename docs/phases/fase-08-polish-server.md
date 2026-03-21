### Fase 8 — Polish e Server-readiness

#### 8.1 — System Prompt & Settings
- [ ] System prompt personalizzabile da UI Settings
- [ ] Editor system prompt con preview (markdown)
- [ ] Settings UI completa: modello LLM, temperatura, max tokens, lingua, tema, plugin on/off
- [ ] **Settings persistence**: salvare su file `config/user.yaml` (overlay su `default.yaml`)
- [ ] REST: `GET/PUT /api/config` per leggere/scrivere settings
- [ ] **Plugin settings**: auto-generate form dalla `get_config_schema()` di ogni plugin
- [ ] Global hotkey: `Ctrl+Shift+O` → attivazione finestra AL\CE (Electron `globalShortcut`)

#### 8.2 — Auth JWT per Deployment Remoto
- [ ] `AuthConfig`: `enabled: bool = False` (local: off), `jwt_secret: SecretStr`, `jwt_algorithm: str = "HS256"`, `token_expiry: int = 3600`
- [ ] Middleware FastAPI: validazione JWT su tutte le route REST quando `auth.enabled = True`
- [ ] **WebSocket auth**: dopo `accept()`, primo messaggio dev'essere `{"type": "auth", "token": "..."}` — timeout 5s, altrimenti `close(403)`
- [ ] Login endpoint: `POST /api/auth/login` → JWT token
- [ ] **Secret management per produzione**: JWT secret da env var `ALICE_JWT_SECRET`, MAI in config file

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
  - Shared data directory: `%APPDATA%\AL\CE` (Win), `~/Library/Application Support/AL\CE` (macOS), `~/.config/alice` (Linux)
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
| `calendar_reminder` | 7.2 | S→C | `{event_id, title, minutes_until}` |
| `timer_fired` | 7.5 | S→C | `{timer_id, label}` |
| `auth` | 8 | C→S | `{token}` |
| `memory_updated` | 9 | S→C | `{memory_id, operation}` |

---

