# O.M.N.I.A. — Project Guidelines

> OMNIA (Orchestrated Modular Network for Intelligent Automation) — assistente AI personale locale.

## Architecture

- **Backend**: Python 3.14, FastAPI, async-first, SQLite via SQLModel, plugin-based
- **Frontend**: Electron + Vue 3 (Composition API) + TypeScript, electron-vite
- **LLM**: LM Studio / Ollama (OpenAI-compatible API)
- **STT**: faster-whisper (CTranslate2)
- **TTS**: Piper TTS (primary), XTTS v2 (optional)
- **Communication**: WebSocket (streaming) + REST API
- **DI**: AppContext pattern

## Project Structure

```
backend/          # Python — pyproject.toml, .venv/
  core/           # App factory, config, context, event bus, plugin system
  services/       # LLM, STT, TTS, audio services
  api/routes/     # FastAPI endpoints
  api/middleware/  # Auth, error handling
  plugins/        # Each plugin: plugin.py + tools.py + business logic
  db/             # database.py, models.py
  tests/          # pytest + pytest-asyncio
frontend/         # Electron — package.json, node_modules/
  src/main/       # Electron main process
  src/preload/    # Context bridge
  src/renderer/   # Vue 3 app (stores, composables, components, views, services, types)
config/           # YAML config, system_prompt.md
models/           # AI model files (gitignored)
scripts/          # PowerShell setup/dev scripts
```

## Code Quality Rules

1. **Coherence** — Read existing code before writing. Never break signatures, endpoints, interfaces, or DB schema.
2. **Readability** — Clean, intuitive, explicit code. A new developer understands it immediately.
3. **Documentation** — Docstrings on public functions (Google-style Python, TSDoc TypeScript). Inline comments for non-obvious logic.
4. **Modularity** — Max ~200 lines per file. Organize by responsibility.
5. **No technical debt** — Implement properly the first time. No TODO/FIXME/hack.
6. **No regressions** — Verify all callers before modifying. Existing tests must pass.
7. **No cascading incompatibilities** — Frontend ↔ Backend ↔ DB must stay consistent.
8. **Function verification** — Before calling a function, verify it exists. Before creating one, verify no duplicate.
9. **Contract consistency** — API endpoints, WS messages, TS types, Pinia stores, and DB models must all agree.
10. **Task-oriented** — One complete logical unit at a time. No partial implementations.

## Code Style

### Python
- Type hints on all functions (params + return)
- `async def` for all I/O operations
- `loguru.logger` (not stdlib logging)
- `pathlib.Path` (not os.path)
- `httpx` (not requests)
- Max line length: 100

### TypeScript/Vue
- `<script setup lang="ts">` exclusively
- No `any` types
- `ref()`, `computed()`, `watch()` — no Options API
- CSS scoped in components

## Build & Test

```powershell
# Backend
cd backend; uv pip install -e ".[dev]"
uvicorn core.app:create_app --factory --reload --port 8000
pytest tests/ -v

# Frontend
cd frontend; npm install; npm run dev
```

## Constraints

- Everything runs locally — NO external paid APIs
- Windows primary target
- All I/O must be async where possible
- Plugin tools must be serializable to JSON for LLM function calling
