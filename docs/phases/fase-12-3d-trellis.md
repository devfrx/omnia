### Fase 12 — Generazione 3D Neurale (TRELLIS) + Documentazione MCP

> **Obiettivo**: permettere a OMNIA di generare modelli 3D da linguaggio naturale
> tramite [TRELLIS-for-windows](https://github.com/sdbds/TRELLIS-for-windows)
> (Microsoft TRELLIS, rete neurale image-to-3D) come microservizio separato,
> visualizzare i modelli interattivamente con Three.js (GLTFLoader), e fornire
> all'LLM accesso alla documentazione tecnica (PDF/EPUB) tramite
> [ebook-mcp](https://github.com/onebirdrocks/ebook-mcp).
>
> **Cambio di paradigma** rispetto all'approccio build123d precedentemente tentato:
> l'LLM NON genera più codice CAD (fase fallita perché il modello linguistico non
> riesce a produrre geometrie spazialmente corrette). Ora l'LLM descrive l'oggetto
> in linguaggio naturale → TRELLIS genera direttamente la mesh 3D come file `.glb`
> con texture. La qualità dipende dalla rete neurale addestrata, non dalla capacità
> dell'LLM di scrivere codice build123d.
>
> Fase 12 = **due feature distinte**, architetture complementari, zero overlap:
> 1. **Documentazione** — puro config: `ebook-mcp` registrato come server MCP nel plugin
>    `mcp_client` esistente (Fase 11). Zero codice.
> 2. **Generazione 3D** — TRELLIS microservizio (Python 3.10-3.12 separato) + plugin
>    `cad_generator` (HTTP client) + route proxy `/api/cad/` + viewer Three.js (GLTFLoader).

- [x] 12.1 — Documentazione MCP (`ebook-mcp`) — config-only
- [x] 12.2 — `TrellisServiceConfig` in `config.py` + `default.yaml`
- [x] 12.3 — TRELLIS Microservizio (`trellis_server/`)
- [x] 12.4 — `TrellisClient` (`backend/plugins/cad_generator/client.py`)
- [x] 12.5 — Orchestrazione VRAM (unload/reload LLM automatico)
- [x] 12.6 — `CadGeneratorPlugin` (1 tool primario: `cad_generate`)
- [x] 12.7 — REST proxy `backend/api/routes/cad.py` (`/api/cad/`)
- [x] 12.8 — Frontend: `CADViewer.vue` (Three.js + GLTFLoader)
- [x] 12.9 — Frontend: estensione `ToolExecutionIndicator.vue` + `types/chat.ts`
- [x] 12.10 — System prompt update (`config/system_prompt.md`)
- [x] 12.11 — Test suite (3+ file, 25+ test case)

---

#### 12.0 — Analisi Vincoli e Scelte Architetturali

**Perché TRELLIS neurale e non build123d code generation:**

L'approccio precedente (build123d code generation via Docker cad-agent) è stato implementato
e revertato perché l'LLM non riesce a generare codice build123d spazialmente corretto:
maniglie fuori posizione, intersezioni casuali di poligoni, geometrie impossibili. Il
problema è intrinseco — i language model non hanno comprensione spaziale 3D sufficientemente
precisa per scrivere codice CAD parametrico corretto al primo tentativo.

TRELLIS (Microsoft Research, MIT license) è una rete neurale image-to-3D che genera
mesh 3D direttamente da un'immagine di input. L'LLM descrive l'oggetto → (opzionalmente)
un modello T2I genera un'immagine di riferimento → TRELLIS produce un file GLB con
texture. La qualità dipende dalla rete neurale pre-addestrata (1.2B parametri), non dalla
capacità dell'LLM di scrivere codice procedurale.

**Perché TRELLIS-for-windows (fork sdbds) e non TRELLIS upstream:**

TRELLIS upstream (Microsoft) è solo Linux. Il fork
[sdbds/TRELLIS-for-windows](https://github.com/sdbds/TRELLIS-for-windows) è un port
Windows completo con installer PowerShell, gestione dipendenze via `uv`, supporto CUDA
12.4, e wheel precompilate per le dipendenze problematiche (flash-attn, kaolin, etc.).
Requisiti: Python 3.10-3.12, CUDA 12.4+, VS Studio 2022 C++ build tools.

**Perché un microservizio separato e non integrato nel backend OMNIA:**

| Vincolo | Motivo |
|---|---|
| **Python 3.14 vs 3.10-3.12** | OMNIA usa Python 3.14; TRELLIS richiede 3.10-3.12 (dipendenze: flash-attn, kaolin, spconv non compilano su 3.14). Impossibile coesistere nello stesso venv. |
| **Dipendenze pesanti** | TRELLIS porta ~8GB di dipendenze (PyTorch, kaolin, flash-attn, xformers, spconv, etc.). Mescolarle nel venv OMNIA creerebbe conflitti e fragilità. |
| **Isolamento fault** | Se TRELLIS crasha (OOM, CUDA error), il backend OMNIA resta stabile. Il microservizio può essere riavviato indipendentemente. |
| **VRAM esclusiva** | TRELLIS-image-large ha bisogno di ≥16GB VRAM esclusivi; TRELLIS-text-large ~10-12GB. LLM ha bisogno di ~10GB. Non possono coesistere. Il microservizio si avvia on-demand e rilascia VRAM quando finisce. |

Il microservizio TRELLIS è un processo Python 3.10-3.12 separato con un proprio venv, che
espone una mini API HTTP (FastAPI, porta 8090). Il plugin OMNIA `cad_generator` lo chiama
via `httpx` — identico al pattern cad-agent Docker della spec precedente, ma senza Docker.

**Perché VRAM swap (unload LLM → TRELLIS → reload LLM):**

Con 16GB VRAM totali (RTX 5080), LLM (~10GB) + TRELLIS-image-large (~15GB) non possono coesistere.
Il flusso è:

```
1. Utente: "Crea un modello 3D di un vaso decorativo"
2. LLM genera risposta + tool_call cad_generate(description="...")
3. === TOOL EXECUTION WINDOW (LLM è idle, aspetta risultato) ===
4.   a) Plugin chiama LM Studio POST /api/v1/models/unload → LLM scaricato, ~10GB VRAM liberi
5.   b) Plugin chiama TRELLIS microservice /generate → TRELLIS carica modello, genera GLB
6.   c) TRELLIS rilascia VRAM (processo rimane in standby o si chiude)
7.   d) Plugin chiama LM Studio POST /api/v1/models/load → LLM ricaricato
8. === FINE TOOL EXECUTION ===
9. LLM riceve ToolResult con URL al .glb → completa la risposta all'utente
```

Questo è possibile perché nel tool loop (`_tool_loop.py`), tra il momento in cui l'LLM
emette la `tool_call` (step 2) e riceve il `ToolResult` (step 9), l'LLM è completamente
idle — non ha bisogno della VRAM. La finestra è naturale e non richiede hack.

LM Studio espone sia `POST /api/v1/models/unload` (per `instance_id`) sia
`POST /api/v1/models/load` — confermato dall'esplorazione del servizio `lmstudio_service.py`
che già wrappa queste API.

**Perché GLB e non STL:**

TRELLIS genera nativamente mesh in formato GLB (glTF Binary) con texture UV-mapped.
Three.js supporta `GLTFLoader` come loader principale (più performante di STLLoader,
supporta materiali PBR, animazioni, compressione Draco). GLB è lo standard de facto per
3D sul web.

**Flusso opzionale T2I per qualità migliore:**

Il README di TRELLIS raccomanda: "It is always recommended to do text to 3D generation
by first generating images using text-to-image models and then using TRELLIS-image models
for 3D generation." Il flusso a due step (text → immagine → 3D) produce risultati più
dettagliati e creativi. Per v1, il T2I è opzionale: se configurato, il plugin lo usa;
altrimenti passa il testo direttamente a TRELLIS-text (qualità inferiore ma funzionante).

**Nessuna modifica a layer esistenti (solo aggiunte pure):**

| Layer | Modificato | Motivo |
|---|---|---|
| `_tool_loop.py` | NO | `content_type` già propagato a WS per tutti i tool result |
| `chat.py` | NO | nessuna dispatch speciale necessaria |
| `plugin_models.py` | NO | `ToolResult.content_type` già esiste |
| `protocols.py` | NO | nessun nuovo protocol necessario (LMStudioManagerProtocol già esiste) |
| `context.py` | NO | plug-in gestito da `PluginManager` come tutti gli altri |
| `app.py` | NO | plugin registrato nel `PLUGIN_REGISTRY` statico |
| `plugin_manager.py` | NO | nessuna modifica |
| `lmstudio_service.py` | NO | API unload/load già esposte |
| `vram_monitor.py` | NO | il plugin gestisce il budget VRAM autonomamente |

---

#### 12.1 — Documentazione MCP (`ebook-mcp`) — Config-Only

`ebook-mcp` (onebirdrocks/ebook-mcp, Apache 2.0, installabile via `uvx`) è un server MCP
stdio che legge PDF e EPUB e ne espone il contenuto come tool. Aggiungere un'entry a
`config/default.yaml` nella sezione `mcp.servers` (introdotta in Fase 11) è l'unica
azione necessaria.

**Tool esposti all'LLM una volta configurato:**

| Tool MCP | Nome visibile all'LLM (via ToolRegistry) |
|---|---|
| `get_all_epub_files` | `mcp_client_mcp_3d_docs_get_all_epub_files` |
| `get_metadata` | `mcp_client_mcp_3d_docs_get_metadata` |
| `get_toc` | `mcp_client_mcp_3d_docs_get_toc` |
| `get_chapter_markdown` | `mcp_client_mcp_3d_docs_get_chapter_markdown` |
| `get_all_pdf_files` | `mcp_client_mcp_3d_docs_get_all_pdf_files` |
| `get_pdf_metadata` | `mcp_client_mcp_3d_docs_get_pdf_metadata` |
| `get_pdf_toc` | `mcp_client_mcp_3d_docs_get_pdf_toc` |
| `get_pdf_page_text` | `mcp_client_mcp_3d_docs_get_pdf_page_text` |
| `get_pdf_page_markdown` | `mcp_client_mcp_3d_docs_get_pdf_page_markdown` |
| `get_pdf_chapter_content` | `mcp_client_mcp_3d_docs_get_pdf_chapter_content` |

**Aggiunta a `config/default.yaml`** (nella sezione `mcp.servers` esistente):

```yaml
mcp:
  servers:
    # ... server esistenti ...
    #
    # - name: 3d_docs
    #   transport: stdio
    #   # Installa ebook-mcp con: uvx ebook-mcp
    #   # Posiziona i PDF/EPUB di documentazione 3D nella cartella models/docs/
    #   command: ["uvx", "ebook-mcp", "--folder", "C:/Users/zagor/Desktop/omnia/models/docs"]
    #   enabled: true
    #   # Usa `get_toc` su ogni documento prima di leggere capitoli specifici
```

**Configurazione utente** (passo manuale one-shot):

```powershell
# 1. Installa ebook-mcp (verifica che uvx/uv sia disponibile — già usato dal progetto)
uvx ebook-mcp --version  # verifica funzionamento

# 2. Crea la cartella documenti e posiziona i PDF/EPUB
New-Item -ItemType Directory -Path "C:\Users\zagor\Desktop\omnia\models\docs" -Force
# Copiare qui: documentazione 3D, manuali tecnici, ecc.

# 3. Decommentare la voce nel default.yaml e aggiornare il path
# 4. Aggiungere "mcp_client" a plugins.enabled se non già presente
```

**Dipendenze:** `ebook-mcp` richiede `uvx` (già disponibile) — zero nuove dipendenze nel
`pyproject.toml` di OMNIA. L'installazione avviene nell'ambiente isolato di `uvx`.

---

#### 12.2 — TrellisServiceConfig (`backend/core/config.py`)

Nuova classe aggiunta in `config.py`, dopo `McpConfig`:

```python
class TrellisServiceConfig(BaseSettings):
    """TRELLIS 3D generation microservice configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_TRELLIS__")

    enabled: bool = False
    """Abilita il plugin cad_generator. Richiede il microservizio TRELLIS installato."""

    service_url: str = "http://localhost:8090"
    """URL base del microservizio TRELLIS (processo Python 3.10-3.12 separato)."""

    request_timeout_s: int = 120
    """Timeout per la generazione 3D (può richiedere 30-90s a seconda della complessità)."""

    max_model_size_mb: int = 100
    """Dimensione massima accettata per i file GLB generati."""

    model_output_dir: str = "data/3d_models"
    """Directory locale dove salvare i file GLB generati (relativa a PROJECT_ROOT)."""

    auto_vram_swap: bool = True
    """Se True, scarica automaticamente l'LLM da VRAM prima della generazione 3D
    e lo ricarica dopo. Necessario su GPU con < 20GB VRAM."""

    trellis_model: str = "TRELLIS-image-large"
    """Modello TRELLIS da caricare nel microservizio. Opzioni:
    - TRELLIS-image-large (1.2B) — image-to-3D, qualità migliore, raccomandato;
    - TRELLIS-text-xlarge (2.0B) — text-to-3D, massima qualità, richiede > 16GB VRAM;
    - TRELLIS-text-large (1.1B) — text-to-3D, buona qualità, ~12GB VRAM;
    - TRELLIS-text-base (342M) — text-to-3D, veloce, ~8GB VRAM.
    Nota: tutti i VAE sono inclusi nel repo TRELLIS-image-large su HuggingFace."""

    use_t2i: bool = False
    """Se True, usa un modello text-to-image intermedio per generare l'immagine di
    riferimento prima di passarla a TRELLIS. Migliora creatività e dettaglio.
    Richiede un modello T2I configurato nel microservizio TRELLIS."""

    seed: int = -1
    """Seed per la generazione. -1 = random. Impostare un valore fisso per riproducibilità."""
```

Aggiunta a `OmniaConfig` (dopo `mcp`):

```python
trellis: TrellisServiceConfig = Field(default_factory=TrellisServiceConfig)
```

Aggiunta a `config/default.yaml` (in fondo, dopo la sezione `mcp:`):

```yaml
# ──────────────────────────────────────────────────
# Fase 12 — Generazione 3D Neurale (TRELLIS)
# ──────────────────────────────────────────────────
trellis:
  enabled: false
  # Installare TRELLIS-for-windows prima di abilitare:
  #   0. [Admin PS] Set-ExecutionPolicy Unrestricted
  #   1. git clone --recurse-submodules https://github.com/sdbds/TRELLIS-for-windows.git trellis_server
  #   2. cd trellis_server && .\1、install-uv-qinglong.ps1
  #   3. Avviare con: .venv\Scripts\python.exe server.py --port 8090
  service_url: "http://localhost:8090"
  request_timeout_s: 120
  max_model_size_mb: 100
  model_output_dir: "data/3d_models"
  auto_vram_swap: true
  trellis_model: "TRELLIS-image-large"
  # Modelli disponibili (da HuggingFace JeffreyXiang/):
  # - TRELLIS-image-large (1.2B) — image-to-3D, qualità migliore (raccomandato con T2I)
  # - TRELLIS-text-large (1.1B) — text-to-3D, buona qualità, ~10-12GB VRAM
  # - TRELLIS-text-base (342M) — text-to-3D, veloce, ~8GB VRAM
  # NOTA: su sistemi con 16GB VRAM e STT caricato, preferire TRELLIS-text-large
  use_t2i: false
  seed: -1

# In plugins.enabled, aggiungere (commentato per default-off):
#   - cad_generator  # abilitare con trellis.enabled: true
```

**SSRF protection**: `service_url` deve essere un URL locale. La validazione è enforced in
`TrellisClient.__init__()` tramite `validate_url_ssrf()` di `http_security.py` —
identica al pattern adottato da `WeatherPlugin`, `NewsPlugin` e `WebSearchPlugin`.

---

#### 12.3 — TRELLIS Microservizio (`trellis_server/`)

**Ruolo**: processo Python 3.10-3.12 separato che wrappa TRELLIS-for-windows ed espone una
mini API HTTP per la generazione 3D. Completamente isolato dal backend OMNIA.

**Directory structure**:

```
trellis_server/                          ← root del microservizio (gitignored, clonato da fork)
├── 1、install-uv-qinglong.ps1           ← ★ installer PowerShell dal fork (--recurse-submodules)
├── 2、run_gui.ps1                       ← launcher Gradio demo opzionale
├── server.py                            ← ★ Mini FastAPI server (scritto da noi, ~150 righe)
├── .venv/                               ← venv Python 3.11/3.12 isolato (creato dall'installer)
└── ... (file TRELLIS-for-windows)       ← repo clonata con submoduli
```

**`trellis_server/server.py`** — Mini FastAPI server (~100 righe):

```python
"""TRELLIS microservice — minimal FastAPI wrapper for 3D generation.

Runs as a separate Python 3.10-3.12 process, isolated from the OMNIA backend.
Exposes /generate, /unload, /health, and /models/{name} on port 8090.

Usage:
    cd trellis_server
    .venv/Scripts/python.exe server.py [--model TRELLIS-image-large] [--port 8090]

Model selection:
    TRELLIS-image-large  (1.2B) — image-to-3D, best quality, recommended
    TRELLIS-text-large   (1.1B) — text-to-3D, lower quality, no image required
    TRELLIS-text-base    (342M) — text-to-3D, fastest, 16GB VRAM constraint
"""
from __future__ import annotations

import argparse
import gc
import io
import os
import re
import tempfile
import time
import uuid
from pathlib import Path

# Must be set before importing any trellis module — disables auto-benchmarking
# so the first run doesn't spend 30-60s selecting optimal CUDA kernels.
os.environ.setdefault("SPCONV_ALGO", "native")

import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

app = FastAPI(title="TRELLIS Microservice", version="1.0.0")

# Set by __main__ — determines which pipeline class to load.
_pipeline = None
_model_name: str = "TRELLIS-image-large"
_output_dir: Path = Path(tempfile.gettempdir()) / "trellis_output"


def _is_image_model() -> bool:
    """Return True for TRELLIS-image-* models, False for TRELLIS-text-*."""
    return "image" in _model_name.lower()


def _load_pipeline():
    """Lazy-load the correct TRELLIS pipeline on first request.

    TRELLIS-image-* uses TrellisImageTo3DPipeline (image input required).
    TRELLIS-text-*  uses TrellisTextTo3DPipeline (text prompt input).
    Both pipelines export identical outputs dict: gaussian / mesh / radiance_field.
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if _is_image_model():
        from trellis.pipelines import TrellisImageTo3DPipeline
        _pipeline = TrellisImageTo3DPipeline.from_pretrained(_model_name)
    else:
        from trellis.pipelines import TrellisTextTo3DPipeline
        _pipeline = TrellisTextTo3DPipeline.from_pretrained(_model_name)
    _pipeline.cuda()
    return _pipeline


def _unload_pipeline():
    """Release TRELLIS model from VRAM."""
    global _pipeline
    if _pipeline is not None:
        _pipeline.to("cpu")
        del _pipeline
        _pipeline = None
        gc.collect()
        torch.cuda.empty_cache()


@app.get("/health")
async def health():
    """Health check. Returns GPU availability and VRAM status."""
    gpu_available = torch.cuda.is_available()
    vram_free = 0
    if gpu_available:
        vram_free = torch.cuda.mem_get_info()[0] // (1024 * 1024)
    return {
        "status": "ok",
        "gpu_available": gpu_available,
        "vram_free_mb": vram_free,
        "model_loaded": _pipeline is not None,
        "model_name": _model_name,
    }


@app.post("/generate")
async def generate(
    image: UploadFile = File(None),
    prompt: str = Form(""),
    seed: int = Form(-1),
    output_name: str = Form(""),
):
    """Generate a 3D GLB model from an image or text prompt.

    Routes to TrellisImageTo3DPipeline or TrellisTextTo3DPipeline based on
    the loaded model. Image-to-3D produces significantly better results —
    always prefer TRELLIS-image-large with a T2I-generated image when possible.

    Raises:
        HTTPException 400: If image-model loaded but no image provided.
        HTTPException 500: On TRELLIS generation or export failure.
    """
    from trellis.utils import postprocessing_utils

    if not image and not prompt:
        raise HTTPException(400, "Provide either 'image' or 'prompt'.")
    if _is_image_model() and not image:
        raise HTTPException(
            400,
            f"Model '{_model_name}' requires an image input. "
            "Either provide an image or switch to a TRELLIS-text-* model.",
        )

    pipeline = _load_pipeline()
    actual_seed = seed if seed >= 0 else int(time.time()) % (2**32)
    name = output_name or f"model_{uuid.uuid4().hex[:8]}"
    _output_dir.mkdir(parents=True, exist_ok=True)
    out_path = _output_dir / f"{name}.glb"

    try:
        if image:
            # Image-to-3D: RGBA input recommended per TRELLIS docs
            img_bytes = await image.read()
            pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            outputs = pipeline.run(pil_image, seed=actual_seed)
        else:
            # Text-to-3D: requires TRELLIS-text-* model (set via --model flag)
            outputs = pipeline.run(prompt, seed=actual_seed)

        # Fuse Gaussian + Mesh into a single textured GLB.
        # simplify=0.95 reduces triangle count while preserving shape.
        # texture_size=1024 gives good quality without excessive file size.
        glb = postprocessing_utils.to_glb(
            outputs["gaussian"][0],
            outputs["mesh"][0],
            simplify=0.95,
            texture_size=1024,
        )
        glb.export(str(out_path))

    except Exception as exc:
        raise HTTPException(500, f"Generation failed: {exc}")

    return JSONResponse({
        "model_name": name,
        "file_path": str(out_path),
        "format": "glb",
        "size_bytes": out_path.stat().st_size,
    })


@app.post("/unload")
async def unload():
    """Unload the TRELLIS model from VRAM to free memory for the LLM."""
    _unload_pipeline()
    return {"status": "unloaded"}


@app.get("/models/{model_name}")
async def get_model(model_name: str):
    """Download a previously generated GLB file by name."""
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", model_name):
        raise HTTPException(400, "Invalid model name.")
    path = _output_dir / f"{model_name}.glb"
    if not path.exists():
        raise HTTPException(404, f"Model '{model_name}' not found.")
    return FileResponse(path, media_type="model/gltf-binary", filename=f"{model_name}.glb")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TRELLIS 3D generation microservice")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument(
        "--model", type=str, default="TRELLIS-image-large",
        help=(
            "TRELLIS model name or local HuggingFace cache path. "
            "TRELLIS-image-large (1.2B, image-to-3D, recommended), "
            "TRELLIS-text-large (1.1B, text-to-3D), "
            "TRELLIS-text-base (342M, text-to-3D, lower VRAM)."
        ),
    )
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    _model_name = args.model
    if args.output_dir:
        _output_dir = Path(args.output_dir)

    uvicorn.run(app, host="127.0.0.1", port=args.port)
```

**Installazione TRELLIS-for-windows** (passo manuale one-shot):

```powershell
# 0. [UNA VOLTA, come Amministratore] Abilita execution policy per script non firmati.
#    Aprire PowerShell come Amministratore ed eseguire:
#      Set-ExecutionPolicy Unrestricted
#    Rispondere A (Yes to All) → chiudere la finestra.

# 1. Clona il fork Windows dalla root del progetto OMNIA.
#    OBBLIGATORIO: --recurse-submodules (il repo include submoduli CUDA)
git clone --recurse-submodules https://github.com/sdbds/TRELLIS-for-windows.git trellis_server

# 2. Entra nella directory
cd trellis_server

# 3. Esegui lo script di installazione del fork.
#    Crea un venv Python 3.11/3.12, installa PyTorch CUDA 12.4 + kaolin + spconv +
#    flash-attn + xformers + nvdiffrast e tutte le altre dipendenze.
#    (il nome del file include un carattere CJK — usare .\ per eseguire da PS)
.\1、install-uv-qinglong.ps1

# 4. Copia server.py nella directory (creato durante l'implementazione di Fase 12)

# 5. Verifica funzionamento
.venv\Scripts\python.exe server.py --port 8090
# In un altro terminale:
curl http://localhost:8090/health
```

**Requisiti sistema TRELLIS-for-windows:**

| Requisito | Dettaglio |
|---|---|
| Python | 3.10-3.12 (gestito dal venv del fork; non condiviso con OMNIA Python 3.14) |
| CUDA | 12.4 (versione usata dal fork; installare CUDA Toolkit 12.4 a sistema) |
| VS Studio | 2022 con workload "Desktop development with C++" (richiesto per compilare submoduli CUDA) |
| VRAM | **≥ 16GB** per TRELLIS-image-large (1.2B, requisito verificato su A100/A6000); su sistemi con 16GB usare TRELLIS-text-large (1.1B) o TRELLIS-text-base (342M) che richiedono ~8-10GB |
| RAM | ≥ 16GB sistema |
| Disco | ~8GB dipendenze + ~10GB HuggingFace model cache |
| GPU | NVIDIA con compute capability ≥ 7.5 (RTX 20xx+) |

**Aggiunta a `.gitignore`:**

```
trellis_server/
data/3d_models/
```

---

#### 12.4 — TrellisClient (`backend/plugins/cad_generator/client.py`)

**Ruolo**: client HTTP asincrono verso il microservizio TRELLIS.
Non conosce il plugin, il context OMNIA né il ToolRegistry — solo I/O HTTP.

```python
"""TRELLIS microservice HTTP client.

Wraps the TRELLIS server.py API with typed async methods.
Isolated from OMNIA internals — only does HTTP I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from backend.core.config import TrellisServiceConfig
from backend.core.http_security import validate_url_ssrf


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Result from TRELLIS 3D generation."""

    model_name: str
    format: str          # always "glb" for now
    size_bytes: int
    remote_path: str     # path on microservice filesystem


class TrellisClient:
    """Async HTTP client for the TRELLIS microservice.

    Holds a persistent httpx.AsyncClient. Call close() to release.

    Args:
        config: TrellisServiceConfig with service_url, timeouts, etc.

    Raises:
        RuntimeError: On construction if service_url fails SSRF validation.
    """

    def __init__(self, config: TrellisServiceConfig) -> None:
        validate_url_ssrf(config.service_url)
        self._base_url = config.service_url.rstrip("/")
        self._timeout = config.request_timeout_s
        self._max_bytes = config.max_model_size_mb * 1_048_576
        self._model = config.trellis_model
        self._seed = config.seed
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
        )

    async def health_check(self) -> bool:
        """Return True if the TRELLIS microservice is reachable."""
        try:
            r = await self._client.get("/health", timeout=5.0)
            return r.status_code < 500
        except Exception:
            return False

    async def generate_from_image(
        self,
        image_bytes: bytes,
        model_name: str,
        seed: int = -1,
    ) -> GenerationResult:
        """Generate a 3D GLB model from an image.

        Args:
            image_bytes: PNG/JPEG image bytes.
            model_name: Unique name for the output model.
            seed: Random seed (-1 = random).

        Returns:
            GenerationResult with metadata.

        Raises:
            httpx.HTTPStatusError: On HTTP error from microservice.
        """
        actual_seed = seed if seed >= 0 else self._seed
        files = {"image": ("input.png", image_bytes, "image/png")}
        data = {"seed": str(actual_seed), "output_name": model_name}

        r = await self._client.post("/generate", files=files, data=data)
        r.raise_for_status()
        result = r.json()

        logger.debug(
            "TRELLIS generation '{}' — {} bytes", model_name, result.get("size_bytes", 0)
        )
        return GenerationResult(
            model_name=result["model_name"],
            format=result.get("format", "glb"),
            size_bytes=result.get("size_bytes", 0),
            remote_path=result.get("file_path", ""),
        )

    async def generate_from_text(
        self,
        prompt: str,
        model_name: str,
        seed: int = -1,
    ) -> GenerationResult:
        """Generate a 3D GLB model from a text prompt.

        Requires the TRELLIS microservice to be running a TRELLIS-text-* model
        (start with: .venv/Scripts/python.exe server.py --model TRELLIS-text-large).
        The TRELLIS-image-* models do NOT accept text input — the server returns
        HTTP 400 if called with a text-only request while an image model is loaded.

        Prefer generate_from_image() when possible: TRELLIS-image models produce
        significantly more creative and detailed results (per upstream TRELLIS docs:
        "text-conditioned models are less creative and detailed due to data limitations").

        Args:
            prompt: Text description of the 3D object.
            model_name: Unique name for the output model.
            seed: Random seed (-1 = random).

        Returns:
            GenerationResult with metadata.
        """
        actual_seed = seed if seed >= 0 else self._seed
        data = {"prompt": prompt, "seed": str(actual_seed), "output_name": model_name}

        r = await self._client.post("/generate", data=data)
        r.raise_for_status()
        result = r.json()

        logger.debug(
            "TRELLIS text generation '{}' — {} bytes",
            model_name,
            result.get("size_bytes", 0),
        )
        return GenerationResult(
            model_name=result["model_name"],
            format=result.get("format", "glb"),
            size_bytes=result.get("size_bytes", 0),
            remote_path=result.get("file_path", ""),
        )

    async def download_model(self, model_name: str) -> bytes:
        """Download a generated GLB file from the microservice.

        Args:
            model_name: Name of the model to download.

        Returns:
            Raw GLB bytes.

        Raises:
            httpx.HTTPStatusError: On HTTP error.
            ValueError: If file exceeds max_model_size_mb.
        """
        r = await self._client.get(f"/models/{model_name}")
        r.raise_for_status()
        if len(r.content) > self._max_bytes:
            raise ValueError(
                f"Model '{model_name}' exceeds max size "
                f"({len(r.content) // 1_048_576} MB > {self._max_bytes // 1_048_576} MB)"
            )
        return r.content

    async def unload_model(self) -> None:
        """Ask the microservice to unload TRELLIS from VRAM."""
        try:
            r = await self._client.post("/unload", timeout=10.0)
            r.raise_for_status()
            logger.info("TRELLIS model unloaded from VRAM")
        except Exception as exc:
            logger.warning("Failed to unload TRELLIS model: {}", exc)

    async def close(self) -> None:
        """Release the underlying httpx.AsyncClient connection pool."""
        await self._client.aclose()
```

**Nota sicurezza `validate_url_ssrf`**: identica alla nota del 12.3 precedente. `localhost`
e `127.0.0.1` devono essere permessi (il microservizio TRELLIS gira sulla stessa macchina).

---

#### 12.5 — Orchestrazione VRAM (unload/reload LLM automatico)

**Ruolo**: durante l'esecuzione del tool `cad_generate`, il plugin deve liberare VRAM
scaricando il modello LLM da LM Studio, eseguire la generazione TRELLIS, e poi ricaricare
il modello LLM per permettergli di completare la risposta.

L'orchestrazione avviene interamente dentro `CadGeneratorPlugin._execute_cad_generate()`,
usando le API già esposte da `LMStudioService`:

```python
async def _vram_swap_generate(
    self,
    description: str,
    model_name: str,
) -> tuple[GenerationResult | None, str | None]:
    """Execute TRELLIS generation with VRAM swap if configured.

    Steps:
        1. Get current LLM model info from LM Studio
        2. Unload LLM from VRAM via LM Studio API
        3. Wait for VRAM to be freed (short sleep for GPU driver)
        4. Call TRELLIS microservice /generate
        5. Ask TRELLIS to unload its model from VRAM
        6. Reload LLM via LM Studio API
        7. Return generation result

    Args:
        description: Natural language description of the 3D object.
        model_name: Name for the generated model.

    Returns:
        Tuple of (GenerationResult or None, error_message or None).
    """
    cfg = self._ctx.config.trellis
    lmstudio: LMStudioManagerProtocol = self._ctx.lmstudio_manager
    client = self._client

    # Step 1: Capture current LLM state for reload
    llm_model_id = None
    if cfg.auto_vram_swap:
        try:
            loaded_models = await lmstudio.list_loaded_models()
            if loaded_models:
                llm_model_id = loaded_models[0].get("id") or loaded_models[0].get("instance_id")
                # Unload LLM
                logger.info("VRAM swap: unloading LLM '{}'", llm_model_id)
                await lmstudio.unload_model(llm_model_id)
                # Brief pause for GPU driver to fully release memory
                await asyncio.sleep(2)
        except Exception as exc:
            logger.warning("VRAM swap: failed to unload LLM: {}", exc)
            # Continue anyway — TRELLIS might still work if enough VRAM

    # Step 2: Generate with TRELLIS
    gen_result = None
    gen_error = None
    try:
        gen_result = await client.generate_from_text(description, model_name)
    except httpx.HTTPStatusError as exc:
        gen_error = f"TRELLIS generation error: {exc.response.text[:500]}"
    except Exception as exc:
        gen_error = f"TRELLIS generation failed: {exc}"

    # Step 3: Unload TRELLIS model from VRAM
    try:
        await client.unload_model()
    except Exception:
        pass  # Best-effort — LLM reload is more important

    # Step 4: Reload LLM
    if cfg.auto_vram_swap and llm_model_id:
        try:
            logger.info("VRAM swap: reloading LLM '{}'", llm_model_id)
            await lmstudio.load_model(llm_model_id)
            # Wait for model to be fully loaded
            for _ in range(30):  # max 30s wait
                await asyncio.sleep(1)
                loaded = await lmstudio.list_loaded_models()
                if any(m.get("id") == llm_model_id for m in loaded):
                    break
        except Exception as exc:
            logger.error("VRAM swap: CRITICAL — failed to reload LLM: {}", exc)
            gen_error = (gen_error or "") + f" [WARNING: LLM reload failed: {exc}]"

    return gen_result, gen_error
```

**Garanzie di sicurezza:**

1. **LLM reload è always-attempted**: anche se TRELLIS fallisce, il blocco `finally` di
   `_execute_cad_generate()` tenta il reload dell'LLM. L'utente non si ritrova mai senza LLM.
2. **Timeout**: il reload ha un loop di max 30 iterazioni × 1s = 30s. Se supera, continua
   con un warning nel risultato.
3. **Fallback senza swap**: se `auto_vram_swap: false`, il plugin chiama TRELLIS direttamente
   senza toccare l'LLM (utile su GPU con ≥ 24GB VRAM dove entrambi possono coesistere).

---

#### 12.6 — CadGeneratorPlugin (`backend/plugins/cad_generator/plugin.py`)

**Ruolo**: plugin OMNIA che espone il tool LLM `cad_generate` per generare modelli 3D.
Gestisce il ciclo di vita del `TrellisClient`, l'orchestrazione VRAM, e il salvataggio
locale del file GLB.

```
backend/plugins/cad_generator/
├── __init__.py     ← import + PLUGIN_REGISTRY["cad_generator"] = CadGeneratorPlugin
├── plugin.py       ← CadGeneratorPlugin(BasePlugin) — tool + VRAM orchestration
└── client.py       ← TrellisClient — HTTP I/O verso microservizio
```

**`__init__.py`** — pattern identico a tutti gli altri plugin:

```python
"""O.M.N.I.A. — CAD Generator plugin package (TRELLIS neural 3D generation).

Importing this module registers CadGeneratorPlugin in the static PLUGIN_REGISTRY.
Requires the TRELLIS microservice running on trellis.service_url.
See https://github.com/sdbds/TRELLIS-for-windows for setup instructions.
"""
from backend.core.plugin_manager import PLUGIN_REGISTRY
from backend.plugins.cad_generator.plugin import CadGeneratorPlugin  # noqa: F401

PLUGIN_REGISTRY["cad_generator"] = CadGeneratorPlugin
```

**`plugin.py`** — `CadGeneratorPlugin(BasePlugin)`:

```python
class CadGeneratorPlugin(BasePlugin):
    """Generates 3D models from natural language via the TRELLIS neural network.

    Uses the TRELLIS microservice (separate Python 3.10-3.12 process) to convert
    text descriptions or images into GLB 3D models. Manages VRAM orchestration
    (LLM unload → TRELLIS generate → LLM reload) automatically when configured.

    The generated GLB file is saved locally and served via /api/cad/ proxy route.
    The frontend renders it with Three.js GLTFLoader.
    """

    plugin_name = "cad_generator"
    plugin_version = "1.0.0"
    plugin_description = (
        "Genera modelli 3D da descrizioni in linguaggio naturale tramite TRELLIS. "
        "I modelli vengono visualizzati interattivamente nel frontend via Three.js."
    )
    plugin_dependencies: list[str] = []
    plugin_priority: int = 20  # bassa priorità: operazione pesante, non essenziale

    def __init__(self) -> None:
        super().__init__()
        self._client: TrellisClient | None = None

    async def initialize(self, ctx: AppContext) -> None:
        """Start the TrellisClient and check microservice availability."""
        await super().initialize(ctx)
        cfg = ctx.config.trellis
        self._client = TrellisClient(cfg)

        # Ensure local output directory exists
        output_dir = Path(cfg.model_output_dir)
        if not output_dir.is_absolute():
            output_dir = Path(ctx.config.project_root) / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir = output_dir

        reachable = await self._client.health_check()
        if not reachable:
            logger.warning(
                "CadGeneratorPlugin: TRELLIS microservice non raggiungibile a {}. "
                "I tool CAD restituiranno un errore finché il servizio non è avviato.",
                cfg.service_url,
            )

    async def cleanup(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        await super().cleanup()

    async def get_connection_status(self) -> ConnectionStatus:
        if self._client is None:
            return ConnectionStatus.DISCONNECTED
        healthy = await self._client.health_check()
        return ConnectionStatus.CONNECTED if healthy else ConnectionStatus.DISCONNECTED
```

**Tool definition** (restituita da `get_tools()`):

| Tool | risk_level | requires_confirmation | timeout_ms | Descrizione |
|---|---|---|---|---|
| `cad_generate` | `safe` | `False` | 180000 | Genera un modello 3D da una descrizione testuale, visualizzabile nel frontend |

**Schema tool `cad_generate`**:

```json
{
  "type": "object",
  "properties": {
    "description": {
      "type": "string",
      "description": "Descrizione in linguaggio naturale dell'oggetto 3D da generare. Più dettagliata è la descrizione, migliore sarà il risultato. Es: 'un vaso decorativo con motivi floreali in rilievo, alto circa 30cm, stile Art Nouveau'",
      "maxLength": 2000
    },
    "model_name": {
      "type": "string",
      "description": "Nome identificativo del modello (solo lettere, numeri, underscore). Se omesso, viene generato automaticamente.",
      "pattern": "^[a-zA-Z0-9_]{1,64}$"
    }
  },
  "required": ["description"]
}
```

**Implementazione `execute_tool("cad_generate", args, ctx)`**:

```python
async def _execute_cad_generate(self, args: dict, context: ExecutionContext) -> ToolResult:
    if self._client is None:
        return ToolResult.error("CadGeneratorPlugin non inizializzato.")

    description: str = args["description"]
    raw_name = args.get("model_name") or f"model_{context.execution_id[:8]}"
    name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name)[:64]

    # 1. Verifica connessione microservizio
    if not await self._client.health_check():
        return ToolResult.error(
            f"TRELLIS microservice non raggiungibile a "
            f"{self._ctx.config.trellis.service_url}. "
            "Assicurarsi che il microservizio sia avviato:\n"
            "  cd trellis_server && .venv\\Scripts\\python.exe server.py"
        )

    # 2. VRAM swap + generazione
    try:
        gen_result, gen_error = await self._vram_swap_generate(description, name)
    except Exception as exc:
        return ToolResult.error(f"Errore generazione 3D: {exc}")

    if gen_error and gen_result is None:
        return ToolResult.error(gen_error)

    # 3. Download GLB dal microservizio e salva localmente
    try:
        glb_bytes = await self._client.download_model(gen_result.model_name)
        local_path = self._output_dir / f"{gen_result.model_name}.glb"
        local_path.write_bytes(glb_bytes)
    except Exception as exc:
        error_msg = f"Errore download modello: {exc}"
        if gen_error:
            error_msg = f"{gen_error}; {error_msg}"
        return ToolResult.error(error_msg)

    # 4. Restituisci URL per il frontend
    export_url = f"/api/cad/models/{gen_result.model_name}"
    payload = {
        "model_name": gen_result.model_name,
        "export_url": export_url,
        "format": "glb",
        "size_bytes": gen_result.size_bytes,
        "description": description,
    }

    warning = ""
    if gen_error:
        warning = f" (avviso: {gen_error})"

    return ToolResult(
        success=True,
        content=json.dumps(payload),
        content_type="application/vnd.omnia.cad-model+json",
    )
```

**Perché l'URL e non i bytes**: il tool restituisce solo il JSON con l'URL al file —
il front-end carica il binario GLB direttamente dalla route proxy `/api/cad/` tramite
una normale richiesta HTTP GET. Questo evita di passare file potenzialmente da decine
di MB attraverso il WebSocket, mantenendo il canale WebSocket per soli messaggi di
controllo leggeri. Pattern identico a quello usato per gli screenshot in Phase 5.

---

#### 12.7 — REST Proxy `/api/cad/` (`backend/api/routes/cad.py`)

**Ruolo**: serve i file GLB generati dal microservizio TRELLIS al frontend Electron.
Il proxy è necessario per mantenere il file serving sotto il dominio OMNIA (localhost:8000),
evitando problemi CSP nel renderer Electron.

Router con prefix e tag coerenti (pattern `tasks.py`, `memory.py`):

```python
router = APIRouter(prefix="/cad", tags=["cad"])
```

**Endpoint esposti:**

```
GET  /api/cad/models/{model_name}    — serve file GLB dal filesystem locale
GET  /api/cad/models                 — lista modelli generati (dal filesystem locale)
GET  /api/cad/health                 — health check del microservizio TRELLIS
```

**Implementazione `/api/cad/models/{model_name}`**:

```python
@router.get("/models/{model_name}")
async def get_model(
    model_name: str,
    request: Request,
) -> FileResponse:
    """Serve a generated GLB 3D model file.

    Args:
        model_name: Model identifier (alphanumeric + underscore only).

    Returns:
        FileResponse with the GLB binary file.

    Raises:
        HTTPException 400: Invalid model name.
        HTTPException 404: Model not found.
    """
    # Input validation anti-path-traversal
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", model_name):
        raise HTTPException(status_code=400, detail="Nome modello non valido.")

    ctx: AppContext = request.app.state.context
    output_dir = Path(ctx.config.trellis.model_output_dir)
    if not output_dir.is_absolute():
        output_dir = Path(ctx.config.project_root) / output_dir

    file_path = output_dir / f"{model_name}.glb"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Modello '{model_name}' non trovato.")

    # Verify the resolved path is within the output directory (symlink protection)
    if not file_path.resolve().is_relative_to(output_dir.resolve()):
        raise HTTPException(status_code=400, detail="Path non valido.")

    return FileResponse(
        path=file_path,
        media_type="model/gltf-binary",
        filename=f"{model_name}.glb",
    )
```

**Registrazione in `backend/api/routes/__init__.py`**:

```python
from backend.api.routes import audit, cad, calendar, chat, config, events, models, plugins, settings, tasks, voice

router.include_router(cad.router)  # /api/cad/*
```

**Sicurezza**:

- Validazione `model_name` con regex `[a-zA-Z0-9_]{1,64}` — previene path traversal
- `file_path.resolve().is_relative_to()` — protezione aggiuntiva contro symlink
- I file vengono serviti dal filesystem locale (`data/3d_models/`), non dal microservizio TRELLIS
  in tempo reale — nessun proxy HTTP-to-HTTP con rischi SSRF
- Nessuna autenticazione per v1 (OMNIA gira in locale — coerente con il resto delle API)

---

#### 12.8 — Frontend: `CADViewer.vue` (Three.js + GLTFLoader)

**Dipendenze da aggiungere a `frontend/package.json`**:

```bash
cd frontend
npm install three
npm install --save-dev @types/three
```

**CSP update in `frontend/src/main/index.ts`**:

Aggiungere `'wasm-unsafe-eval'` a `script-src` nella Content Security Policy per permettere
la decompressione Draco (opzionale per GLB, ma Three.js la usa se disponibile):

```typescript
// In webPreferences o CSP header:
// script-src 'self' 'wasm-unsafe-eval';
```

**Componente `frontend/src/renderer/src/components/chat/CADViewer.vue`**:

Il componente è lazy-loaded (`defineAsyncComponent`) per non aumentare il bundle iniziale
dell'app (Three.js pesa ~600KB gzip).

```vue
<script setup lang="ts">
/**
 * Interactive 3D model viewer using Three.js + GLTFLoader.
 *
 * Renders a GLB model generated by TRELLIS via the /api/cad/ proxy route.
 * Supports: orbit controls (drag/scroll/right-drag), zoom, auto-rotate toggle,
 * wireframe toggle, and model download.
 *
 * Props:
 *   modelUrl - Relative URL to the GLB file (e.g. /api/cad/models/xxx)
 *   modelName - Display name for the model (used in download filename)
 */
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { resolveBackendUrl } from '@/services/api'

const props = defineProps<{
  modelUrl: string
  modelName?: string
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const wireframe = ref(false)
const autoRotate = ref(false)

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let frameId: number | null = null
let controls: InstanceType<typeof OrbitControls> | null = null
let loadedModel: THREE.Group | null = null

async function initScene(): Promise<void> {
  const container = containerRef.value
  if (!container) return

  const w = container.clientWidth
  const h = container.clientHeight || 360

  // Scene
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a2e)

  // Camera
  const camera = new THREE.PerspectiveCamera(50, w / h, 0.01, 10000)
  camera.position.set(0, 1.5, 3)

  // Lighting (PBR-friendly setup for GLB materials)
  const ambient = new THREE.AmbientLight(0xffffff, 0.4)
  scene.add(ambient)
  const dir1 = new THREE.DirectionalLight(0xffffff, 1.0)
  dir1.position.set(5, 10, 7)
  dir1.castShadow = true
  scene.add(dir1)
  const dir2 = new THREE.DirectionalLight(0xffffff, 0.3)
  dir2.position.set(-3, 5, -5)
  scene.add(dir2)
  // Environment hemisphere for natural fill
  const hemi = new THREE.HemisphereLight(0xddeeff, 0x0f0e0d, 0.5)
  scene.add(hemi)

  // Grid helper for spatial reference
  const grid = new THREE.GridHelper(10, 20, 0x333355, 0x222244)
  scene.add(grid)

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(w, h)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  container.appendChild(renderer.domElement)

  // Controls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.autoRotate = autoRotate.value
  controls.autoRotateSpeed = 2.0

  // Load GLB
  const loader = new GLTFLoader()
  const fullUrl = resolveBackendUrl(props.modelUrl)

  try {
    const gltf = await new Promise<{ scene: THREE.Group }>((resolve, reject) => {
      loader.load(fullUrl, resolve, undefined, reject)
    })
    loadedModel = gltf.scene

    // Auto-fit camera to model bounding box
    const box = new THREE.Box3().setFromObject(loadedModel)
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3()).length()

    loadedModel.position.sub(center)  // center the model at origin
    camera.position.set(0, size * 0.5, size * 1.5)
    camera.far = size * 10
    camera.updateProjectionMatrix()
    controls.target.set(0, 0, 0)
    controls.update()

    scene.add(loadedModel)
    loading.value = false

    // Render loop
    const animate = (): void => {
      frameId = requestAnimationFrame(animate)
      controls!.autoRotate = autoRotate.value
      controls!.update()
      renderer!.render(scene!, camera)
    }
    animate()
  } catch (err) {
    error.value = `Impossibile caricare il modello: ${err}`
    loading.value = false
  }

  // Resize observer
  const resizeObserver = new ResizeObserver(() => {
    if (!container || !renderer) return
    const nw = container.clientWidth
    const nh = container.clientHeight || 360
    camera.aspect = nw / nh
    camera.updateProjectionMatrix()
    renderer.setSize(nw, nh)
  })
  resizeObserver.observe(container)
}

function toggleWireframe(): void {
  wireframe.value = !wireframe.value
  if (loadedModel) {
    loadedModel.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const mat = child.material as THREE.MeshStandardMaterial
        mat.wireframe = wireframe.value
      }
    })
  }
}

function download(): void {
  const link = document.createElement('a')
  link.href = resolveBackendUrl(props.modelUrl)
  link.download = `${props.modelName ?? 'model'}.glb`
  link.click()
}

function resetCamera(): void {
  controls?.reset()
}

onMounted(initScene)

onUnmounted(() => {
  if (frameId !== null) cancelAnimationFrame(frameId)
  renderer?.dispose()
  controls?.dispose()
})
</script>

<template>
  <div class="cad-viewer-wrapper">
    <div class="cad-viewer-toolbar">
      <span class="cad-viewer-title">
        🧊 {{ modelName ?? 'Modello 3D' }}
      </span>
      <div class="cad-viewer-actions">
        <button @click="autoRotate = !autoRotate" :class="{ active: autoRotate }"
                title="Auto-rotazione">⟳</button>
        <button @click="toggleWireframe" :class="{ active: wireframe }"
                title="Wireframe">⬡</button>
        <button @click="resetCamera" title="Reset vista">⌖</button>
        <button @click="download" title="Scarica GLB">⬇</button>
      </div>
    </div>
    <div ref="containerRef" class="cad-viewer-canvas" :style="{ height: '360px' }">
      <div v-if="loading" class="cad-viewer-overlay">
        <div class="cad-viewer-spinner" />
        Generazione modello 3D in corso…
      </div>
      <div v-if="error" class="cad-viewer-overlay cad-viewer-error">{{ error }}</div>
    </div>
  </div>
</template>

<style scoped>
.cad-viewer-wrapper {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(79, 195, 247, 0.2);
  background: #1a1a2e;
  margin: 8px 0;
}
.cad-viewer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 13px;
  color: #b0bec5;
}
.cad-viewer-title { font-weight: 500; color: #4fc3f7; }
.cad-viewer-actions { display: flex; gap: 8px; }
.cad-viewer-actions button {
  background: none;
  border: 1px solid rgba(255,255,255,0.15);
  color: #b0bec5;
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
}
.cad-viewer-actions button:hover { border-color: #4fc3f7; color: #4fc3f7; }
.cad-viewer-actions button.active {
  border-color: #4fc3f7; color: #4fc3f7; background: rgba(79,195,247,0.1);
}
.cad-viewer-canvas { position: relative; width: 100%; }
.cad-viewer-overlay {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px;
  color: #b0bec5; font-size: 14px; background: rgba(26, 26, 46, 0.9);
}
.cad-viewer-error { color: #ef5350; }
.cad-viewer-spinner {
  width: 32px; height: 32px;
  border: 3px solid rgba(79, 195, 247, 0.2);
  border-top-color: #4fc3f7;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

**Lazy loading in `ToolExecutionIndicator.vue`** — usando `defineAsyncComponent`:

```typescript
import { defineAsyncComponent } from 'vue'

const CADViewer = defineAsyncComponent(
  () => import('./CADViewer.vue')
)
```

---

#### 12.9 — Frontend: Estensione `ToolExecutionIndicator.vue` + `types/chat.ts`

**`frontend/src/renderer/src/types/chat.ts`** — aggiunta dell'interfaccia `CadModelPayload`:

```typescript
/**
 * Payload JSON del ToolResult con content_type='application/vnd.omnia.cad-model+json'.
 * Generato da CadGeneratorPlugin.cad_generate().
 */
export interface CadModelPayload {
  model_name: string
  /** URL relativo della route proxy: /api/cad/models/{name} */
  export_url: string
  /** Formato: sempre "glb" per TRELLIS */
  format: string
  /** Dimensione file in bytes */
  size_bytes?: number
  /** Descrizione originale usata per la generazione */
  description?: string
}
```

**`ToolExecutionIndicator.vue`** — aggiunta del caso `application/vnd.omnia.cad-model+json`
nel template. La gestione segue il pattern esistente per `image/*`:

```typescript
// Nella sezione <script setup> — helper per parsare il payload
function parseCadPayload(result: string): CadModelPayload | null {
  try {
    const parsed = JSON.parse(result) as CadModelPayload
    if (typeof parsed.model_name === 'string' && typeof parsed.export_url === 'string') {
      return parsed
    }
    return null
  } catch {
    return null
  }
}
```

Nel `<template>`, nel blocco che renderizza il risultato per ogni `exec in executions`,
aggiungere il caso CAD model accanto al caso image esistente:

```vue
<!-- caso immagini (già esistente) -->
<img
  v-if="exec.result && exec.contentType?.startsWith('image/')"
  :src="`data:${exec.contentType};base64,${exec.result}`"
  class="tool-result-image"
/>
<!-- caso modello 3D (aggiunto in Fase 12) -->
<template v-else-if="exec.contentType === 'application/vnd.omnia.cad-model+json' && exec.result">
  <CADViewer
    :model-url="parseCadPayload(exec.result)?.export_url ?? ''"
    :model-name="parseCadPayload(exec.result)?.model_name"
  />
</template>
```

**Nessuna modifica a:**

- `useChat.ts` — già passa `content_type` a `store.completeToolExecution()` senza dispatch speciale
- `chat.ts` Pinia store — già memorizza `contentType?: string` in `ToolExecution`
- `ws.ts` WebSocket manager — invariato
- `MessageBubble.vue` — i tool result nelle conversazioni caricate da DB non hanno `contentType`
  (non persistito in DB) → nessun `CADViewer` in storico (comportamento accettabile per v1,
  coerente con screenshot che presentano la stessa limitazione)

---

#### 12.10 — System Prompt Update (`config/system_prompt.md`)

Aggiungere una nuova sezione per il tool `cad_generate`:

```markdown
### Generazione 3D (cad_generate)

Quando l'utente chiede di creare, visualizzare o generare un oggetto 3D:

- Usa `cad_generate(description="...")` con una descrizione DETTAGLIATA dell'oggetto
- Più dettagliata è la descrizione, migliore sarà il risultato (forma, dimensioni,
  materiale apparente, stile, dettagli decorativi)
- Il modello 3D verrà generato automaticamente e visualizzato nel frontend
- NON scrivere codice CAD — il sistema usa una rete neurale image-to-3D (TRELLIS)
- Usa `model_name` descrittivi in inglese (es. "decorative_vase", "phone_stand")
- Se il risultato non soddisfa l'utente, riprova con una descrizione più precisa
- Avvisa l'utente che la generazione richiede 30-90 secondi

Esempi di buone descrizioni:
- "A sleek modern phone stand with curved edges, matte black finish, minimalist design"
- "A decorative vase, tall and slender, with Art Nouveau floral relief patterns"
- "A small gear mechanism with 12 teeth, industrial style, metallic appearance"

### Documentazione (ebook-mcp)

Se configurato, puoi consultare documenti PDF/EPUB:
- Usa `get_toc` per la struttura del documento prima di leggere sezioni specifiche
- Usa `get_chapter_markdown` per leggere solo i capitoli necessari
```

---

#### 12.11 — Dipendenze e Compatibilità

**Backend — nessuna nuova dipendenza Python:**

Il plugin `cad_generator` usa solo `httpx` (già presente) e `json` (stdlib).
TRELLIS e tutte le sue dipendenze pesanti (PyTorch, kaolin, flash-attn, xformers, spconv)
vivono nel venv isolato del microservizio `trellis_server/` — mai installate nel
venv OMNIA.

**Frontend — dipendenze Three.js:**

```json
{
  "dependencies": {
    "three": "^0.170.0"
  },
  "devDependencies": {
    "@types/three": "^0.170.0"
  }
}
```

Installazione: `cd frontend && npm install three && npm install --save-dev @types/three`

**Microservizio TRELLIS — processo separato:**

| Componente | Dettaglio |
|---|---|
| Repository | `sdbds/TRELLIS-for-windows` (MIT license) |
| Python | 3.10-3.12 (venv isolato, non condiviso con OMNIA) |
| CUDA | 12.4+ (toolkit installato a sistema) |
| VS Studio | 2022 con "Desktop development with C++" |
| Installer | `1、install-uv-qinglong.ps1` nella directory clonata |
| Run command | `.venv\Scripts\python.exe server.py --port 8090` |
| Verifica | `curl http://localhost:8090/health` |

Il microservizio TRELLIS non è un requisito hard di OMNIA: se non installato/avviato,
il plugin si carica, mostra status `DISCONNECTED` nella UI plugin, e il tool `cad_generate`
restituisce un messaggio di errore descrittivo con istruzioni di setup. Il resto dell'app
funziona normalmente.

**VRAM Budget (tabella aggiornata):**

| Componente | VRAM | Note |
|---|---|---|
| LLM (Qwen 3.5 9B, Q4) | ~10 GB | Scaricato durante generazione 3D (`auto_vram_swap`) |
| STT (faster-whisper) | ~1.5 GB | Rimane caricato — contribuisce al footprint totale |
| TTS (Piper) | ~200 MB | CPU-only per default |
| TRELLIS-image-large (1.2B) | ~12-16 GB | Caricato on-demand, scaricato dopo generazione |
| TRELLIS-text-large (1.1B) | ~10-12 GB | Alternativa consigliata su sistemi con 16GB per flusso text-only |
| Three.js viewer (GPU) | < 100 MB | GPU RAM del renderer Electron, non VRAM dedicata |
| ebook-mcp (uv) | 0 MB | CPU only |

**Flusso VRAM durante generazione 3D (con `auto_vram_swap: true`):**

```
Stato normale:              LLM (10GB) + STT (1.5GB)                         = ~11.5 GB
Tool execution (image-lg):  LLM unloaded + TRELLIS (15GB) + STT (1.5GB)    = ~16.5 GB  ← margine stretto su RTX 5080
Tool execution (text-lg):   LLM unloaded + TRELLIS (11GB) + STT (1.5GB)    = ~12.5 GB  ✓ sicuro
Post-generation:            TRELLIS unloaded + LLM (10GB) + STT (1.5GB)    = ~11.5 GB  (stato normale)
```

**Nota VRAM per RTX 5080 (16GB)**: TRELLIS-image-large richiede fino a 16GB per i
picchi di generazione (buffers intermedi inclusi). Su sistemi con esattamente 16GB e
STT caricato (~1.5GB), potrebbe verificarsi OOM. Opzioni:
1. Usare `TRELLIS-text-large` (1.1B, ~10-12GB) per flusso text-only — sempre sicuro
2. Aggiungere `stop_stt_during_generation: true` alla configurazione (implementazione futura)
3. Usare `TRELLIS-image-large` accettando il rischio di OOM occasionale

---

#### 12.12 — Test Suite Fase 12

**`backend/tests/test_trellis_client.py`**:

- `test_health_check_success`: mock httpx GET /health → `True`
- `test_health_check_failure_returns_false`: `ConnectError` → `False` (no raise)
- `test_generate_from_image_success`: mock POST /generate con file → `GenerationResult`
- `test_generate_from_text_success`: mock POST /generate con prompt → `GenerationResult`
- `test_generate_http_error`: mock 500 → `HTTPStatusError` propagato
- `test_download_model_success`: mock GET /models/{name} → bytes
- `test_download_model_exceeds_size`: mock 120MB response → `ValueError`
- `test_unload_model`: mock POST /unload → success, no raise
- `test_ssrf_validation_rejects_remote_url`: URL `http://192.168.1.200:8090` → `RuntimeError`
- `test_ssrf_validation_allows_localhost`: `http://localhost:8090` → nessun errore

**`backend/tests/test_cad_generator_plugin.py`**:

- `test_initialize_reachable`: mock health_check True → plugin status CONNECTED
- `test_initialize_unreachable_no_crash`: mock health_check False → plugin carica,
  warning loggato, nessun crash (graceful degradation)
- `test_cad_generate_tool_definition`: `get_tools()` restituisce `ToolDefinition` per
  `cad_generate` con `risk_level="safe"`, `timeout_ms=180000`
- `test_cad_generate_success`: mock generazione + download → `ToolResult.success=True`,
  `content_type="application/vnd.omnia.cad-model+json"`, content è JSON valido con
  `model_name` e `export_url`
- `test_cad_generate_microservice_offline`: mock health_check False →
  `ToolResult.success=False`, errore con istruzioni setup
- `test_cad_generate_generation_error`: mock generate 500 → `ToolResult.success=False`
- `test_cad_generate_auto_name`: `model_name` assente → nome generato da execution_id
- `test_cad_generate_sanitizes_name`: `model_name="test-model/v2"` → `"test_model_v2"`
- `test_vram_swap_unload_reload`: mock LM Studio list_loaded + unload + load →
  sequenza corretta di chiamate verificata
- `test_vram_swap_disabled`: `auto_vram_swap=false` → nessuna chiamata unload/load
- `test_vram_swap_reload_after_trellis_failure`: TRELLIS fallisce → LLM viene
  comunque ricaricato (garanzia di sicurezza)
- `test_cleanup_closes_client`: `cleanup()` → `client.close()` chiamato

**`backend/tests/test_cad_proxy_route.py`**:

- `test_get_model_success`: GET `/api/cad/models/test_cube` → mock file exists →
  `200 OK`, `Content-Type: model/gltf-binary`
- `test_get_model_not_found`: file non esiste → `404`
- `test_get_model_invalid_name`: `model_name="../../etc/passwd"` → `400 Bad Request`
- `test_get_model_plugin_not_active`: plugin disabilitato → config trellis assente → `404`
- `test_cad_health`: GET `/api/cad/health` → mock health_check True → `200 {"status": "ok"}`
- `test_cad_model_list`: GET `/api/cad/models` → listing directory locale → JSON array

**Verifica no-regression**: tutta la suite esistente deve passare invariata. In particolare,
verificare che `_tool_loop.py` (non modificato) gestisca correttamente il timeout esteso
(180s) del tool `cad_generate` e che `ToolResult` con `content_type` diverso da `image/*`
segua il path normale senza troncamenti.

---

#### 12.13 — File Structure Fase 12

```
trellis_server/                              ← microservizio separato (Python 3.10-3.12, gitignored)
├── server.py                                ← Mini FastAPI server (porta 8090)
├── 1、install-uv-qinglong.ps1                ← installer dal fork sdbds
├── .venv/                                   ← venv Python 3.10-3.12 isolato
└── ... (repo TRELLIS-for-windows)

backend/
├── plugins/
│   └── cad_generator/
│       ├── __init__.py                      ← PLUGIN_REGISTRY["cad_generator"]
│       ├── plugin.py                        ← CadGeneratorPlugin + VRAM orchestration
│       └── client.py                        ← TrellisClient (httpx → microservizio)
├── api/
│   └── routes/
│       ├── cad.py                           ← REST /api/cad/* (serve GLB locali)
│       └── __init__.py                      ← + cad.router
├── core/
│   └── config.py                            ← + TrellisServiceConfig + OmniaConfig.trellis
└── tests/
    ├── test_trellis_client.py
    ├── test_cad_generator_plugin.py
    └── test_cad_proxy_route.py

config/
├── default.yaml                             ← + trellis: section + ebook-mcp in mcp.servers
└── system_prompt.md                         ← + sezione cad_generate + documentazione

frontend/
├── package.json                             ← + three, @types/three
└── src/
    ├── main/
    │   └── index.ts                         ← + 'wasm-unsafe-eval' in CSP (per Draco)
    └── renderer/src/
        ├── components/
        │   └── chat/
        │       ├── CADViewer.vue            ← Three.js + GLTFLoader (nuovo)
        │       └── ToolExecutionIndicator.vue ← + caso content_type cad-model
        └── types/
            └── chat.ts                      ← + CadModelPayload interface

data/
└── 3d_models/                               ← file GLB generati (gitignored)
```

---

#### 12.14 — Ordine di Implementazione Consigliato

1. **`TrellisServiceConfig`** in `config.py` + `default.yaml` entry — zero dipendenze
2. **`trellis_server/server.py`** — microservizio standalone, testabile indipendentemente
3. **`TrellisClient`** + test `test_trellis_client.py` — layer I/O isolabile con mock
4. **`CadGeneratorPlugin`** + `__init__.py` + VRAM orchestration + test `test_cad_generator_plugin.py`
5. **`cad.py` route** + registrazione in `routes/__init__.py` + test `test_cad_proxy_route.py`
6. **`types/chat.ts`** — aggiunta `CadModelPayload` (frontend, zero rischio)
7. **`CADViewer.vue`** — componente Three.js GLTFLoader (frontend, standalone)
8. **`ToolExecutionIndicator.vue`** — aggiunta caso CAD (frontend, minimale)
9. **CSP update** — `'wasm-unsafe-eval'` in `index.ts` (1 riga)
10. **`config/system_prompt.md`** — aggiunta sezioni generazione 3D e documentazione
11. **`default.yaml`** — aggiunta entry `ebook-mcp` commentata in `mcp.servers`
12. **Test manuale**: installare TRELLIS-for-windows → avviare microservizio →
    attivare plugin → "crea un vaso decorativo" → verificare Three.js viewer nel frontend

---

#### 12.15 — Verifiche Fase 12

| Scenario | Comportamento atteso |
|---|---|
| "Crea un vaso decorativo Art Nouveau con rilievi floreali" | LLM scrive description → chiama `cad_generate` → VRAM swap (LLM unload) → TRELLIS genera GLB → VRAM swap (LLM reload) → `ToolResult(content_type="application/vnd.omnia.cad-model+json")` → frontend mostra `CADViewer.vue` con modello 3D interattivo |
| Utente ruota il modello | OrbitControls Three.js funzionanti — drag/scroll/pinch |
| Utente clicca "⬇ Scarica GLB" | `GET /api/cad/models/{name}` → download file .glb |
| TRELLIS microservizio non avviato | `health_check()` → False → `ToolResult(success=False, error_message="TRELLIS non raggiungibile... cd trellis_server && ...")` — nessun crash |
| Generazione 3D fallisce (CUDA OOM) | TRELLIS restituisce 500 → ToolResult error → LLM comunque ricaricato (garanzia) |
| `trellis.enabled: false` (default) | Plugin non caricato, zero overhead; altri plugin e chat invariati |
| auto_vram_swap: LLM unload + reload | LLM scaricato prima di TRELLIS, ricaricato dopo — verificare che risposta LLM continui correttamente |
| auto_vram_swap: LLM reload fallisce | Warning nel log + warning nel ToolResult → utente informato, può ricaricare manualmente |
| LLM chiede consultare docs | Se `ebook-mcp` configurato: tool MCP `get_toc` → capitoli → `get_chapter_markdown` |
| `ebook-mcp` non configurato | Zero impatto, tool non nel ToolRegistry |
| `model_name="../../../etc"` via tool | Sanitizzato a `"______etc"` dal plugin |
| GET `/api/cad/models/../../passwd` | Regex `[a-zA-Z0-9_]{1,64}` → `400 Bad Request` |
| Modello GLB > `max_model_size_mb` | `download_model()` → `ValueError` → ToolResult error |
| Conversazione ricaricata da DB | `CADViewer` non compare (content_type non persistito) — comportamento noto v1 |
| `GET /api/plugins` | Card `cad_generator` con status CONNECTED/DISCONNECTED |
| GPU con ≥ 24GB VRAM, `auto_vram_swap: false` | LLM e TRELLIS coesistono — nessun unload/reload |

---

