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
│       │ audio        │ json                │ json       │
│       └──────────WebSocket / REST──────────┘            │
└──────────────────────┬──────────────────────────────────┘
                       │  ws://localhost:8000
┌──────────────────────┼───────────────────────────────────┐
│                      ▼      FASTAPI BACKEND              │
│  ┌─────────┐ ┌─────────────┐                             │
│  │ STT Svc │ │ LLM Svc     │──→ LMStudio (:1234)         │
│  │(whisper)│ │(es. Qwen9B) │←── streaming tokens         │
│  └────┬────┘ └────┬────────┘                             │
│       │ text      │ tool calls                           │
│       ▼           ▼                                      │
│  ┌──────────────────────────────┐   ┌─────────┐          │
│  │      Plugin Manager          │   │ TTS Svc │→Speaker  │
│  │ ┌─────┐┌─────┐┌──────┐┌───┐  │   │ (Piper) │          │
│  │ │ PC  ││ IoT ││Search││Cal│  │   └─────────┘          │
│  │ └──┬──┘└──┬──┘└──┬───┘└─┬─┘  │                        │
│  └────┼──────┼──────┼──────┼────┘                        │
└───────┼──────┼──────┼──────┼─────────────────────────────┘
        ▼      ▼      ▼      ▼
     Windows  Home   DDG/   SQLite
     OS APIs  Asst.  SearXNG
              MQTT
```

### Persistenza Conversazioni

```
data/conversations/
├── {uuid}.json          # Una conversazione completa (metadata + messaggi)
├── {uuid}.json
└── ...
```

Ogni conversazione è salvata come file JSON atomico, sincronizzato automaticamente ad ogni modifica. Questo layer fornisce:
- **Durabilità**: i dati sopravvivono a corruzione del DB SQLite
- **Portabilità**: export/import di conversazioni come singoli file JSON
- **Recovery**: ricostruzione completa del DB da file
- **Leggibilità**: formato JSON human-readable per debug e backup

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

| Fase | Titolo | File |
|---|---|---|
| 1 | Setup iniziale (FastAPI + Electron + Vue 3) | [fase-01-setup.md](fase-01-setup.md) |
| 2 | STT — faster-whisper | [fase-02-stt.md](fase-02-stt.md) |
| 3 | TTS — Piper + XTTS | [fase-03-tts.md](fase-03-tts.md) |
| 4 | Plugin System (BasePlugin + PluginManager) | [fase-04-plugin-system.md](fase-04-plugin-system.md) |
| 5 | Plugin: pc_automation, home_automation, web_search, media_control | [fase-05-plugins-base.md](fase-05-plugins-base.md) |
| 6 | Plugin: calendar, notifications, clipboard, weather, news | [fase-06-plugins-extra.md](fase-06-plugins-extra.md) |
| 7 | LLM tool calling + thinking parser + Pinia streaming | [fase-07-llm-toolcalling.md](fase-07-llm-toolcalling.md) |
| 8 | Voice pipeline end-to-end + HybridView | [fase-08-voice-pipeline.md](fase-08-voice-pipeline.md) |
| 9 | Memory Service (vettori + RAG) | [fase-09-memory-service.md](fase-09-memory-service.md) |
| 10 | VRAM monitor + preferences + conversation file manager | [fase-10-services.md](fase-10-services.md) |
| 11 | MCP Client plugin | [fase-11-mcp-client.md](fase-11-mcp-client.md) |
| 12 | Audit di coerenza full-stack (marzo 2026) | [fase-12-coherence-audit.md](fase-12-coherence-audit.md) |
| 13 | Note System (NoteService + plugin + REST + frontend) | [fase-13-note-system.md](fase-13-note-system.md) |
| 14 | Chart Generator (plugin LLM + CAD 3D + frontend) | [fase-14-chart-generator.md](fase-14-chart-generator.md) |
| **15** | **Email Assistant (IMAP/SMTP locale)** | [fase-15-email-assistant.md](fase-15-email-assistant.md) |

