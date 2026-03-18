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

