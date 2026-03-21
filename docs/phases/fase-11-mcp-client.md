### Fase 11 — MCP Client (Strumenti Esterni via Model Context Protocol)

> **Obiettivo**: permettere a AL\CE di connettersi a qualsiasi server MCP esterno
> (filesystem, database, git, browser, motori di ricerca, ecc.) tramite il
> Model Context Protocol. I tool esposti dai server MCP entrano automaticamente
> nel `ToolRegistry` esistente e diventano disponibili all'LLM — senza modifiche
> al flusso chat, al tool loop o a qualsiasi layer esistente.

- [x] `McpServerConfig` + `McpConfig` in `config.py` + `default.yaml` — §11.1
- [x] `McpSession` service (stdio + SSE transport) — §11.2
- [x] `McpClientPlugin` (aggregazione + dispatch) — §11.3
- [x] Tool namespacing `mcp_{server}_{tool}` — §11.4
- [x] `AliceEvent.MCP_SERVER_CONNECTED` + `MCP_SERVER_DISCONNECTED` — §11.5
- [x] Dipendenza `mcp` in `pyproject.toml` — §11.6
- [x] File structure — §11.7
- [x] Test suite (2 file, 14+ test case) — §11.8

---

#### 11.0 — Analisi Vincoli e Scelte Architetturali

**Perché un Plugin, non un Service:**
- Il pattern "esponi tool all'LLM" è esattamente il contratto di `BasePlugin`
- `get_tools()` + `execute_tool()` è l'interfaccia perfetta per aggregare tool remoti
- Il `PluginManager` gestisce già lifecycle (init/cleanup), crash isolation e health check
- Il `ToolRegistry` aggrega già i tool da tutti i plugin — zero modifiche necessarie
- `AppContext` non richiede nuovi campi — il plugin vive in `plugin_manager` come gli altri

**Perché un Plugin unico (`McpClientPlugin`) e non un plugin per server:**
- Il `PLUGIN_REGISTRY` è statico (popolato a import-time per compatibilità PyInstaller)
- Creare plugin dinamicamente da config violerebbe questo pattern fondamentale
- Un singolo plugin che gestisce N sessioni è il compromesso corretto:
  config-driven, lifecycle unificato, crash isolation a livello di singola sessione

**Perché il SDK ufficiale `mcp` e non raw JSON-RPC:**
- `mcp` è il package ufficiale Anthropic, mantenuto attivamente
- Gestisce transport abstraction (stdio/SSE), capabilities negotiation e framing messaggi
- Riduce il codice AL\CE a ~150 LOC totali senza duplicare logica di protocollo
- Usa `httpx` (già presente) per SSE e `anyio`/`asyncio` per subprocess stdio

**Tool namespacing — `mcp_{server}_{tool}`:**
- I plugin nativi AL\CE usano `{plugin_name}_{tool_name}` (es. `system_info_get_cpu_usage`)
- I tool MCP vengono prefissati `mcp_{server_name}_{tool_name}` da `McpClientPlugin.get_tools()`; il `ToolRegistry` aggiunge il prefisso `mcp_client_` → l’LLM vede `mcp_client_mcp_{server}_{tool}` (es. `mcp_client_mcp_filesystem_read_file`)
- Nessuna collisione possibile: il prefisso `mcp_` non è mai usato da plugin nativi
- Parsing inverso deterministico: iterare le sessioni cercando il prefisso corrispondente

**Nessuna modifica ai layer esistenti:**
- `LLMService`: invariato — il LLM riceve tool in formato OpenAI e li chiama per nome
- `ToolRegistry`: invariato — aggrega `get_tools()` da tutti i plugin incluso `McpClientPlugin`
- `ChatRoute` + `_tool_loop.py`: invariati — `tool_registry.execute_tool(name, args)` funziona già
- `AppContext`: nessun nuovo campo
- Frontend: il plugin card `mcp_client` appare automaticamente nell'UI plugin esistente

**Nessun endpoint REST dedicato (v1):**
- I server MCP si configurano via `config/default.yaml`
- Lo stato è visibile tramite `/api/plugins` (health check esistente)
- Una UI per gestire dinamicamente i server MCP è rinviata a v2

---

#### 11.1 — McpConfig (`backend/core/config.py`)

Nuove classi aggiunte in `config.py`, dopo `MemoryConfig`:

```python
class McpServerConfig(BaseModel):
    """Configuration for a single MCP server connection."""

    name: str
    """Unique identifier (lowercase_snake_case). Used in tool prefix: mcp_{name}_*."""

    transport: Literal["stdio", "sse"] = "stdio"
    """Connection transport: 'stdio' for subprocess, 'sse' for HTTP/SSE."""

    command: list[str] | None = None
    """[stdio only] Command + args to launch the MCP server subprocess.
    Example: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/docs"]
    """

    url: str | None = None
    """[sse only] Full URL of the SSE endpoint.
    Example: "http://localhost:3000/sse"
    """

    env: dict[str, str] = {}
    """Extra environment variables injected into the subprocess (stdio only)."""

    enabled: bool = True
    """Set to false to skip this server without removing it from config."""

    @model_validator(mode="after")
    def _validate_transport_fields(self) -> McpServerConfig:
        if self.transport == "stdio" and not self.command:
            raise ValueError(
                f"MCP server '{self.name}': stdio transport requires 'command'"
            )
        if self.transport == "sse" and not self.url:
            raise ValueError(
                f"MCP server '{self.name}': sse transport requires 'url'"
            )
        return self


class McpConfig(BaseSettings):
    """MCP client configuration."""

    model_config = SettingsConfigDict(env_prefix="ALICE_MCP__")

    servers: list[McpServerConfig] = Field(default_factory=list)
    """List of MCP servers to connect at startup. Empty by default (opt-in)."""
```

Campo aggiunto a `AliceConfig` (dopo `memory`):

```python
mcp: McpConfig = Field(default_factory=McpConfig)
```

Aggiunta in `config/default.yaml` (in fondo, dopo la sezione `memory`):

```yaml
mcp:
  servers: []
  # Esempi di server MCP disponibili (decommentare e configurare per abilitare):
  #
  # - name: filesystem
  #   transport: stdio
  #   command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "C:/Users/utente/documenti"]
  #   enabled: true
  #
  # - name: git
  #   transport: stdio
  #   command: ["uvx", "mcp-server-git", "--repository", "C:/progetti/mio-repo"]
  #   enabled: true
  #
  # - name: brave_search
  #   transport: sse
  #   url: "http://localhost:3001/sse"
  #   enabled: true
```

Il plugin `mcp_client` è **opt-in**: non è nella lista `plugins.enabled` di default.
Per attivarlo: aggiungere `"mcp_client"` a `plugins.enabled` e configurare almeno un server.

---

#### 11.2 — McpSession (`backend/services/mcp_session.py`)

**Ruolo**: gestisce il ciclo di vita di una singola connessione MCP. Non conosce il
plugin, il context AL\CE né il ToolRegistry. Si occupa solo di connettersi, listare
tool e fare dispatch delle chiamate.

```
McpSession
├── start()         — connette al server, invia initialize, chiama tools/list (popola cache)
├── stop()          — chiude la connessione, rilascia subprocess/HTTP client
├── get_tools()     — restituisce la lista ToolDefinition cached (sincrono, post-start)
├── call_tool()     — esegue tools/call e restituisce il testo del risultato
├── status          — CONNECTED | DISCONNECTED | ERROR (property sincrona)
└── server_name     — nome del server (da config.name)
```

Sketch implementativo:

```python
class McpSession:
    """Manages the lifecycle of a single MCP server connection.

    Uses the official `mcp` SDK for transport abstraction (stdio/SSE).
    The tool list is cached after start() to allow synchronous get_tools().

    Args:
        config: The server configuration (name, transport, command/url, env).
    """

    def __init__(self, config: McpServerConfig) -> None:
        self._config = config
        self._status: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self._cached_tools: list[ToolDefinition] = []
        self._session: mcp.ClientSession | None = None
        self._exit_stack: contextlib.AsyncExitStack | None = None

    async def start(self) -> None:
        """Connect, initialize handshake, and cache the tool list.

        Raises:
            RuntimeError: If connection or initialization fails.
        """
        stack = contextlib.AsyncExitStack()
        try:
            if self._config.transport == "stdio":
                read, write = await stack.enter_async_context(
                    mcp.client.stdio.stdio_client(
                        mcp.StdioServerParameters(
                            command=self._config.command[0],
                            args=self._config.command[1:],
                            env={**os.environ, **self._config.env},
                        )
                    )
                )
            else:  # sse
                read, write = await stack.enter_async_context(
                    mcp.client.sse.sse_client(self._config.url)
                )
            session = await stack.enter_async_context(mcp.ClientSession(read, write))
            await session.initialize()
            tools_response = await session.list_tools()
            self._cached_tools = [
                ToolDefinition(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema or {"type": "object", "properties": {}},
                )
                for tool in tools_response.tools
            ]
            self._session = session
            self._exit_stack = stack
            self._status = ConnectionStatus.CONNECTED
        except Exception:
            await stack.aclose()
            self._status = ConnectionStatus.ERROR
            raise

    async def stop(self) -> None:
        """Disconnect and release all resources."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._session = None
        self._status = ConnectionStatus.DISCONNECTED
        self._cached_tools = []

    def get_tools(self) -> list[ToolDefinition]:
        """Return cached tool definitions (populated after start())."""
        return self._cached_tools

    async def call_tool(self, tool_name: str, args: dict) -> str:
        """Execute a tools/call request and return the string result.

        Args:
            tool_name: Original tool name (without mcp_ prefix).
            args: Tool arguments dict.

        Returns:
            String content of the tool result (text blocks joined by newline).

        Raises:
            RuntimeError: If the session is not connected.
        """
        if self._session is None or self._status != ConnectionStatus.CONNECTED:
            raise RuntimeError(
                f"MCP server '{self._config.name}' is not connected"
            )
        result = await self._session.call_tool(tool_name, args)
        return "\n".join(
            block.text for block in result.content if hasattr(block, "text")
        )

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    @property
    def server_name(self) -> str:
        return self._config.name
```

**Nota sul ciclo di vita**: `start()` usa `AsyncExitStack` per gestire i context manager
del SDK MCP senza mantenere attivi blocchi `with`. `stop()` chiude lo stack, propagando
le chiusure al trasporto e al processo subprocess.

---

#### 11.3 — McpClientPlugin (`backend/plugins/mcp_client/plugin.py`)

**Ruolo**: plugin AL\CE che gestisce N sessioni MCP, aggrega i loro tool nel ToolRegistry
e fa dispatch delle esecuzioni alla sessione corretta.

```
McpClientPlugin
├── initialize(ctx)   — avvia tutte le sessioni enabled (crash-isolated per sessione)
├── cleanup()         — ferma tutte le sessioni ordinatamente
├── get_tools()       — aggrega ToolDefinition da tutte le sessioni CONNECTED
├── execute_tool()    — parsing prefisso → dispatch a McpSession.call_tool()
├── get_connection_status()  — CONNECTED se tutte ok, DEGRADED se alcune, ERROR se nessuna
└── get_status()      — dict {server_name: status} per health detail
```

```python
class McpClientPlugin(BasePlugin):
    """Bridges AL\CE to external MCP servers.

    At startup, connects to every enabled server in config.mcp.servers.
    Each server's tools are namespaced as mcp_{server_name}_{tool_name}
    and exposed via get_tools(), making them available to the LLM.
    """

    plugin_name = "mcp_client"
    plugin_version = "1.0.0"
    plugin_description = (
        "Bridges AL\CE to external MCP servers "
        "(filesystem, git, browser, search engine, …)"
    )

    def __init__(self) -> None:
        super().__init__()
        self._sessions: dict[str, McpSession] = {}

    async def initialize(self, ctx: AppContext) -> None:
        await super().initialize(ctx)
        for server_cfg in ctx.config.mcp.servers:
            if not server_cfg.enabled:
                continue
            session = McpSession(server_cfg)
            try:
                await session.start()
                self._sessions[server_cfg.name] = session
                self.logger.info(
                    "MCP '{}' connesso ({} tool)",
                    server_cfg.name,
                    len(session.get_tools()),
                )
                await ctx.event_bus.emit(
                    AliceEvent.MCP_SERVER_CONNECTED, server=server_cfg.name,
                )
            except Exception as exc:
                self.logger.error("MCP '{}' fallito: {}", server_cfg.name, exc)
                await ctx.event_bus.emit(
                    AliceEvent.MCP_SERVER_DISCONNECTED,
                    server=server_cfg.name,
                    reason=str(exc),
                )

    async def cleanup(self) -> None:
        for session in self._sessions.values():
            try:
                await session.stop()
            except Exception as exc:
                self.logger.warning(
                    "Errore chiusura MCP '{}': {}", session.server_name, exc,
                )
        self._sessions.clear()

    def get_tools(self) -> list[ToolDefinition]:
        tools: list[ToolDefinition] = []
        for server_name, session in self._sessions.items():
            if session.status != ConnectionStatus.CONNECTED:
                continue
            for tool in session.get_tools():
                tools.append(ToolDefinition(
                    name=f"mcp_{server_name}_{tool.name}",
                    description=f"[{server_name}] {tool.description}",
                    parameters=tool.parameters,
                ))
        return tools

    async def execute_tool(
        self, tool_name: str, args: dict, context: ExecutionContext,
    ) -> ToolResult:
        for server_name, session in self._sessions.items():
            prefix = f"mcp_{server_name}_"
            if tool_name.startswith(prefix):
                original = tool_name[len(prefix):]
                try:
                    content = await session.call_tool(original, args)
                    return ToolResult(success=True, content=content)
                except Exception as exc:
                    return ToolResult(success=False, error_message=str(exc))
        return ToolResult(
            success=False,
            error_message=f"Tool MCP non trovato: {tool_name}",
        )

    async def get_connection_status(self) -> ConnectionStatus:
        if not self._sessions:
            return ConnectionStatus.CONNECTED  # nessun server configurato ≠ errore
        connected = sum(
            1 for s in self._sessions.values()
            if s.status == ConnectionStatus.CONNECTED
        )
        if connected == len(self._sessions):
            return ConnectionStatus.CONNECTED
        return ConnectionStatus.DEGRADED if connected > 0 else ConnectionStatus.ERROR

    async def get_status(self) -> dict[str, str]:
        """Return per-server connection status for health reporting."""
        return {name: s.status.value for name, s in self._sessions.items()}
```

`backend/plugins/mcp_client/__init__.py` — registrazione nel registry statico:

```python
from backend.core.plugin_manager import PLUGIN_REGISTRY
from backend.plugins.mcp_client.plugin import McpClientPlugin

PLUGIN_REGISTRY["mcp_client"] = McpClientPlugin
```

---

#### 11.4 — Tool Namespacing

| MCP Server | Tool originale | Nome in `get_tools()` | Nome visibile all'LLM (ToolRegistry) |
|---|---|---|---|
| `filesystem` | `read_file` | `mcp_filesystem_read_file` | `mcp_client_mcp_filesystem_read_file` |
| `filesystem` | `write_file` | `mcp_filesystem_write_file` | `mcp_client_mcp_filesystem_write_file` |
| `git` | `git_log` | `mcp_git_git_log` | `mcp_client_mcp_git_git_log` |
| `brave_search` | `brave_web_search` | `mcp_brave_search_brave_web_search` | `mcp_client_mcp_brave_search_brave_web_search` |
| `postgres` | `query` | `mcp_postgres_query` | `mcp_client_mcp_postgres_query` |

**Regola di parsing in `execute_tool`**: il `ToolRegistry` passa a `plugin.execute_tool()` il
`tool_def.name` originale (es. `mcp_filesystem_read_file`), non il nome completo con prefisso
esterno (`mcp_client_mcp_filesystem_read_file`). Il plugin itera le sessioni cercando il server
il cui `f"mcp_{name}_"` è un prefisso di `tool_name`, quindi estrae il nome MCP originale.

**Collisioni impossibili per construction**: il prefisso `mcp_` non è mai usato nei
plugin nativi AL\CE (tutti usano `{plugin_name}_` senza tale prefisso).

**Nome server con caratteri speciali**: il `name` deve essere `lowercase_snake_case`
(validato da `McpServerConfig`). Nomi come `brave-search` devono essere scritti come
`brave_search` nella config.

---

#### 11.5 — AliceEvent (`backend/core/event_bus.py`)

Due nuovi eventi aggiunti all'enum `AliceEvent`:

```python
MCP_SERVER_CONNECTED = "mcp.server.connected"
"""Emesso con server=str quando un server MCP si connette con successo."""

MCP_SERVER_DISCONNECTED = "mcp.server.disconnected"
"""Emesso con server=str, reason=str quando un server MCP fallisce o si disconnette."""
```

---

#### 11.6 — Dipendenza (`pyproject.toml`)

```toml
[project.dependencies]
mcp = ">=1.0"
```

Nessun'altra dipendenza. Il SDK `mcp` usa internamente:
- `httpx` — già presente nel progetto (per SSE transport)
- `anyio` — già presente come dipendenza transitiva di FastAPI (per subprocess stdio)

---

#### 11.7 — File Structure Fase 11

```
backend/
├── services/
│   └── mcp_session.py              ← McpSession (connessione singolo server MCP)
├── plugins/
│   └── mcp_client/
│       ├── __init__.py             ← PLUGIN_REGISTRY["mcp_client"] = McpClientPlugin
│       └── plugin.py              ← McpClientPlugin (aggregazione N sessioni)
├── core/
│   ├── config.py                  ← + McpServerConfig + McpConfig + AliceConfig.mcp
│   └── event_bus.py               ← + MCP_SERVER_CONNECTED + MCP_SERVER_DISCONNECTED
└── tests/
    ├── test_mcp_session.py        ← unit test McpSession (mock mcp SDK)
    └── test_mcp_client_plugin.py  ← unit test McpClientPlugin (mock McpSession)

config/
└── default.yaml                   ← + sezione mcp.servers (lista vuota default)
```

Nessun file modificato nei layer esistenti: `app.py`, `protocols.py`, `context.py`,
`tool_registry.py`, `plugin_manager.py`, `routes/`, frontend.

---

#### 11.8 — Test Suite

**`backend/tests/test_mcp_session.py`**:
- `test_start_stdio_success`: mock `stdio_client` + `ClientSession` → `start()` → status CONNECTED, tool cache popolata
- `test_start_sse_success`: mock `sse_client` → stesso flusso con `url` come parametro
- `test_start_failure_sets_error_status`: eccezione in `session.initialize()` → status ERROR, `_cached_tools == []`
- `test_start_failure_closes_exit_stack`: eccezione → `AsyncExitStack.aclose()` chiamato (no resource leak)
- `test_call_tool_success`: sessione CONNECTED → `call_tool("read_file", {...})` → stringa risultato
- `test_call_tool_disconnected_raises`: sessione DISCONNECTED → `call_tool(...)` → `RuntimeError`
- `test_stop_resets_state`: `start()` → `stop()` → `status == DISCONNECTED`, `get_tools() == []`

**`backend/tests/test_mcp_client_plugin.py`**:
- `test_initialize_starts_all_enabled_sessions`: 2 server enabled + 1 disabled → 2 sessioni avviate
- `test_initialize_isolates_session_failure`: server A ok, server B crash → plugin inizializzato, A in `_sessions`, B escluso
- `test_initialize_emits_events`: server connesso → `MCP_SERVER_CONNECTED` emesso; server fallito → `MCP_SERVER_DISCONNECTED` emesso
- `test_get_tools_aggregates_from_connected`: 2 sessioni 3 tool ciascuna → 6 tool con prefisso `mcp_{server}_`
- `test_get_tools_skips_disconnected`: sessione con status ERROR → tool non inclusi
- `test_execute_tool_dispatches_to_correct_session`: `mcp_filesystem_read_file` → sessione `filesystem`
- `test_execute_tool_unknown_returns_failure`: tool senza prefisso valido → `ToolResult(success=False)`
- `test_get_connection_status_all_connected`: tutte le sessioni CONNECTED → `ConnectionStatus.CONNECTED`
- `test_get_connection_status_partial`: 1 su 2 CONNECTED → `ConnectionStatus.DEGRADED`
- `test_get_connection_status_none_connected`: zero sessioni CONNECTED → `ConnectionStatus.ERROR`
- `test_get_connection_status_no_servers`: `_sessions` vuoto → `ConnectionStatus.CONNECTED`
- `test_cleanup_stops_all_sessions`: `cleanup()` → `stop()` chiamato su ogni sessione

**Verifica no-regression** (pre-PR): tutta la suite esistente deve passare invariata.

---

#### 11.9 — Ordine di Implementazione

1. `McpServerConfig` + `McpConfig` in `config.py` + `default.yaml`
2. `AliceEvent.MCP_SERVER_CONNECTED` + `MCP_SERVER_DISCONNECTED` in `event_bus.py`
3. `mcp >= 1.0` in `pyproject.toml` + `uv pip install -e ".[dev]"` ← dipendenza SDK necessaria prima di `mcp_session.py`
4. `McpSession` service (`backend/services/mcp_session.py`)
5. `McpClientPlugin` (`backend/plugins/mcp_client/__init__.py` + `plugin.py`)
6. Test suite completa
7. Aggiungere `"mcp_client"` a `plugins.enabled` in `default.yaml` + configurare almeno un server per il test manuale

---

#### 11.10 — Verifiche Fase 11

| Scenario | Comportamento atteso |
|---|---|
| `mcp.servers: []` (default) | Plugin si carica, `get_tools()` restituisce `[]`, `get_connection_status()` CONNECTED, zero impatto su test esistenti |
| Server stdio con NPX filesystem | Subprocess lanciato, tool listati, `mcp_client_mcp_filesystem_*` disponibili all'LLM |
| LLM chiama `mcp_client_mcp_filesystem_read_file` con path valido | Dispatch a `McpSession.call_tool("read_file", {...})` → contenuto file come `ToolResult` |
| LLM chiama tool con path fuori directory permessa | Il server MCP restituisce errore → `ToolResult(success=False, error_message=...)` → messaggio user-friendly |
| Server SSE non raggiungibile all'avvio | Status ERROR, evento `MCP_SERVER_DISCONNECTED` emesso, altri plugin e chat funzionanti |
| Un server crasha durante `initialize()` | Solo quel server escluso; altri server connessi normalmente; plugin inizializzato |
| Tool call verso sessione ERROR | `ToolResult(success=False)` con error_message, nessun crash plugin |
| `GET /api/plugins` | Plugin card `mcp_client` presente con status CONNECTED/DEGRADED/ERROR |
| `mcp_client` non in `plugins.enabled` | Plugin non caricato, zero tool MCP nel ToolRegistry, zero overhead |

---

---

