# O.M.N.I.A. — Orchestrated Modular Network for Intelligent Automation

> Assistente AI personale, 100% locale, modulare e estensibile.

---

## Overview

OMNIA è un assistente AI personale ispirato a Jarvis (Iron Man), costruito per funzionare interamente in locale senza dipendenze da servizi cloud a pagamento. L'architettura è modulare (plugin-based) e progettata per essere spostabile su un server dedicato in futuro.

## Hardware Target

| Componente | Spec |
|---|---|
| GPU | NVIDIA RTX 5080 16GB VRAM |
| CPU | AMD Ryzen 9 9950X3D |
| RAM | 32GB DDR5 |
| OS | Windows |

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| LLM locale | LM Studio / Ollama (OpenAI-compatible) + Qwen 3.5 9B (~6GB VRAM, vision nativo) + Thinking (QwQ, DeepSeek R1) |
| STT | faster-whisper large-v3 (~1.5GB VRAM) |
| TTS | Piper TTS (primario, CPU) + XTTS v2 (opzionale, voice cloning) |
| Backend | Python — FastAPI + uvicorn (ASGI) |
| Frontend | Electron + Vue 3 + TypeScript + Pinia (via electron-vite) |
| Comunicazione | WebSocket (streaming) + REST API (CRUD) |
| Database | SQLite + SQLModel |
| PC Automation | pywinauto + pyautogui + pywin32 |
| IoT | Home Assistant REST API + MQTT (paho-mqtt) |
| Ricerca Web | duckduckgo-search (o SearXNG self-hosted) |
| Python Deps | uv |
| Node Deps | npm |

## Architettura

```
┌─────────────────────────────────────────────────────────┐
│               ELECTRON + VUE 3 (Frontend)               │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ Voice UI │  │ Chat UI  │  │ Plugin UIs (dinamiche) │ │
│  └────┬─────┘  └────┬─────┘  └────────────┬───────────┘ │
│       │ audio        │ json                │ json        │
│       └──────────WebSocket / REST──────────┘             │
└──────────────────────┬───────────────────────────────────┘
                       │  ws://localhost:8000
┌──────────────────────┼───────────────────────────────────┐
│                      ▼      FASTAPI BACKEND              │
│  ┌─────────┐ ┌─────────┐                                │
│  │ STT Svc │ │ LLM Svc │──→ Ollama (:11434)             │
│  │(whisper)│ │(Qwen9B) │←── streaming tokens             │
│  └────┬────┘ └────┬────┘                                │
│       │ text      │ tool calls                           │
│       ▼           ▼                                      │
│  ┌──────────────────────────────┐   ┌─────────┐         │
│  │      Plugin Manager          │   │ TTS Svc │→Speaker │
│  │ ┌─────┐┌─────┐┌──────┐┌───┐ │   │ (Piper) │         │
│  │ │ PC  ││ IoT ││Search││Cal│ │   └─────────┘         │
│  │ └──┬──┘└──┬──┘└──┬───┘└─┬─┘ │                       │
│  └────┼──────┼──────┼──────┼────┘                       │
└───────┼──────┼──────┼──────┼─────────────────────────────┘
        ▼      ▼      ▼      ▼
     Windows  Home   DDG/   SQLite
     OS APIs  Asst.  SearXNG
              MQTT
```

## Budget VRAM/RAM

| Componente | VRAM | RAM |
|---|---|---|
| Qwen 3.5 9B (Ollama, vision nativo) | ~6 GB | ~1 GB |
| Thinking models (swap: QwQ, DeepSeek R1) | ~6-10 GB (shared) | ~1 GB |
| faster-whisper large-v3 | ~1.5 GB | ~0.5 GB |
| Piper TTS | 0 | ~0.1 GB |
| FastAPI + Plugin | 0 | ~0.5 GB |
| Electron + Vue | 0 | ~0.3 GB |
| **Totale** | **~7.5 / 16 GB** | **~2.4 / 32 GB** |

## Roadmap

### Fase 0 — Setup Progetto e Toolchain
- [x] Struttura monorepo
- [x] Backend Python (pyproject.toml, venv, deps)
- [x] Frontend Electron + Vue 3 + TS
- [x] Script di setup/dev
- [x] Git init + .gitignore

### Fase 1 — Core Backend + Chat Testuale
- [x] Config system (Pydantic Settings + YAML)
- [x] AppContext (DI container)
- [x] Event Bus asincrono
- [x] FastAPI app factory
- [x] Ollama + Qwen 3.5 9B setup (vision nativo)
- [x] LLM Service con streaming
- [x] WebSocket chat endpoint
- [x] REST chat history
- [x] Database (SQLite + SQLModel)

### Fase 2 — Frontend Base + Chat UI
- [x] Electron window frameless + custom title bar
- [x] WebSocket manager
- [x] LLM stream composable
- [x] Pinia chat store
- [x] Chat UI components (ChatView, MessageBubble, ChatInput, StreamingIndicator)

### Fase 1.5 — Supporto Multimodale + Thinking

- [x] Thinking model support (QwQ, DeepSeek R1) — parsing `<think>` tags + reasoning_content delta
- [x] Thinking token streaming via WebSocket (`type: "thinking"`)
- [x] Frontend thinking display (collapsible reasoning block)
- [x] Vision model support (LLaVA, Qwen2-VL) — multimodal content format
- [x] Image upload endpoint (POST /chat/upload)
- [x] Image attachment UI (paste, drag-drop, file picker)
- [x] Image display in message bubbles
- [x] Attachment DB model + file storage

### Fase 3 — Plugin System
- [ ] BasePlugin ABC
- [ ] PluginManager (discovery, lifecycle)
- [ ] ToolRegistry (aggregazione tool per LLM)
- [ ] Tool calling loop
- [ ] Plugin di esempio: system_info

### Fase 4 — Voce (STT + TTS)
- [ ] faster-whisper + Silero VAD
- [ ] Audio capture service
- [ ] WebSocket voice endpoint
- [ ] Piper TTS + voci italiane
- [ ] Frontend voice composable + UI
- [ ] (Opzionale) XTTS v2 voice cloning

### Fase 5 — Plugin: PC Automation
- [ ] Tools LLM (open/close app, type, keys, screenshot)
- [ ] Executor (pywinauto + pyautogui + subprocess)
- [ ] Layer di conferma per azioni distruttive

### Fase 6 — Plugin: Domotica / IoT
- [ ] Home Assistant client (REST + WS)
- [ ] MQTT client
- [ ] Registro dispositivi unificato

### Fase 7 — Plugin: Ricerca Web + Calendario
- [ ] Web search (DDG / SearXNG)
- [ ] Web scraping (httpx + bs4)
- [ ] Calendario/Task (SQLModel)
- [ ] UI dedicate

### Fase 8 — Polish e Server-readiness
- [ ] System prompt personalizzato
- [ ] Settings UI
- [ ] Global hotkey (Ctrl+Shift+O)
- [ ] Auth JWT per deployment remoto
- [ ] Packaging (PyInstaller + electron-builder)

## Verifiche per Fase

| Fase | Test |
|---|---|
| 1-2 | "Ciao OMNIA" → risposta streammata in italiano |
| 1.5 | Immagine + "Cosa vedi?" → descrizione; Thinking model → blocco ragionamento collassabile |
| 3 | "Quanta RAM uso?" → tool call → risposta naturale |
| 4 | Voce: "Che ore sono?" → risposta vocale |
| 5 | "Apri Notepad" → si apre automaticamente |
| 6 | "Accendi la luce" → luce si accende |
| 7 | "Che tempo fa a Roma?" → ricerca + risposta |
| 8 | Ctrl+Shift+O → attivazione globale |
