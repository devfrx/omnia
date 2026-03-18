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

