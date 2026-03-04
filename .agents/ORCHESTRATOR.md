# O.M.N.I.A. — Agent Orchestration System

> Sistema multi-agent per lo sviluppo di OMNIA.
> Un **orchestratore** (Claude Opus 4.6) coordina **subagent specializzati** (Claude Opus 4.6),
> ciascuno con un dominio, contesto e set di strumenti ben definito.

---

## Filosofia

L'orchestratore NON scrive codice direttamente. Il suo ruolo è:
1. **Analizzare** la richiesta dell'utente
2. **Pianificare** i task (manage_todo_list)
3. **Delegare** ai subagent giusti con prompt precisi
4. **Verificare** l'output di ogni subagent
5. **Integrare** i risultati e gestire le dipendenze tra task

Ogni subagent è **stateless** — riceve un prompt completo con tutto il contesto necessario e restituisce un risultato finale. L'orchestratore mantiene lo stato complessivo.

---

## Code Quality Guidelines (propagate to ALL subagents)

Every subagent prompt MUST enforce these principles:

1. **Coherence** — Read existing code before writing. Never break existing signatures, endpoints, interfaces, or DB schema.
2. **Readability & Simplicity** — Clean, intuitive, explicit code. A new developer understands it immediately.
3. **Detailed Documentation** — Docstrings on all public functions. Inline comments for non-obvious logic. Explain *why*.
4. **Modularity** — Split into multiple files/components. Max ~200 lines per file. Organize by responsibility.
5. **No Technical Debt** — Implement properly the first time. No TODO shortcuts.
6. **No Regressions** — Verify all callers before modifying. Existing tests must still pass.
7. **No Cascading Incompatibilities** — Check every call target exists with correct signature. Frontend ↔ backend ↔ DB must stay consistent.
8. **Function Verification** — Before calling a function, verify it exists. Before creating one, verify no duplicate.
9. **Contract Consistency** — API endpoints, WS messages, types, Pinia stores, and DB models must all agree.
10. **Task-Oriented** — One complete logical unit at a time. No half-implementations.

---

## Subagent Disponibili

| ID | Nome | Specializzazione |
|---|---|---|
| `backend` | Backend Engineer | Python, FastAPI, servizi, DB, plugin |
| `frontend` | Frontend Engineer | Electron, Vue 3, TypeScript, UI/UX |
| `build` | Build & DevOps | Setup, build, packaging, dipendenze |
| `debugger` | Debugger | Analisi errori, fix, diagnostica |
| `docs` | Documentation | README, commenti, docstring, guide |
| `git` | Git Manager | Commit, branch, merge strategy |
| `refactor` | Refactoring | Code quality, pattern, architettura |
| `reviewer` | Code Reviewer | Review, best practices, sicurezza |
| `mcp` | MCP Server | Model Context Protocol, tool integration |
| `test` | Test Engineer | Unit test, integration test, fixtures |

---

## Come Usare

L'orchestratore (tu, Claude Opus 4.6 nella chat principale) chiama i subagent così:

```
runSubagent(
  description: "breve descrizione (3-5 parole)",
  prompt: "<prompt dal file .agents/prompts/{agent_id}.md>"
)
```

### Regole di Orchestrazione

1. **Un subagent alla volta** per task che dipendono l'uno dall'altro
2. **Subagent in parallelo** quando possibile (es. docs + test dopo un'implementazione)
3. **Sempre passare** al subagent: path dei file coinvolti, contesto architetturale, vincoli
4. **Sempre verificare** l'output del subagent prima di passare al successivo
5. **Usare il reviewer** dopo ogni implementazione significativa
6. **Usare il debugger** quando qualcosa non funziona dopo 1 tentativo manuale

### Workflow Tipo per una Feature

```
Utente: "Implementa il LLM service"

Orchestratore:
  1. Pianifica (manage_todo_list)
  2. → backend agent: "Implementa backend/services/llm_service.py" (con spec dettagliate)
  3. Verifica output
  4. → test agent: "Scrivi test per llm_service.py"
  5. → reviewer agent: "Review llm_service.py"
  6. Integra feedback se necessario
  7. → git agent: "Commit feat: implement LLM service"
  8. Aggiorna todo
```

---

## File di Riferimento

- `.agents/ORCHESTRATOR.md` — Questo file (istruzioni orchestratore)
- `.agents/prompts/backend.md` — Prompt per Backend Engineer
- `.agents/prompts/frontend.md` — Prompt per Frontend Engineer
- `.agents/prompts/build.md` — Prompt per Build & DevOps
- `.agents/prompts/debugger.md` — Prompt per Debugger
- `.agents/prompts/docs.md` — Prompt per Documentation
- `.agents/prompts/git.md` — Prompt per Git Manager
- `.agents/prompts/refactor.md` — Prompt per Refactoring
- `.agents/prompts/reviewer.md` — Prompt per Code Reviewer
- `.agents/prompts/mcp.md` — Prompt per MCP Server
- `.agents/prompts/test.md` — Prompt per Test Engineer
