# TRELLIS 3D Generation — Setup & Troubleshooting Guide

> Guida completa per far funzionare la generazione 3D neurale (TRELLIS) in OMNIA
> su GPU NVIDIA Blackwell (RTX 5080) con Windows + CUDA 12.8 + VS 2025.

## Indice

1. [Panoramica architettura](#1-panoramica-architettura)
2. [Requisiti hardware/software](#2-requisiti-hardwaresoftware)
3. [Installazione TRELLIS-for-windows](#3-installazione-trellis-for-windows)
4. [Aggiornamenti PyTorch per Blackwell (cu128)](#4-aggiornamenti-pytorch-per-blackwell-cu128)
5. [Ricompilazione estensioni CUDA da sorgente](#5-ricompilazione-estensioni-cuda-da-sorgente)
6. [Patch host_config.h per VS 2025 (MSVC 19.50)](#6-patch-host_configh-per-vs-2025-msvc-1950)
7. [Configurazione server.py](#7-configurazione-serverpy)
8. [Configurazione OMNIA](#8-configurazione-omnia)
9. [Avvio e test](#9-avvio-e-test)
10. [Problemi risolti (changelog)](#10-problemi-risolti-changelog)

---

## 1. Panoramica architettura

```
┌────────────────────────────────┐      ┌──────────────────────────────┐
│  OMNIA Backend (Python 3.14)   │      │  TRELLIS Microservice        │
│  ┌──────────────────────────┐  │      │  (Python 3.10, porta 8090)   │
│  │ cad_generator plugin     │──┼─HTTP─┤  trellis_server/server.py    │
│  │ - VRAM swap (unload LLM) │  │      │  - FastAPI wrapper            │
│  │ - httpx async client     │  │      │  - Zero GPU at idle           │
│  └──────────────────────────┘  │      │  - TRELLIS-for-windows venv   │
│  ┌──────────────────────────┐  │      └──────────────────────────────┘
│  │ /api/cad/ proxy routes   │  │
│  └──────────────────────────┘  │      ┌──────────────────────────────┐
│  ┌──────────────────────────┐  │      │  LM Studio                   │
│  │ LLM via LM Studio        │──┼─HTTP─┤  - /api/v1/models/unload     │
│  │ - Unload before TRELLIS  │  │      │  - /api/v1/models/load        │
│  │ - Reload after TRELLIS   │  │      └──────────────────────────────┘
│  └──────────────────────────┘  │
└────────────────────────────────┘
         │
    WebSocket + REST
         │
┌────────────────────────────────┐
│  Frontend (Electron + Vue 3)   │
│  CADViewer.vue (Three.js)      │
│  - GLTFLoader per .glb         │
│  - OrbitControls interattivi   │
└────────────────────────────────┘
```

**Perché un processo separato:** OMNIA usa Python 3.14; TRELLIS richiede 3.10-3.12
(flash-attn, kaolin, spconv non compilano su 3.14). Impossibile coesistere nello
stesso venv. Il microservizio si avvia on-demand e rilascia VRAM quando inattivo.

**VRAM swap:** Con 16GB VRAM (RTX 5080), LLM (~10GB) + TRELLIS (~12GB) non coesistono.
Il plugin `cad_generator` prima scarica l'LLM da VRAM, poi avvia la generazione
TRELLIS, poi ricarica l'LLM. Tutto avviene nella finestra di tool execution
(LLM idle, non serve VRAM).

---

## 2. Requisiti hardware/software

| Componente | Requisito |
|---|---|
| **GPU** | NVIDIA con ≥16GB VRAM (testato su RTX 5080 Blackwell sm_120) |
| **CUDA Toolkit** | v12.8 (per `nvcc`, `cudart.lib`, headers JIT) |
| **VS Build Tools** | 2022 o 2025 (con VS 2025 serve [patch host_config.h](#6-patch-host_configh-per-vs-2025-msvc-1950)) |
| **Python** | 3.10 (nel venv TRELLIS; OMNIA usa 3.14 separatamente) |
| **uv** | Package manager (usato dall'installer TRELLIS) |
| **OS** | Windows 10/11 |
| **LM Studio** | Per gestione LLM e VRAM swap |

---

## 3. Installazione TRELLIS-for-windows

```powershell
# 1. Clone il fork Windows nella root del workspace (accanto alla cartella omnia/)
#    --recurse-submodules è OBBLIGATORIO: inizializza il submodule flexicubes
cd C:\Users\Jays\Desktop\omnia
git clone --recurse-submodules https://github.com/devfrx/TRELLIS-for-windows.git

# 2. Installa con lo script PowerShell di OMNIA
cd omnia
.\scripts\start-trellis.ps1 -Install
```

Lo script `start-trellis.ps1`:
- Trova automaticamente lo script di installazione `1*install-uv-qinglong.ps1`
- Crea un venv Python 3.10 in `TRELLIS-for-windows/.venv/`
- Installa tutte le dipendenze da `requirements.txt`
- Il primo avvio scarica i pesi del modello da HuggingFace (~4GB)

**Layout risultante:**
```
C:\Users\Jays\Desktop\omnia\
├── omnia\                      ← progetto OMNIA
│   ├── trellis_server\server.py  ← microservizio wrapper
│   └── scripts\start-trellis.ps1
└── TRELLIS-for-windows\        ← fork devfrx (Blackwell-ready)
    ├── .venv\                  ← Python 3.10 venv
    ├── requirements.txt        ← aggiornato per cu128
    ├── trellis\
    │   └── representations\mesh\flexicubes\  ← submodule (MaxtirError/FlexiCubes)
    └── extensions\vox2seq\     ← estensione CUDA da ricompilare
```

> **flexicubes** è un git submodule obbligatorio (`MaxtirError/FlexiCubes`).
> Viene inizializzato automaticamente con `--recurse-submodules`.
> Senza di esso, `import trellis` fallisce al primo utilizzo di FlexiCubes
> durante la post-elaborazione della mesh.

---

## 4. Aggiornamenti PyTorch per Blackwell (cu128)

Le GPU Blackwell (RTX 50xx, compute capability sm_120) richiedono **PyTorch cu128**
o superiore. Il `requirements.txt` originale di TRELLIS-for-windows usa cu124/cu126
che non supporta sm_120.

### Modifiche a `requirements.txt`

```diff
- torch==2.5.1+cu124
- torchvision==0.20.1+cu124
+ torch==2.7.0+cu128
+ torchvision==0.22.0+cu128
+ torchaudio==2.7.0+cu128          # aggiunto (non era presente)

- spconv-cu120                     # era cu120, non cu124
+ spconv-cu126                     # cu128 non esiste come pacchetto

- numba==0.60.0                    # era pin fisso
- numpy==1.26.3                    # rimosso pin, lascia risolvere a torch
+ numba>=0.62.0

- https://github.com/bdashore3/flash-attention/releases/download/v2.7.1.post1/flash_attn-2.7.1.post1+cu124torch2.5.1cxx11abiFALSE-cp310-cp310-win_amd64.whl
+ https://github.com/kingbri1/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu128torch2.7.0cxx11abiFALSE-cp310-cp310-win_amd64.whl
```

### Pacchetti aggiornati manualmente

Dopo l'installazione base, queste versioni sono state verificate funzionanti:

| Pacchetto | Versione | Note |
|---|---|---|
| `torch` | 2.7.0+cu128 | Con index `https://download.pytorch.org/whl/cu128` |
| `torchvision` | 0.22.0+cu128 | |
| `flash-attn` | 2.8.3+cu128 | Wheel precompilato da kingbri1 |
| `xformers` | 0.0.30 | Compatibile torch 2.7 |
| `kaolin` | 0.18.0 | `pip install kaolin==0.18.0` |
| `spconv-cu126` | latest | spconv-cu128 non esiste, cu126 funziona su CUDA 12.8 |
| `numba` | 0.64.0 | ≥0.62 per Python 3.10 + numpy compat |
| `nvdiffrast` | 0.3.3 | Wheel da sdbds releases |

---

## 5. Ricompilazione estensioni CUDA da sorgente

TRELLIS richiede 3 estensioni CUDA C++ che vengono compilate con `setup.py`. Le wheel
pre-built nel fork originale sono compilate per torch 2.5.1+cu124 e **non funzionano**
con torch 2.7.0+cu128 (ABI mismatch: `_ZN2at4_ops...` symbol resolution failure).

### Prerequisiti

```powershell
# Variabili d'ambiente necessarie per la compilazione
$env:CUDA_HOME = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8"
$env:TORCH_CUDA_ARCH_LIST = "12.0"   # sm_120 per Blackwell
$env:DISTUTILS_USE_SDK = "1"

# Attivare il venv TRELLIS
& "C:\Users\Jays\Desktop\omnia\TRELLIS-for-windows\.venv\Scripts\Activate.ps1"
```

### 5.1 — diff-gaussian-rasterization

```powershell
# Fork sdbds — supporta torch 2.7 + sm_120 (repo separata, non TRELLIS-for-windows)
cd C:\Users\Jays\Desktop\omnia
git clone https://github.com/sdbds/diff-gaussian-rasterization.git
cd diff-gaussian-rasterization
git submodule update --init --recursive
pip install . --no-build-isolation
```

### 5.2 — diffoctreerast

```powershell
cd C:\Users\Jays\Desktop\omnia
git clone https://github.com/JeffreyXiang/diffoctreerast.git
cd diffoctreerast
pip install . --no-build-isolation
```

### 5.3 — vox2seq

```powershell
cd C:\Users\Jays\Desktop\omnia\TRELLIS-for-windows\extensions\vox2seq
pip install . --no-build-isolation
```

### Verifica

```powershell
python -c "import diff_gaussian_rasterization; print('OK')"
python -c "import diffoctreerast; print('OK')"
python -c "import vox2seq; print('OK')"
```

> **Nota:** La compilazione richiede `ninja` (installato nel venv) e il
> CUDA Toolkit con `nvcc`. Se `ninja` non viene trovato, controllare che
> `Scripts/` del venv sia nel `PATH`.

---

## 6. Patch host_config.h per VS 2025 (MSVC 19.50)

CUDA 12.8 `host_config.h` non riconosce MSVC 19.50+ (Visual Studio 2025).
La compilazione JIT di `nvdiffrast` fallisce con:

```
C:\...\CUDA\v12.8\include\crt\host_config.h(164): fatal error C1189:
#error: -- unsupported Microsoft Visual Studio version!
```

### Fix manuale

Aprire `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8\include\crt\host_config.h`
e cambiare il check di versione massima MSVC:

```c
// Riga ~164, cambiare il valore massimo:
// Da:
#if _MSC_VER < 1910 || _MSC_VER >= 1950
// A:
#if _MSC_VER < 1910 || _MSC_VER >= 2000
```

Questo permette a CUDA 12.8 di accettare MSVC 19.50-19.59 (VS 2025 17.x).

> **Nota:** Questo fix è necessario solo con Visual Studio 2025. Con VS 2022
> non serve alcuna patch.

---

## 7. Configurazione server.py

Il file `trellis_server/server.py` è il wrapper FastAPI che espone TRELLIS come
microservizio HTTP. Caratteristiche principali:

| Feature | Dettaglio |
|---|---|
| **Zero GPU at idle** | Nessun `import torch` a livello modulo — CUDA context creato solo al primo `/generate` |
| **CUDA_HOME auto-detect** | Cerca in `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\` e prende la versione più recente |
| **SPCONV_ALGO=native** | Disabilita auto-benchmarking che aggiunge 30-60s al primo avvio |
| **CUDA_MODULE_LOADING=LAZY** | Caricamento kernel CUDA differito |
| **ninja su PATH** | Aggiunge `Scripts/` del venv al PATH per il JIT di nvdiffrast |
| **Fog of war VRAM** | `/health` riporta VRAM solo se pipeline già caricata (no context creation per health check) |

### Endpoints

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/health` | Stato servizio + VRAM (zero GPU se idle) |
| POST | `/generate` | Generazione 3D da testo o immagine → GLB |
| POST | `/unload` | Scarica modello TRELLIS da VRAM |
| POST | `/load` | Carica/switcha modello TRELLIS |
| GET | `/models/{name}` | Download file GLB generato |

---

## 8. Configurazione OMNIA

### config/default.yaml

```yaml
trellis:
  enabled: true
  trellis_dir: ""                               # vuoto = auto-detect (../TRELLIS-for-windows)
  service_url: "http://localhost:8090"
  trellis_model: "JeffreyXiang/TRELLIS-text-large"
  auto_vram_swap: true                          # Unload LLM prima di generare, reload dopo
  request_timeout_s: 600                        # 10 min (prima generazione scarica pesi HF)
  max_model_size_mb: 10000
  model_output_dir: "data/3d_models"
  seed: -1                                      # -1 = random
```

### Plugin cad_generator

Il plugin `backend/plugins/cad_generator/` gestisce:
- **VRAM swap**: chiama `POST /api/v1/models/unload` su LM Studio prima della
  generazione, poi `POST /api/v1/models/load` dopo (polling 60s per reload)
- **Health check con TTL**: cache 30s per evitare richieste ripetute
- **Timeout chain**: `(request_timeout_s + 30) * 1000` ms per accomodare download modello
- **Format LM Studio v1 API**: body `{"id": "<instance_id>"}` per unload

### Frontend CADViewer

`CADViewer.vue` è il viewer Three.js con:
- GLTFLoader per file `.glb`
- OrbitControls (drag/scroll/pinch)
- Toolbar: auto-rotate, wireframe, reset camera, download
- Stile visivo coerente con il tema OMNIA (charcoal scuro + cream accent)
- Auto-fit camera al bounding box del modello
- Cleanup completo risorse GPU on unmount

---

## 9. Avvio e test

```powershell
# 1. Avvia LM Studio (deve essere già running con un modello caricato)

# 2. Avvia TRELLIS microservice
cd C:\Users\Jays\Desktop\omnia\omnia
.\scripts\start-trellis.ps1

# 3. Avvia backend OMNIA (in un altro terminale)
& ".\backend\.venv\Scripts\python.exe" -m uvicorn backend.core.app:create_app --factory --reload --reload-dir backend --host 0.0.0.0 --port 8000

# 4. Avvia frontend Electron
cd frontend && npm run dev
```

### Test manuale

Nella chat OMNIA, scrivi:
```
Genera un modello 3D di una tazza di ceramica
```

Il flusso atteso:
1. LLM riceve la richiesta e invoca `cad_generate(description="ceramic mug")`
2. Plugin scarica LLM da VRAM (`auto_vram_swap: true`)
3. Plugin chiama TRELLIS `/generate` con il prompt
4. TRELLIS carica il modello, genera GLB (~60-90s)
5. Plugin ricarica LLM
6. Modello `.glb` mostrato nel CADViewer inline nella chat

### Test API diretto

```powershell
# Health check
Invoke-RestMethod http://localhost:8090/health

# Generazione diretta
$body = @{ prompt = "a simple red cube"; output_name = "test_cube" }
Invoke-WebRequest -Uri http://localhost:8090/generate -Method POST `
    -ContentType "application/x-www-form-urlencoded" `
    -Body "prompt=a simple red cube&output_name=test_cube"
```

---

## 10. Problemi risolti (changelog)

Elenco completo di tutti i problemi incontrati e risolti per far funzionare
TRELLIS su RTX 5080 Blackwell (sm_120) con Windows + CUDA 12.8 + VS 2025.

### 10.1 — PyTorch cu124 non supporta Blackwell

**Sintomo:** `CUDA error: no kernel image is available for execution on the device`
**Causa:** torch 2.5.1+cu124 non include kernel per sm_120 (Blackwell)
**Fix:** Upgrade a torch 2.7.0+cu128 + torchvision 0.22.0+cu128

### 10.2 — flash-attn wheel incompatibile

**Sintomo:** `ImportError: DLL load failed` per flash_attn
**Causa:** La wheel originale era per cu124 + torch 2.5.1
**Fix:** Wheel precompilata da kingbri1: `flash_attn-2.8.3+cu128torch2.7.0`

### 10.3 — HuggingFace model name errato

**Sintomo:** `404 Not Found` al download dei pesi
**Causa:** Nome modello con typo o path errato
**Fix:** Nome corretto: `JeffreyXiang/TRELLIS-text-large`

### 10.4 — Estensioni CUDA ABI mismatch

**Sintomo:** `undefined symbol: _ZN2at4_ops...` all'import delle estensioni
**Causa:** Le wheel pre-built erano compilate per torch 2.5.1+cu124 ABI;
torch 2.7.0 ha ABI diversa
**Fix:** Ricompilazione da sorgente di tutte e 3 le estensioni con
`TORCH_CUDA_ARCH_LIST=12.0` (vedi [sezione 5](#5-ricompilazione-estensioni-cuda-da-sorgente))

### 10.5 — ninja non trovato nel PATH

**Sintomo:** `RuntimeError: Ninja is required to load C++ extensions`
(durante JIT di nvdiffrast)
**Causa:** `ninja.exe` installato nel venv `Scripts/` ma non nel PATH del processo
**Fix:** `server.py` aggiunge `sys.executable/../` al PATH all'avvio

### 10.6 — CUDA_HOME non impostato

**Sintomo:** `nvcc not found` durante compilazione JIT di nvdiffrast
**Causa:** CUDA_HOME non impostato nell'ambiente
**Fix:** `server.py` auto-detect: cerca in `C:\...\CUDA\` e prende la versione
più recente con `nvcc.exe`

### 10.7 — host_config.h rifiuta MSVC 19.50 (VS 2025)

**Sintomo:** `fatal error C1189: unsupported Microsoft Visual Studio version`
**Causa:** CUDA 12.8 `host_config.h` ha un check `_MSC_VER >= 1950` che blocca VS 2025
**Fix:** Patch manuale del check a `>= 2000` (vedi [sezione 6](#6-patch-host_configh-per-vs-2025-msvc-1950))

### 10.8 — Import torch a livello modulo (VRAM sprecata)

**Sintomo:** TRELLIS server occupa ~500MB VRAM anche quando idle
**Causa:** `import torch` a livello modulo crea un CUDA context permanente
**Fix:** Riscrittura `server.py` con import differiti — torch importato solo
in `_load_pipeline()` e `_unload_pipeline()`

### 10.9 — Timeout troppo brevi

**Sintomo:** `httpx.ReadTimeout` dopo 30s durante la prima generazione
**Causa:** Prima generazione scarica pesi HF (~4GB) + compila kernel, richiede minuti
**Fix:** Timeout chain: `request_timeout_s: 600` in config → client usa
`(600 + 30) * 1000` ms; server non ha timeout interno

### 10.10 — Formato API VRAM swap errato

**Sintomo:** `422 Unprocessable Entity` su LM Studio `/api/v1/models/unload`
**Causa:** Plugin mandava `{"model": "..."}` ma LM Studio v1 API vuole `{"id": "..."}`
(instance ID, non model name)
**Fix:** Plugin ora recupera `instance_id` da `GET /api/v1/models` e manda
`{"id": "<instance_id>"}` per unload

### 10.11 — Port check false positive

**Sintomo:** Script `start-trellis.ps1` dice "port 8090 already in use" anche
quando nessun server è attivo
**Causa:** Connessioni TCP in stato `TIME_WAIT`/`CLOSE_WAIT` (PID=0, kernel)
venivano contate come "in uso"
**Fix:** Filtro: solo `State -eq "Listen"` o `OwningProcess -gt 0 and Established`

### 10.12 — CADViewer scompare dopo streaming

**Sintomo:** Il viewer 3D appare durante l'esecuzione del tool ma scompare
quando la risposta dell'LLM termina
**Causa:** `CADViewer` era solo in `ToolExecutionIndicator` (dentro `StreamingIndicator`),
che viene smontato quando lo streaming finisce. `finalizeStream()` pulisce
`activeToolExecutions` e `loadConversation()` ricarica i messaggi persistiti.
**Fix:** Aggiunto rendering `CADViewer` in `MessageBubble.vue` per messaggi
`role: 'tool'` persistiti con payload CAD JSON (`model_name` + `export_url`).

### 10.13 — spconv-cu128 non esiste

**Sintomo:** `pip install spconv-cu128` fallisce
**Causa:** Il pacchetto spconv pubblica solo cu120 e cu126
**Fix:** `spconv-cu126` funziona correttamente con CUDA 12.8 (compatibilità forward)

### 10.14 — numba incompatibile

**Sintomo:** `ImportError` per numba con numpy mismatch
**Causa:** numba 0.60 non supporta la versione numpy richiesta da torch 2.7
**Fix:** `numba>=0.62.0` (testato con 0.64.0)
