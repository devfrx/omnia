## Fase 14 — Generazione Grafici Interattivi (Chart Generator)

> **Obiettivo**: aggiungere all'agente la capacità di generare grafici interattivi e di
> renderizzarli direttamente nella chat. I dati possono provenire da qualsiasi fonte
> gestita dall'LLM: note del vault (Fase 13), allegati immagine/CSV via vision,
> risultati di ricerca web, o dati forniti direttamente nel prompt.
> I grafici sono persistiti su disco con un ID univoco e possono essere
> aggiornati, recuperati o eliminati nelle conversazioni successive tramite i tool dedicati.
>
> **Pattern architetturale**: `chart_generator` segue esattamente il pattern di
> `cad_generator` (Fase 12): plugin-only (no service separato), `ToolResult` con
> `content_type='application/vnd.omnia.chart+json'`, REST proxy `/api/charts/`,
> `ChartViewer.vue` lazy-loaded via `defineAsyncComponent` in `MessageBubble.vue`.
> La libreria di rendering è **Apache ECharts** (utilizzo diretto senza wrapper Vue,
> consistente con il pattern Three.js in `CADViewer.vue`).

- [x] §14.1 `ChartConfig` in `backend/core/config.py`
- [x] §14.2 Modello dati `ChartSpec`, `ChartPayload`, `ChartListItem` (Pydantic)
- [x] §14.3 `ChartStore` — persistenza JSON in `data/charts/`
- [x] §14.4 Plugin `ChartGeneratorPlugin` (5 tool LLM)
- [x] §14.5 REST API `/api/charts/` — 3 endpoint
- [x] §14.6 Frontend: `ChartPayload` in `types/chat.ts` + `ChartViewer.vue` + aggiornamenti `MessageBubble.vue` e `ToolExecutionIndicator.vue`
- [x] §14.7 System prompt aggiornato
- [x] §14.8 Dipendenze
- [x] §14.9 Struttura file
- [x] §14.10 Test suite
- [x] §14.11 Ordine di implementazione
- [x] §14.12 Verifiche

---

### §14.0 — Scelte architetturali

**Perché plugin e non service?**
Il sistema non richiede una vera service layer: non c'è embeddings, full-text search,
né logica di routing complessa. Il plugin gestisce direttamente lo storage tramite
`ChartStore` e delega all'LLM tutta la fase di estrazione e formattazione dei dati.
Questo è identico al pattern di `cad_generator`, che ha un plugin senza service associato.

**Perché Apache ECharts?**
ECharts usa una configurazione interamente JSON-dichiarativa (`option` object) che
gli LLM conoscono molto bene. Supporta 20+ tipi di grafico (bar, line, pie, scatter,
heatmap, sankey, candlestick, radar, treemap, …) contro ~8 di Chart.js.
La visualizzazione è interattiva (zoom, tooltip, legend toggle) out-of-the-box.

**Perché utilizzo diretto di ECharts (no vue-echarts)?**
`CADViewer.vue` usa Three.js direttamente (`import * as THREE from 'three'`), senza
wrapper Vue. La stessa scelta si applica a ECharts per coerenza: `import * as echarts from 'echarts'`,
mount manuale nel `div` container, `onMounted`/`onUnmounted` per lifecycle Composition API.
Evita la dipendenza `vue-echarts` e il suo overhead di reattività.

**Perché JSON file e non SQLite?**
I chart spec sono blob JSON arbitrari di dimensione variabile (5 KB – 300 KB).
SQLite è ottimale per query strutturate; JSON files sono migliori per blob opachi
non interrogabili. Il `ChartStore` è analogo a `ConversationFileManager` (Fase 1.6):
file `.json` in `data/charts/`, no migrations, no schema.

**Perché il payload `ToolResult` non include la `echarts_option` inline?**
`MAX_TOOL_RESULT_LENGTH = 15_000`. Un chart con dataset medio (100–500 punti) può
eccedere facilmente questo limite. La soluzione è salvare la spec su disco e mettere
nel `ToolResult` solo i metadati (`chart_id`, `title`, `chart_type`, `chart_url`).
`ChartViewer.vue` effettua una GET a `/api/charts/{chart_id}` per caricare la spec completa.
Identico al pattern `CADViewer.vue` → `/api/cad/models/{name}`.

**Separazione responsabilità LLM / plugin:**
Il plugin è un puro "salva e servi". L'LLM è responsabile di:
- leggere i dati sorgente (via `read_note`, `web_search`, vision su immagini/CSV)
- costruire l'oggetto `echarts_option` (conosce il formato dalla documentazione)
- scegliere il tipo di grafico appropriato
- chiamare `generate_chart` con l'option pronta

---

### §14.1 — Configurazione

**`backend/core/config.py`** — aggiungere la classe e il campo:

```python
class ChartConfig(BaseSettings):
    """Configurazione plugin chart_generator."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_CHART__")

    enabled: bool = False
    """Abilita il plugin chart_generator (opt-in, come tutti i plugin OMNIA)."""

    chart_output_dir: str = "data/charts"
    """Directory dove vengono salvati i chart spec JSON."""

    max_option_chars: int = 10_000
    """Dimensione massima della echarts_option serializzata (in caratteri).

    L'LLM deve aggregare i dati prima di chiamare generate_chart se il
    dataset supera questo limite.
    """

    max_charts: int = 1_000
    """Numero massimo di grafici persistiti. Oltre questo limite, generate_chart
    restituisce un errore con istruzioni per eliminare grafici vecchi.
    """
```

Nella classe `OmniaConfig`:

```python
chart: ChartConfig = Field(default_factory=ChartConfig)
```

**`config/default.yaml`** — aggiungere sezione:

```yaml
chart:
  enabled: true
  chart_output_dir: "data/charts"
  max_option_chars: 10000
  max_charts: 1000
```

---

### §14.2 — Modello dati

**`backend/plugins/chart_generator/models.py`**

I modelli Pydantic definiscono il contratto interno al plugin e il JSON salvato
su disco. Non è un `SQLModel` perché lo storage è file-based.

```python
"""Modelli Pydantic per il plugin chart_generator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class ChartSpec(BaseModel):
    """Specifica completa di un grafico, persistita su disco.

    Ogni istanza corrisponde a un file `data/charts/{chart_id}.json`.
    """

    chart_id: str
    """UUID v4 identificativo univoco."""

    title: str
    """Titolo leggibile del grafico, usato in UI e nei tool list."""

    chart_type: str
    """Tipo principale del grafico (bar, line, pie, scatter, …).

    Informativo — il tipo effettivo è determinato da `echarts_option.series[].type`.
    """

    description: str = ""
    """Breve descrizione della fonte dati e dello scopo del grafico."""

    echarts_option: dict[str, Any]
    """Configurazione Apache ECharts completa (option object).

    Esempio minimo:
    {
      "title": {"text": "Vendite Q1"},
      "xAxis": {"type": "category", "data": ["Gen", "Feb", "Mar"]},
      "yAxis": {"type": "value"},
      "series": [{"type": "bar", "data": [150, 230, 180]}]
    }
    """

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ChartPayload(BaseModel):
    """Payload serializzato nel `ToolResult.content`.

    Piccolo subset della ChartSpec — non include `echarts_option`.
    Questo è il JSON che viene salvato nel DB come contenuto del messaggio tool.
    Deve restare sincronizzato con l'interfaccia TypeScript `ChartPayload` nel frontend.
    """

    chart_id: str
    title: str
    chart_type: str
    chart_url: str
    """URL relativo `/api/charts/{chart_id}` per caricare la spec completa."""
    created_at: datetime


class ChartListItem(BaseModel):
    """Elemento della lista grafici — usato da `list_charts` e `GET /api/charts`."""

    chart_id: str
    title: str
    chart_type: str
    description: str
    created_at: datetime
    updated_at: datetime
```

---

### §14.3 — ChartStore

**`backend/plugins/chart_generator/chart_store.py`**

Gestisce la persistenza dei grafici come file JSON in `data/charts/`.
Pattern identico a `ConversationFileManager` (`backend/services/conversation_file_manager.py`):
tutto l'I/O file sincrono viene eseguito in un thread separato via `asyncio.to_thread`.

```python
"""ChartStore — persistenza JSON per i grafici generati dall'agente."""

from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from .models import ChartListItem, ChartSpec


class ChartStore:
    """Gestisce il salvataggio e il recupero dei grafici su disco.

    Ogni grafico viene salvato come `{chart_output_dir}/{chart_id}.json`.
    """

    def __init__(self, chart_output_dir: str | Path) -> None:
        self._dir = Path(chart_output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Operazioni pubbliche (async)
    # ------------------------------------------------------------------

    async def save(self, spec: ChartSpec) -> None:
        """Salva un nuovo grafico su disco."""
        await asyncio.to_thread(self._write, spec)

    async def load(self, chart_id: str) -> ChartSpec | None:
        """Carica un grafico dal disco. Restituisce None se non trovato."""
        return await asyncio.to_thread(self._read, chart_id)

    async def update(self, chart_id: str, new_spec: ChartSpec) -> bool:
        """Sovrascrive la spec di un grafico esistente.

        Args:
            chart_id: ID del grafico da aggiornare.
            new_spec: Nuova spec — ``new_spec.chart_id`` deve corrispondere a ``chart_id``.

        Returns:
            True se aggiornato, False se il file non esiste.

        Raises:
            ValueError: Se ``new_spec.chart_id`` non coincide con ``chart_id``.
        """
        if new_spec.chart_id != chart_id:
            raise ValueError(
                f"chart_id mismatch: atteso {chart_id!r}, ricevuto {new_spec.chart_id!r}"
            )
        path = self._path(chart_id)
        if not await asyncio.to_thread(path.exists):
            return False
        await asyncio.to_thread(self._write, new_spec)
        return True

    async def delete(self, chart_id: str) -> bool:
        """Elimina un grafico dal disco.

        Returns:
            True se eliminato, False se non trovato.
        """
        path = self._path(chart_id)
        deleted = await asyncio.to_thread(self._unlink, path)
        if deleted:
            logger.info(f"Chart eliminato: {chart_id}")
        return deleted

    async def list(self, limit: int = 50, offset: int = 0) -> list[ChartListItem]:
        """Restituisce la lista dei grafici persistiti, ordinata per data di modifica decrescente."""
        return await asyncio.to_thread(self._list_sync, limit, offset)

    async def count(self) -> int:
        """Restituisce il numero totale di grafici salvati."""
        return await asyncio.to_thread(self._count_sync)

    # ------------------------------------------------------------------
    # Metodi sincroni (eseguiti in thread pool via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _path(self, chart_id: str) -> Path:
        # Sanitizzazione: accetta solo caratteri alfanumerici e trattini (UUID format).
        # Previene path traversal — `../../../etc/passwd` diventa `etcpasswd`.
        safe_id = "".join(c for c in chart_id if c.isalnum() or c == "-")
        if not safe_id:
            raise ValueError(f"chart_id non valido (nessun carattere sicuro): {chart_id!r}")
        return self._dir / f"{safe_id}.json"

    def _write(self, spec: ChartSpec) -> None:
        path = self._path(spec.chart_id)
        path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    def _read(self, chart_id: str) -> ChartSpec | None:
        path = self._path(chart_id)
        if not path.exists():
            return None
        try:
            return ChartSpec.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
                logger.exception(f"Errore lettura chart {chart_id}")

    def _unlink(self, path: Path) -> bool:
        if path.exists():
            path.unlink()
            return True
        return False

    def _list_sync(self, limit: int, offset: int) -> list[ChartListItem]:
        def _mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except FileNotFoundError:
                return 0.0

        files = sorted(
            self._dir.glob("*.json"),
            key=_mtime,
            reverse=True,
        )
        page = files[offset : offset + limit]
        items: list[ChartListItem] = []
        for f in page:
            try:
                spec = ChartSpec.model_validate_json(f.read_text(encoding="utf-8"))
                items.append(
                    ChartListItem(
                        chart_id=spec.chart_id,
                        title=spec.title,
                        chart_type=spec.chart_type,
                        description=spec.description,
                        created_at=spec.created_at,
                        updated_at=spec.updated_at,
                    )
                )
            except Exception:
                logger.warning(f"Grafico non leggibile: {f.name} (ignorato)")
        return items

    def _count_sync(self) -> int:
        return sum(1 for _ in self._dir.glob("*.json"))
```

---

### §14.4 — Plugin ChartGeneratorPlugin

**`backend/plugins/chart_generator/__init__.py`**

```python
"""O.M.N.I.A. — Chart Generator plugin package.

Importing this module registers ChartGeneratorPlugin in the static PLUGIN_REGISTRY
so the plugin manager can discover it.
"""

from backend.core.plugin_manager import PLUGIN_REGISTRY
from backend.plugins.chart_generator.plugin import ChartGeneratorPlugin  # noqa: F401

PLUGIN_REGISTRY["chart_generator"] = ChartGeneratorPlugin
```

**`backend/plugins/chart_generator/plugin.py`**

Il plugin implementa 5 tool. Non ha dipendenze dal plugin registry (`depends_on = []`).

```python
"""Plugin chart_generator — genera, aggiorna e gestisce grafici ECharts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from backend.core.plugin_base import BasePlugin
from backend.core.plugin_models import ExecutionContext, ToolDefinition, ToolResult

from .chart_store import ChartStore
from .models import ChartPayload, ChartSpec

if TYPE_CHECKING:
    from backend.core.context import AppContext

_GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Titolo del grafico (max 255 caratteri).",
            "maxLength": 255,
        },
        "chart_type": {
            "type": "string",
            "description": (
                "Tipo principale del grafico. Esempi: bar, line, pie, scatter, "
                "radar, heatmap, sankey, candlestick, treemap, funnel."
            ),
        },
        "echarts_option": {
            "type": "object",
            "description": (
                "Configurazione Apache ECharts completa (option object). "
                "Deve includere almeno: title, series. Includere xAxis/yAxis "
                "per grafici cartesiani, legend e tooltip per interattività. "
                "Il formato è identico alla documentazione ufficiale ECharts."
            ),
            "additionalProperties": True,
        },
        "description": {
            "type": "string",
            "description": "Breve descrizione della fonte dati e dello scopo del grafico.",
            "maxLength": 500,
        },
    },
    "required": ["title", "chart_type", "echarts_option"],
}

_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "chart_id": {
            "type": "string",
            "description": "UUID del grafico da aggiornare.",
        },
        "echarts_option": {
            "type": "object",
            "description": "Nuova configurazione ECharts completa che sostituisce la precedente.",
            "additionalProperties": True,
        },
        "title": {
            "type": "string",
            "description": "Nuovo titolo (opzionale — omettere per mantenere il titolo corrente).",
            "maxLength": 255,
        },
    },
    "required": ["chart_id", "echarts_option"],
}

_GET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "chart_id": {
            "type": "string",
            "description": "UUID del grafico da recuperare.",
        },
    },
    "required": ["chart_id"],
}

_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "description": "Numero massimo di grafici da restituire (default 20, max 100).",
            "default": 20,
            "minimum": 1,
            "maximum": 100,
        },
        "offset": {
            "type": "integer",
            "description": "Numero di grafici da saltare per paginazione (default 0).",
            "default": 0,
            "minimum": 0,
        },
    },
}

_DELETE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "chart_id": {
            "type": "string",
            "description": "UUID del grafico da eliminare definitivamente.",
        },
    },
    "required": ["chart_id"],
}


class ChartGeneratorPlugin(BasePlugin):
    """Plugin per la generazione di grafici interattivi Apache ECharts.

    L'LLM costruisce autonomamente la `echarts_option` JSON dai dati
    disponibili (note, vision, ricerca web, prompt). Il plugin si occupa
    di persistere la spec su disco e di restituire un `ToolResult` con
    `content_type='application/vnd.omnia.chart+json'` che il frontend
    renderizza come `ChartViewer.vue`.
    """

    plugin_name: str = "chart_generator"
    plugin_version: str = "1.0.0"
    plugin_description: str = "Genera grafici interattivi ECharts da qualsiasi fonte dati."
    plugin_dependencies: list[str] = []
    plugin_priority: int = 25

    def __init__(self) -> None:
        super().__init__()
        self._store: ChartStore | None = None

    async def initialize(self, ctx: "AppContext") -> None:
        await super().initialize(ctx)
        cfg = ctx.config.chart
        if not cfg.enabled:
            self.logger.info("Plugin chart_generator disabilitato dalla configurazione.")
            return
        self._store = ChartStore(cfg.chart_output_dir)
        self.logger.info(f"ChartGeneratorPlugin inizializzato (dir={cfg.chart_output_dir})")

    async def cleanup(self) -> None:
        self._store = None
        await super().cleanup()

    def get_tools(self) -> list[ToolDefinition]:
        if not self.ctx.config.chart.enabled:
            return []
        return [
            ToolDefinition(
                name="generate_chart",
                description=(
                    "Genera un grafico interattivo Apache ECharts e lo persiste su disco. "
                    "L'output viene visualizzato direttamente nella chat come viewer interattivo. "
                    "Costruisci l'echarts_option in base ai dati raccolti (note, vision, web, prompt). "
                    "Usa questo tool SOLO dopo aver raccolto tutti i dati necessari."
                ),
                parameters=_GENERATE_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=30_000,
            ),
            ToolDefinition(
                name="update_chart",
                description=(
                    "Aggiorna la configurazione ECharts di un grafico esistente. "
                    "Usa il chart_id restituito da generate_chart o list_charts. "
                    "L'intera echarts_option viene sostituita con la nuova versione."
                ),
                parameters=_UPDATE_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=15_000,
            ),
            ToolDefinition(
                name="get_chart",
                description=(
                    "Recupera i metadati e la echarts_option di un grafico salvato. "
                    "Utile per leggere un grafico esistente prima di aggiornarlo."
                ),
                parameters=_GET_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=5_000,
            ),
            ToolDefinition(
                name="list_charts",
                description=(
                    "Elenca i grafici persistiti nel vault, ordinati dal più recente. "
                    "Restituisce chart_id, title, chart_type, description e date."
                ),
                parameters=_LIST_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=5_000,
            ),
            ToolDefinition(
                name="delete_chart",
                description=(
                    "Elimina definitivamente un grafico dal disco. L'operazione è irreversibile."
                ),
                parameters=_DELETE_SCHEMA,
                risk_level="medium",
                requires_confirmation=True,
                timeout_ms=5_000,
            ),
        ]

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """Dispatch al metodo privato corrispondente al tool_name."""
        if not self.ctx.config.chart.enabled:
            return ToolResult(success=False, content="Plugin chart_generator non abilitato.")

        handlers = {
            "generate_chart": self._generate_chart,
            "update_chart": self._update_chart,
            "get_chart": self._get_chart,
            "list_charts": self._list_charts,
            "delete_chart": self._delete_chart,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return ToolResult(success=False, content=f"Tool sconosciuto: {tool_name}")
        return await handler(args)

    # ------------------------------------------------------------------
    # Implementazioni tool private
    # ------------------------------------------------------------------

    async def _generate_chart(self, args: dict[str, Any]) -> ToolResult:
        """Crea un nuovo grafico, lo salva su disco e restituisce il payload per il frontend."""
        cfg = self.ctx.config.chart
        count = await self._store.count()
        if count >= cfg.max_charts:
            return ToolResult(
                success=False,
                content=(
                    f"Limite massimo di grafici raggiunto ({cfg.max_charts}). "
                    "Usa `delete_chart` per eliminare grafici non più necessari."
                ),
            )

        option = args["echarts_option"]
        option_str = json.dumps(option, ensure_ascii=False)
        if len(option_str) > cfg.max_option_chars:
            return ToolResult(
                success=False,
                content=(
                    f"La echarts_option supera il limite di {cfg.max_option_chars} caratteri "
                    f"(attuale: {len(option_str)}). Aggrega o riduci i dati prima di richiamare il tool."
                ),
            )

        chart_id = str(uuid4())
        now = datetime.now(timezone.utc)
        spec = ChartSpec(
            chart_id=chart_id,
            title=args["title"],
            chart_type=args["chart_type"],
            description=args.get("description", ""),
            echarts_option=option,
            created_at=now,
            updated_at=now,
        )
        await self._store.save(spec)
        self.logger.info(f"Grafico '{spec.title}' generato (id={chart_id}, type={spec.chart_type})")

        payload = ChartPayload(
            chart_id=chart_id,
            title=spec.title,
            chart_type=spec.chart_type,
            chart_url=f"/api/charts/{chart_id}",
            created_at=now,
        )
        return ToolResult(
            success=True,
            content=payload.model_dump_json(),
            content_type="application/vnd.omnia.chart+json",
        )

    async def _update_chart(self, args: dict[str, Any]) -> ToolResult:
        """Aggiorna la echarts_option di un grafico esistente."""
        chart_id = args["chart_id"]
        existing = await self._store.load(chart_id)
        if existing is None:
            return ToolResult(success=False, content=f"Grafico non trovato: {chart_id}")

        cfg = self.ctx.config.chart
        option_str = json.dumps(args["echarts_option"], ensure_ascii=False)
        if len(option_str) > cfg.max_option_chars:
            return ToolResult(
                success=False,
                content=f"echarts_option supera il limite di {cfg.max_option_chars} caratteri.",
            )

        existing.echarts_option = args["echarts_option"]
        existing.updated_at = datetime.now(timezone.utc)
        if "title" in args:
            existing.title = args["title"]

        await self._store.update(chart_id, existing)
        self.logger.info(f"Grafico aggiornato: {chart_id}")

        payload = ChartPayload(
            chart_id=chart_id,
            title=existing.title,
            chart_type=existing.chart_type,
            chart_url=f"/api/charts/{chart_id}",
            created_at=existing.created_at,
        )
        return ToolResult(
            success=True,
            content=payload.model_dump_json(),
            content_type="application/vnd.omnia.chart+json",
        )

    async def _get_chart(self, args: dict[str, Any]) -> ToolResult:
        """Recupera metadata e echarts_option di un grafico salvato."""
        chart_id = args["chart_id"]
        spec = await self._store.load(chart_id)
        if spec is None:
            return ToolResult(success=False, content=f"Grafico non trovato: {chart_id}")
        return ToolResult(success=True, content=spec.model_dump_json())

    async def _list_charts(self, args: dict[str, Any]) -> ToolResult:
        """Elenca i grafici salvati con paginazione."""
        limit = min(int(args.get("limit", 20)), 100)
        offset = max(int(args.get("offset", 0)), 0)
        items = await self._store.list(limit=limit, offset=offset)
        total = await self._store.count()
        payload = {
            "charts": [item.model_dump(mode="json") for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
        return ToolResult(
            success=True,
            content=json.dumps(payload, ensure_ascii=False, default=str),
        )

    async def _delete_chart(self, args: dict[str, Any]) -> ToolResult:
        """Elimina un grafico dal disco."""
        chart_id = args["chart_id"]
        deleted = await self._store.delete(chart_id)
        if not deleted:
            return ToolResult(success=False, content=f"Grafico non trovato: {chart_id}")
        return ToolResult(success=True, content=f"Grafico eliminato: {chart_id}")
```

**Registrazione plugin** in `backend/plugins/__init__.py` — aggiungere dopo l'import di `cad_generator`:

```python
from .chart_generator import ChartGeneratorPlugin  # noqa: F401
```

---

### §14.5 — REST API `/api/charts/`

**`backend/api/routes/charts.py`**

Tre endpoint: GET spec singola, GET lista paginata, DELETE.
I tool del plugin gestiscono la logica core — la route è un proxy che serve
i file JSON salvati su disco al `ChartViewer.vue` nel frontend.

```python
"""REST API per il recupero e la gestione dei grafici generati dall'agente."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/charts", tags=["charts"])


def _get_store(request: Request):
    """Recupera il ChartStore dal plugin chart_generator tramite AppContext."""
    ctx = request.app.state.context
    plugin = ctx.plugin_manager.get_plugin("chart_generator")
    if plugin is None or not ctx.config.chart.enabled:
        raise HTTPException(status_code=503, detail="Plugin chart_generator non disponibile.")
    store = plugin._store
    if store is None:
        raise HTTPException(status_code=503, detail="ChartStore non inizializzato.")
    return store


@router.get("/{chart_id}", summary="Recupera la spec completa di un grafico")
async def get_chart(chart_id: str, request: Request) -> JSONResponse:
    """Restituisce il JSON completo della ChartSpec (inclusa echarts_option).

    Chiamato da `ChartViewer.vue` al mount per caricare la configurazione ECharts.
    """
    store = _get_store(request)
    spec = await store.load(chart_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Grafico non trovato: {chart_id}")
    return JSONResponse(content=spec.model_dump(mode="json"))


@router.get("", summary="Lista grafici salvati")
async def list_charts(
    request: Request, limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """Restituisce la lista paginata dei grafici, ordinata dal più recente."""
    store = _get_store(request)
    items = await store.list(limit=min(limit, 100), offset=offset)
    total = await store.count()
    return {
        "charts": [item.model_dump(mode="json") for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/{chart_id}", summary="Elimina un grafico")
async def delete_chart(chart_id: str, request: Request) -> dict[str, str]:
    """Elimina il file JSON del grafico dal disco.

    Nota: per l'eliminazione via LLM usare il tool `delete_chart`,
    che attiva il dialog di conferma utente.
    """
    store = _get_store(request)
    deleted = await store.delete(chart_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Grafico non trovato: {chart_id}")
    return {"status": "deleted", "chart_id": chart_id}
```

**Registrazione router** in `backend/api/routes/__init__.py` — aggiungere dopo il router `cad`:

```python
# Aggiungere alla riga import esistente (o come import separato):
from . import charts

# Nella sezione di registrazione router:
router.include_router(charts.router)
```

---

### §14.6 — Frontend

#### Tipo `ChartPayload` — `frontend/src/renderer/src/types/chat.ts`

Aggiungere l'interfaccia accanto a `CadModelPayload`:

```typescript
/** Payload restituito dai tool `generate_chart` e `update_chart`.
 *  Corrisponde al modello Pydantic `ChartPayload` nel backend.
 *  Non include `echarts_option` — il viewer la carica via `chart_url`.
 */
export interface ChartPayload {
  chart_id: string
  title: string
  chart_type: string
  /** URL relativo: "/api/charts/{chart_id}" */
  chart_url: string
  created_at: string
}
```

#### `ChartViewer.vue` — `frontend/src/renderer/src/components/chat/ChartViewer.vue`

Componente autonomo che monta un'istanza ECharts su un `div` di riferimento.
Pattern identico a `CADViewer.vue`: utilizzo diretto della libreria (no wrapper Vue),
`onMounted`/`onUnmounted` lifecycle, `ResizeObserver` per dimensionamento responsivo.

```vue
<script setup lang="ts">
/**
 * ChartViewer.vue — Visualizza un grafico Apache ECharts nella chat.
 *
 * Carica la ChartSpec completa dall'endpoint REST GET /api/charts/{chart_id},
 * monta un'istanza echarts.init() sul div container e gestisce il resize.
 */
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { resolveBackendUrl } from '../../services/api'
import type { ChartPayload } from '../../types/chat'

const props = defineProps<{ payload: ChartPayload }>()

const containerRef = ref<HTMLDivElement | null>(null)
let instance: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const loading = ref(true)
const error = ref<string | null>(null)

async function loadAndRender(): Promise<void> {
  if (!containerRef.value) return
  try {
    const response = await fetch(resolveBackendUrl(props.payload.chart_url))
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const spec = await response.json()

    instance = echarts.init(containerRef.value, 'dark')
    instance.setOption(spec.echarts_option)
    loading.value = false

    resizeObserver = new ResizeObserver(() => instance?.resize())
    resizeObserver.observe(containerRef.value)
  } catch (err) {
    error.value = `Impossibile caricare il grafico: ${(err as Error).message}`
    loading.value = false
  }
}

onMounted(loadAndRender)

onUnmounted(() => {
  resizeObserver?.disconnect()
  instance?.dispose()
  instance = null
})
</script>

<template>
  <div class="chart-viewer">
    <div class="chart-viewer__header">
      <span class="chart-viewer__title">{{ payload.title }}</span>
      <span class="chart-viewer__type">{{ payload.chart_type }}</span>
    </div>
    <div v-if="loading" class="chart-viewer__loading">Caricamento grafico…</div>
    <div v-if="error" class="chart-viewer__error">{{ error }}</div>
    <div v-show="!loading && !error" ref="containerRef" class="chart-viewer__canvas" />
  </div>
</template>

<style scoped>
.chart-viewer {
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-2);
  margin: 8px 0;
}
.chart-viewer__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-3);
  border-bottom: 1px solid var(--border);
}
.chart-viewer__title {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-primary);
  flex: 1;
}
.chart-viewer__type {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.chart-viewer__canvas {
  width: 100%;
  height: 380px;
}
.chart-viewer__loading,
.chart-viewer__error {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.875rem;
}
.chart-viewer__error {
  color: var(--danger);
}
</style>
```

#### `MessageBubble.vue` — aggiornamento

Aggiungere il supporto per `application/vnd.omnia.chart+json` nei messaggi `role='tool'`
già persistiti nella cronologia della chat. Pattern identico a `cadPayload`:

```typescript
// Aggiungere import accanto a CadModelPayload:
import type { ChartPayload } from '../../types/chat'

const ChartViewer = defineAsyncComponent(
  () => import('./ChartViewer.vue')
)

// Aggiungere computed accanto a cadPayload:
const chartPayload = computed((): ChartPayload | null => {
  if (props.message.role !== 'tool') return null
  try {
    const p = JSON.parse(props.message.content)
    if (
      typeof p.chart_id === 'string' &&
      typeof p.chart_url === 'string' &&
      typeof p.chart_type === 'string'
    ) {
      return p as ChartPayload
    }
  } catch { /* non è JSON chart payload */ }
  return null
})
```

Nel template, aggiungere **dopo** `<CADViewer v-if="cadPayload" …>`:

```vue
<ChartViewer v-if="chartPayload" :payload="chartPayload" />
```

La condizione del contenuto testuale deve diventare:
```vue
<div v-if="!cadPayload && !chartPayload" class="bubble__content" … />
```

#### `ToolExecutionIndicator.vue` — aggiornamento

Aggiungere il case per `application/vnd.omnia.chart+json` accanto al case esistente
per `application/vnd.omnia.cad-model+json` (rendering inline durante lo streaming).
Siccome `ToolExecutionIndicator.vue` itera su `executions: ToolExecution[]` (non espone
`contentType`/`result` come props atomici), si usa una funzione helper per-elemento
anziché un `computed` top-level:

```typescript
import type { ChartPayload } from '../../types/chat'

const ChartViewer = defineAsyncComponent(
  () => import('./ChartViewer.vue')
)

/** Analizza il contenuto di un tool result come ChartPayload. Restituisce null se non è un chart. */
function parseChartPayload(result: string): ChartPayload | null {
  try {
    const p = JSON.parse(result)
    if (typeof p.chart_id === 'string' && typeof p.chart_url === 'string') return p as ChartPayload
    return null
  } catch { return null }
}
```

Nel template (dopo il blocco `cad-model+json` esistente):

```vue
<template v-else-if="exec.contentType === 'application/vnd.omnia.chart+json' && exec.result">
  <ChartViewer
    v-if="parseChartPayload(exec.result)"
    :payload="parseChartPayload(exec.result)!"
  />
</template>
```

---

### §14.7 — System Prompt

**`config/system_prompt.md`** — aggiungere sezione:

```yaml
chart_generator:
  principio: genera e gestisce grafici interattivi Apache ECharts da qualsiasi fonte dati
  workflow:
    - "raccolta dati PRIMA di chiamare generate_chart: note → read_note/search_notes, immagini/CSV → analisi visiva, web → web_search, prompt → dati già disponibili"
    - "costruzione echarts_option: costruisci il JSON ECharts mentalmente prima della tool call. Deve essere un object JSON valido, NON una stringa serializzata"
    - "chiamata generate_chart: passa la spec completa — il grafico è visualizzato nella chat come viewer interattivo"
  tipi_supportati: bar line pie scatter radar heatmap sankey candlestick treemap funnel gauge boxplot parallel themeRiver — e qualsiasi combinazione in series misto
  limiti:
    - "echarts_option serializzata: max 10.000 caratteri. Aggrega o campiona i dati prima di chiamare il tool se il dataset è grande"
    - "max 1.000 grafici nel vault. Usa list_charts / delete_chart per gestirli"
  update: usa update_chart(chart_id, echarts_option) per modificare un grafico esistente. Recupera prima la spec con get_chart(chart_id) per modifiche puntuali
```

---

### §14.8 — Dipendenze

#### Frontend

**`frontend/package.json`** — aggiungere in `dependencies`:

```json
"echarts": "^5.6.0"
```

Installazione: `cd frontend && npm install --save echarts`.

Non è necessario `vue-echarts` — ECharts viene usato con API imperativa
(`echarts.init`, `instance.setOption`), coerente con il pattern Three.js di `CADViewer.vue`.

#### Backend

Nessuna dipendenza Python aggiuntiva. Il plugin usa solo librerie stdlib:
`pathlib`, `json`, `uuid`, `asyncio` — e `pydantic` già in uso nel progetto.

---

### §14.9 — Struttura file

```
backend/
  plugins/
    __init__.py                       # + import ChartGeneratorPlugin
    chart_generator/
      __init__.py                     # Esporta ChartGeneratorPlugin
      plugin.py                       # ChartGeneratorPlugin + PLUGIN_REGISTRY
      chart_store.py                  # ChartStore (JSON file persistence)
      models.py                       # ChartSpec, ChartPayload, ChartListItem
  api/
    routes/
      charts.py                       # GET /{id}, GET /, DELETE /{id}
      __init__.py                     # + charts_router
  core/
    config.py                         # + ChartConfig, OmniaConfig.chart

frontend/
  package.json                        # + echarts ^5.6.0
  src/renderer/src/
    components/chat/
      ChartViewer.vue                 # Viewer ECharts autonomo (nuovo)
      MessageBubble.vue               # + chartPayload computed + <ChartViewer>
      ToolExecutionIndicator.vue      # + parseChartPayload helper + <ChartViewer>
    types/
      chat.ts                         # + ChartPayload interface

config/
  default.yaml                        # + sezione chart:
  system_prompt.md                    # + sezione chart_generator:

data/
  charts/                             # Creata automaticamente da ChartStore
    {uuid}.json                       # Un file JSON per ogni grafico

backend/
  tests/
    test_chart_store.py
    test_chart_generator_plugin.py
    test_charts_route.py
```

---

### §14.10 — Test suite

**`backend/tests/test_chart_store.py`**

```python
"""Test ChartStore — operazioni CRUD su file JSON."""

import pytest
from pathlib import Path
from backend.plugins.chart_generator.chart_store import ChartStore
from backend.plugins.chart_generator.models import ChartSpec


@pytest.fixture
def store(tmp_path: Path) -> ChartStore:
    return ChartStore(chart_output_dir=tmp_path)


@pytest.fixture
def sample_spec() -> ChartSpec:
    return ChartSpec(
        chart_id="test-uuid-001",
        title="Vendite Q1",
        chart_type="bar",
        description="Dati di test",
        echarts_option={
            "xAxis": {"type": "category", "data": ["Gen", "Feb", "Mar"]},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": [150, 230, 180]}],
        },
    )


@pytest.mark.asyncio
async def test_save_and_load(store: ChartStore, sample_spec: ChartSpec) -> None:
    await store.save(sample_spec)
    loaded = await store.load(sample_spec.chart_id)
    assert loaded is not None
    assert loaded.title == "Vendite Q1"
    assert loaded.echarts_option["series"][0]["type"] == "bar"


@pytest.mark.asyncio
async def test_load_nonexistent_returns_none(store: ChartStore) -> None:
    assert await store.load("nonexistent-id") is None


@pytest.mark.asyncio
async def test_delete_existing(store: ChartStore, sample_spec: ChartSpec) -> None:
    await store.save(sample_spec)
    assert await store.delete(sample_spec.chart_id) is True
    assert await store.load(sample_spec.chart_id) is None


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(store: ChartStore) -> None:
    assert await store.delete("ghost-id") is False


@pytest.mark.asyncio
async def test_list_and_count(store: ChartStore, sample_spec: ChartSpec) -> None:
    for i in range(3):
        spec = sample_spec.model_copy(update={"chart_id": f"id-{i}", "title": f"Chart {i}"})
        await store.save(spec)
    assert await store.count() == 3
    items = await store.list(limit=2, offset=0)
    assert len(items) == 2


@pytest.mark.asyncio
async def test_path_sanitization(store: ChartStore, sample_spec: ChartSpec) -> None:
    """Path traversal non possibile — i caratteri non-UUID vengono rimossi dal filename."""
    spec = sample_spec.model_copy(update={"chart_id": "../../../etc/passwd"})
    await store.save(spec)
    # _path() deve restituire un percorso DENTRO store._dir, non fuori
    sanitized_path = store._path("../../../etc/passwd")
    assert sanitized_path.parent == store._dir, (
        "Il path sanitizzato deve rimanere dentro la directory del store"
    )
    assert sanitized_path.exists(), "Il file sanitizzato deve esistere nella directory del store"
```

**`backend/tests/test_chart_generator_plugin.py`**

```python
"""Test ChartGeneratorPlugin — esecuzione tool LLM."""

import pytest
from unittest.mock import MagicMock
from backend.plugins.chart_generator.plugin import ChartGeneratorPlugin

VALID_OPTION = {"series": [{"type": "bar", "data": [1, 2, 3]}]}


@pytest.fixture
def mock_ctx(tmp_path):
    ctx = MagicMock()
    ctx.config.chart.enabled = True
    ctx.config.chart.max_option_chars = 10_000
    ctx.config.chart.max_charts = 1_000
    ctx.config.chart.chart_output_dir = str(tmp_path)
    return ctx


@pytest.fixture
async def plugin(mock_ctx):
    p = ChartGeneratorPlugin(mock_ctx)
    await p.initialize(mock_ctx)
    return p


@pytest.mark.asyncio
async def test_generate_chart_success(plugin) -> None:
    result = await plugin.execute_tool("generate_chart", {
        "title": "Test Chart",
        "chart_type": "bar",
        "echarts_option": VALID_OPTION,
    }, context=None)
    assert result.success is True
    assert result.content_type == "application/vnd.omnia.chart+json"
    import json
    payload = json.loads(result.content)
    assert "chart_id" in payload
    assert payload["chart_url"].startswith("/api/charts/")


@pytest.mark.asyncio
async def test_generate_chart_option_too_large(plugin) -> None:
    plugin.ctx.config.chart.max_option_chars = 10
    result = await plugin.execute_tool("generate_chart", {
        "title": "Big",
        "chart_type": "line",
        "echarts_option": {"data": list(range(10_000))},
    }, context=None)
    assert result.success is False
    assert "limite" in result.content.lower()


@pytest.mark.asyncio
async def test_list_charts_empty(plugin) -> None:
    result = await plugin.execute_tool("list_charts", {}, context=None)
    assert result.success is True
    import json
    data = json.loads(result.content)
    assert data["charts"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_chart_not_found(plugin) -> None:
    result = await plugin.execute_tool("get_chart", {"chart_id": "nonexistent"}, context=None)
    assert result.success is False


@pytest.mark.asyncio
async def test_delete_chart_success(plugin) -> None:
    gen = await plugin.execute_tool("generate_chart", {
        "title": "Da eliminare",
        "chart_type": "bar",
        "echarts_option": VALID_OPTION,
    }, context=None)
    assert gen.success is True
    import json
    chart_id = json.loads(gen.content)["chart_id"]

    result = await plugin.execute_tool("delete_chart", {"chart_id": chart_id}, context=None)
    assert result.success is True

    get = await plugin.execute_tool("get_chart", {"chart_id": chart_id}, context=None)
    assert get.success is False


@pytest.mark.asyncio
async def test_delete_chart_not_found(plugin) -> None:
    result = await plugin.execute_tool("delete_chart", {"chart_id": "nonexistent"}, context=None)
    assert result.success is False


@pytest.mark.asyncio
async def test_update_chart_success(plugin) -> None:
    gen = await plugin.execute_tool("generate_chart", {
        "title": "Originale",
        "chart_type": "bar",
        "echarts_option": VALID_OPTION,
    }, context=None)
    import json
    chart_id = json.loads(gen.content)["chart_id"]

    new_option = {"series": [{"type": "line", "data": [10, 20, 30]}]}
    result = await plugin.execute_tool("update_chart", {
        "chart_id": chart_id,
        "echarts_option": new_option,
    }, context=None)
    assert result.success is True


@pytest.mark.asyncio
async def test_plugin_disabled_returns_no_tools(mock_ctx) -> None:
    mock_ctx.config.chart.enabled = False
    p = ChartGeneratorPlugin(mock_ctx)
    await p.initialize(mock_ctx)
    assert p.get_tools() == []
```

**`backend/tests/test_charts_route.py`**

```python
"""Test REST route /api/charts/."""

import pytest


@pytest.mark.asyncio
async def test_get_chart_not_found(client) -> None:
    response = await client.get("/api/charts/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_charts_empty(client) -> None:
    response = await client.get("/api/charts")
    assert response.status_code == 200
    data = response.json()
    assert "charts" in data
    assert "total" in data
    assert data["charts"] == []
    assert data["total"] == 0
```

---

### §14.11 — Ordine di implementazione

1. `backend/plugins/chart_generator/models.py` — modelli Pydantic
2. `backend/plugins/chart_generator/chart_store.py` — ChartStore
3. `backend/core/config.py` — `ChartConfig` + campo `chart` in `OmniaConfig`
4. `config/default.yaml` — sezione `chart:`
5. `backend/plugins/chart_generator/plugin.py` — ChartGeneratorPlugin completo
6. `backend/plugins/chart_generator/__init__.py` — export
7. `backend/plugins/__init__.py` — import per trigger PLUGIN_REGISTRY
8. `backend/api/routes/charts.py` — 3 endpoint REST
9. `backend/api/routes/__init__.py` — registrazione `charts_router`
10. `frontend/package.json` → `npm install echarts`
11. `frontend/src/renderer/src/types/chat.ts` — `ChartPayload` interface
12. `frontend/src/renderer/src/components/chat/ChartViewer.vue` — nuovo componente
13. `frontend/src/renderer/src/components/chat/MessageBubble.vue` — `chartPayload` + `<ChartViewer>`
14. `frontend/src/renderer/src/components/chat/ToolExecutionIndicator.vue` — case chart
15. `config/system_prompt.md` — sezione `chart_generator`
16. Test `test_chart_store.py`, `test_chart_generator_plugin.py` e `test_charts_route.py`

---

### §14.12 — Verifiche

| Scenario | Risultato atteso |
|---|---|
| "Fai un grafico a barre: Gen=150, Feb=230, Mar=180" | LLM costruisce echarts_option → `generate_chart(...)` → ToolResult `application/vnd.omnia.chart+json` → `ChartViewer` in chat |
| "Fai un grafico dalla nota 'statistiche vendite'" | LLM chiama `read_note` → estrae dati → `generate_chart(...)` → viewer in chat |
| Upload immagine con tabella + "Grafico da questa tabella" | LLM legge immagine via vision → estrae valori → `generate_chart(...)` → viewer |
| `list_charts(limit=5)` | Lista con titolo, tipo, date; paginazione `offset` funzionante |
| `get_chart(chart_id)` | Metadati + `echarts_option` del grafico restituiti correttamente; chart inesistente → errore descrittivo |
| `update_chart(chart_id, echarts_option)` | Spec aggiornata su disco; `ChartViewer` ricarica e mostra grafico aggiornato |
| `delete_chart(chart_id)` | Dialog di conferma → approvazione → file eliminato; `GET /api/charts/{id}` → 404 |
| Ricaricamento conversazione con grafico precedente dal DB | `MessageBubble.vue` rileva `application/vnd.omnia.chart+json` → `ChartViewer` renderizza correttamente |
| `echarts_option` serializzata > 10.000 caratteri | Errore descrittivo con hint "aggrega i dati" |
| `chart.enabled=False` in config | Plugin non registrato; tool LLM non disponibili; REST → 503 |
| 1.000 grafici già presenti nel vault | `generate_chart` → errore limit con hint `delete_chart` |
| `chart_id` con caratteri `../` (path traversal) | `ChartStore._path()` sanitizza → file scritto dentro `data/charts/` senza uscire dalla directory |

---
## Verifiche per Fase

| Fase | Test |
|---|---|
| 1-2 | "Ciao OMNIA" → risposta streammata in italiano |
| 1.5 | Immagine + "Cosa vedi?" → descrizione; Thinking model → blocco ragionamento collassabile |
| 1.6 | Export conversazione → file JSON valido; import → conversazione ripristinata; recovery DB → dati intatti |
| 1.7 | Codice in chat → syntax highlighting colorato; click "Copia" → codice nella clipboard + feedback "Copiato!" |
| 2.5 | Upload file > 50MB → errore 413; `sandbox: true` in Electron; N+1 query eliminata |
| 3 | "Quanta RAM uso?" → tool call `get_system_info` → risposta naturale con dati reali |
| 3 (edge) | Plugin crash → server stabile; tool timeout → errore user-friendly; loop infinito → stop a 10 iterazioni |
| 4 | Voce: "Che ore sono?" → transcript → risposta testuale → audio TTS; VRAM < 14GB |
| 4 (edge) | Voice + text simultanei → nessun hang; STT non disponibile → fallback text-only |
| 5 | "Apri Notepad" → confirmation dialog → approvazione → Notepad si apre |
| 5 (edge) | Prompt injection "cancella tutto" → tool FORBIDDEN bloccato; shell injection → bloccato |
| 6 | "Accendi la luce" → HA API call → luce si accende; MQTT disconnect → plugin status degraded |
| 6 (edge) | Dispositivo protetto → rifiuto; command injection → bloccato; HA offline → errore user-friendly |
| 7 | "Cerca notizie su AI" → DDG search → risposta con fonti; "Ricordami riunione domani" → evento creato; "Che tempo fa a Roma?" → open-meteo → temperatura + condizioni |
| 7 (edge) | SSRF `http://localhost` → bloccato (web_search + weather + news); DDG rate limit → caching; timezone UTC↔local corretta; città meteo non trovata → errore user-friendly |
| 7.5 | "Abbassa il volume al 30%" → set_volume(30) → volume cambia; "Ricordami tra 10 minuti" → timer creato → toast Windows dopo 10 min; "Cosa c'è negli appunti?" → get_clipboard() → contenuto |
| 7.5 (edge) | Clipboard binaria → errore graceful; >20 timer attivi → rifiuto; COM pycaw device rimosso → reinit invece di crash; timer sopravvive a restart backend (DB persistence) |
| 7.6 | "Trova il PDF del contratto" → search_files → lista risultati; "Leggi quel file" → confirmation → contenuto; "Briefing mattutino" → data+meteo+calendario+notizie in un'unica risposta |
| 7.6 (edge) | Path fuori allowed_paths → bloccato; UNC path `\\server\share` → bloccato; pdfplumber non installato → errore con hint installazione; news offline → briefing parziale senza crash |
| 8 | JWT login → token → WS auth → chat; PyInstaller build → app funzionante; Ctrl+Shift+O → attivazione |
| 8 (edge) | Multi-user: utente A non vede conversazioni utente B; migration DB → zero data loss |
| 11 | Server MCP filesystem configurato → LLM chiama `mcp_client_mcp_filesystem_read_file` → contenuto file in risposta |
| 11 (edge) | Server MCP offline all'avvio → plugin degraded, chat funzionante; server non configurato → zero impatto |
| 12 | "Crea un vaso decorativo Art Nouveau" → `cad_generate(description="...")` → VRAM swap (LLM unload → TRELLIS genera GLB → LLM reload) → ToolResult con `content_type=cad-model+json` → CADViewer Three.js GLTFLoader nel frontend; ebook-mcp configurato → LLM legge docs PDF |
| 12 (edge) | TRELLIS microservizio non avviato → errore descrittivo con istruzioni; CUDA OOM → errore + LLM comunque ricaricato; `auto_vram_swap: false` su GPU ≥ 24GB → coesistenza senza swap; `model_name="../../../etc"` → sanitizzato; GLB > 100MB → ValueError; conversazione ricaricata da DB → viewer non compare (noto v1) |
| 13 | "Crea una nota sulla carbonara" → `create_note(title=..., content=..., folder_path="cucina")` → nota salvata in notes.db → conferma all'utente; "Trova note su Python" → `search_notes("Python")` → FTS5 + semantic → lista titoli; UI NoteEditor autosave dopo 800ms |
| 13 (edge) | `notes.enabled=False` → service non avviato, tool restituiscono errore graceful, REST 503, zero impatto test esistenti; `embedding_enabled=False` → solo FTS5, nessun sqlite-vec caricato; LM Studio offline → nota creata senza embedding, search solo keyword; `delete_note` → `requires_confirmation=True` → dialog conferma |
| 14 | "Fai un grafico a barre: Gen=150, Feb=230, Mar=180" → LLM costruisce echarts_option → `generate_chart(...)` → ToolResult `application/vnd.omnia.chart+json` → `ChartViewer.vue` ECharts renderizzato in chat; `get_chart` → metadati+option corretti; `list_charts` → lista paginata; `update_chart` → grafico aggiornato; ricaricamento conversazione da DB → viewer ripristinato |
| 14 (edge) | `chart.enabled=False` → tool LLM non disponibili, REST 503; `echarts_option` > 10.000 char → errore descrittivo con hint; 1.000 grafici presenti → errore limit con hint `delete_chart`; `delete_chart` → dialog conferma prima di eliminare; `chart_id` con `../` → sanitizzato, file scritto dentro `data/charts/` |
