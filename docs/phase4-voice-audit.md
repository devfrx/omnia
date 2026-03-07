# Phase 4 Voice — Audit Report

> Data: 2026-03-07
> Agenti impiegati: 9 subagent specializzati (backend×3, frontend, test, reviewer, refactor, debugger, build)
> Scope: Tutte le modifiche e aggiunte della Fase 4 del PROJECT.md

---

## CRITICAL (6) — Da fixare subito

### C1 — STT model non thread-safe per transcription concorrente
- **File:** `backend/services/stt_service.py`
- **Problema:** Due chiamate `transcribe()` concorrenti (2 WS client) invocano `_model.transcribe()` in thread separati senza alcun lock di inferenza. `WhisperModel` di faster-whisper condivide stato CUDA internamente — crash garantito sotto load concorrente.
- **Fix:** Aggiungere un `asyncio.Lock` (o `threading.Lock`) per serializzare l'accesso al modello durante la transcription.

### C2 — TTS `synthesize_stream` crash se `stop()` chiamato mid-stream
- **File:** `backend/services/tts_service.py`
- **Problema:** `synthesize_stream` controlla `self._engine is None` solo all'inizio. Se `stop()` viene chiamato da un'altra coroutine durante l'iterazione delle frasi, `self._engine` diventa `None` → `AttributeError: 'NoneType' object has no attribute 'synthesize'`.
- **Fix:** Catturare `self._engine` in una variabile locale all'inizio del metodo e usarla per tutta la durata.

### C3 — Frontend: transcript non pulito dopo auto-send
- **File:** `frontend/src/renderer/src/composables/useVoice.ts` + `frontend/src/renderer/src/views/ChatView.vue`
- **Problema:** Il `watch(transcript)` in ChatView auto-invia il testo alla chat ma non chiama `clearTranscript()`. Frasi ripetute non triggerano il watch (stesso valore, Vue skippa).
- **Fix:** Dopo l'invio, chiamare `store.clearTranscript()` o resettare il ref.

### C4 — Frontend: `playbackCtx` AudioContext mai chiuso — resource leak
- **File:** `frontend/src/renderer/src/composables/useVoice.ts`
- **Problema:** L'`AudioContext` per TTS playback viene creato al primo chunk ma mai chiuso — né in `cleanupAudioResources()`, né in `disconnect()`, né in `onScopeDispose`. I browser limitano a ~6-8 istanze; dopo diverse sessioni il TTS smette di funzionare.
- **Fix:** Aggiungere `playbackCtx.close(); playbackCtx = null` in `disconnect()` e cleanup.

### C5 — Frontend: `startRecordingTimer()` mai chiamato
- **File:** `frontend/src/renderer/src/stores/voice.ts` + `frontend/src/renderer/src/composables/useVoice.ts`
- **Problema:** L'azione `startRecordingTimer()` è definita nello store ma mai invocata. `recordingDuration` è sempre 0. Il timer viene solo stoppato, mai avviato.
- **Fix:** Chiamare `store.startRecordingTimer()` in `startListening()` dopo aver settato `isListening = true`.

### C6 — Test Phase 4: 34/60 test FALLISCONO per patch target errati
- **File:** `backend/tests/test_stt_service.py`, `backend/tests/test_tts_service.py`, `backend/tests/test_vram_monitor.py`, `backend/tests/test_voice_tool_calling.py`
- **Problema:**
  - STT: `@patch("backend.services.stt_service.WhisperModel")` → `WhisperModel` è importato solo sotto `TYPE_CHECKING`, non esiste a runtime sul modulo. Inoltre `_create_model()` fa `from faster_whisper import WhisperModel` (local import).
  - TTS: `@patch("backend.services.tts_service.PiperVoice")` → import locale dentro il costruttore engine.
  - VRAM: `@patch("backend.services.vram_monitor.pynvml")` → il modulo usa `import pynvml as _pynvml`.
  - Voice tool calling: 15 test testano solo mock, zero codice di produzione.
- **Fix:** Correggere tutti i patch target e ristrutturare i test per testare codice reale.

---

## MAJOR (18) — Da pianificare

### M1 — STT: `_validate_audio` usa costanti hardcoded, ignora config
- **File:** `backend/services/stt_service.py`
- **Problema:** `MAX_AUDIO_SIZE_BYTES` è una costante module-level (50 MB). `STTConfig` ha `max_audio_size_mb` configurabile, ma `_validate_audio` è `@staticmethod` e non legge la config.
- **Fix:** Rendere `_validate_audio` un metodo d'istanza e usare `self._config.max_audio_size_mb`.

### M2 — STT: `MAX_AUDIO_DURATION_S` definita ma mai controllata
- **File:** `backend/services/stt_service.py`
- **Problema:** La costante esiste e la config ha `max_audio_duration_s = 300`, ma nessun codice controlla la durata effettiva dell'audio.
- **Fix:** Aggiungere check durata in `_validate_audio` leggendo header WAV o usando la config.

### M3 — STT: `avg_logprob` esposto come "confidence" (range errato)
- **File:** `backend/services/stt_service.py`
- **Problema:** `avg_logprob` di faster-whisper è un log-probability negativo (tipicamente -0.1 a -1.5). Il campo `confidence` viene esposto raw. Frontend e test si aspettano range [0, 1].
- **Fix:** Convertire con `math.exp(avg_logprob)` che mappa a range ~0.2-0.9.

### M4 — STT: `_invalidate_model` non thread-safe
- **File:** `backend/services/stt_service.py`
- **Problema:** `_invalidate_model` setta `self._model = None` senza sincronizzazione. Una transcription in corso in un worker thread potrebbe accedere a `self._model` dopo l'invalidazione.
- **Fix:** In `_transcribe_sync`, catturare `model = self._model` in variabile locale all'inizio.

### M5 — TTS: nessun fallback XTTS → Piper
- **File:** `backend/services/tts_service.py`
- **Problema:** Se `engine == "xtts"` e il caricamento fallisce, il servizio resta morto. Lo spec prevede fallback a Piper.
- **Fix:** In `start()`, se XTTS fallisce, tentare caricamento Piper come fallback.

### M6 — TTS: `speed` config definito ma mai usato
- **File:** `backend/services/tts_service.py`
- **Problema:** `TTSConfig.speed` esiste (default 1.0) ma nessun engine lo passa alla sintesi. Piper supporta `length_scale`, XTTS supporta `speed`.
- **Fix:** Passare `speed` / `length_scale` ai rispettivi engine.

### M7 — TTS: Piper voice path non risolto relativo a project root
- **File:** `backend/services/tts_service.py`
- **Problema:** `model_path` è costruito come `voice + ".onnx"` (path relativo). Se il backend è lanciato da una directory diversa, il modello non viene trovato.
- **Fix:** Risolvere il path relativo alla root del progetto.

### M8 — VRAM: `get_usage()` crash senza GPU
- **File:** `backend/services/vram_monitor.py`
- **Problema:** `get_usage()` è pubblico ma non ha guard per `self._available`. Su sistemi senza GPU, `_read_vram_nvidia_smi` lancia `CalledProcessError`.
- **Fix:** Check `self._available` all'inizio di `get_usage()`.

### M9 — VRAM: nessun handler iscritto agli eventi warning/critical
- **File:** `backend/services/vram_monitor.py` + `backend/core/app.py`
- **Problema:** Il monitor emette `VRAM_WARNING` e `VRAM_CRITICAL` ma nessun subscriber reagisce. Lo spec richiede: STT downscale, XTTS→Piper fallback.
- **Fix:** Registrare handler in `app.py` che delegano a STT/TTS service per degradazione.

### M10 — Voice endpoint: nessuna integrazione voice → LLM → tool loop → TTS
- **File:** `backend/api/routes/voice.py`
- **Problema:** Il voice endpoint restituisce solo il transcript al client. Non c'è pipeline server-side voice→LLM→tool→TTS come da spec 4.5.
- **Fix:** Dopo la transcription, invocare il tool loop LLM e streamare la risposta TTS.

### M11 — Voice endpoint: nessun flusso di conferma vocale per tool
- **File:** `backend/api/routes/voice.py`
- **Problema:** Spec richiede: per tool con `requires_confirmation`, sintetizzare domanda TTS + attendere risposta voice "sì/no". Non implementato.
- **Fix:** Aggiungere flusso di conferma vocale integrato con TTS+STT.

### M12 — Frontend: 4 componenti voice sono dead code
- **Files:** `VoiceIndicator.vue`, `TranscriptOverlay.vue`, `AudioPlayback.vue`, `VoiceSettings.vue`
- **Problema:** Componenti implementati ma mai importati o renderizzati da nessun parent.
- **Fix:** Integrarli nei componenti parent appropriati (ChatView, sidebar, etc.).

### M13 — Frontend: `sendBinary()` senza backpressure
- **File:** `frontend/src/renderer/src/services/ws.ts`
- **Problema:** `send()` controlla `bufferedAmount` e accoda, ma `sendBinary()` invia direttamente senza check. A 16kHz il mic genera ~32KB/s, su connessione lenta il buffer cresce senza limiti.
- **Fix:** Aggiungere check `bufferedAmount` in `sendBinary()`, drop frame se buffer pieno.

### M14 — Frontend: `VoiceStartMessage` type manca `sample_rate`
- **File:** `frontend/src/renderer/src/types/voice.ts`
- **Problema:** Il tipo è `{ type: 'voice_start' }` ma il payload reale include `sample_rate: number`.
- **Fix:** Aggiungere `sample_rate?: number` al tipo.

### M15 — Frontend: `store.micPermission` mai sincronizzato
- **File:** `frontend/src/renderer/src/composables/useVoice.ts` + `frontend/src/renderer/src/stores/voice.ts`
- **Problema:** Il composable mantiene `micPermission` locale e non lo propaga allo store. Lo store resta sempre `'prompt'`.
- **Fix:** Sincronizzare `store.micPermission` dal composable.

### M16 — Costanti audio duplicate in 3 file
- **Files:** `backend/services/stt_service.py`, `backend/services/audio_utils.py`, `backend/api/routes/voice.py`
- **Problema:** `MAX_AUDIO_SIZE`, `MAX_DURATION`, magic bytes definiti in 3 posti diversi con gli stessi valori.
- **Fix:** Consolidare in `audio_utils.py` e importare ovunque.

### M17 — File troppo lunghi (stt_service ~376 righe, useVoice ~430 righe)
- **Files:** `backend/services/stt_service.py`, `frontend/src/renderer/src/composables/useVoice.ts`
- **Problema:** Superano il limite di ~200 righe/file del progetto.
- **Fix:** STT: estrarre DLL registration in `cuda_dll_loader.py`. useVoice: estrarre audio capture e TTS playback in composable separati.

### M18 — Frontend: URL WebSocket hardcoded
- **File:** `frontend/src/renderer/src/composables/useVoice.ts`
- **Problema:** `ws://localhost:8000/api/voice/ws/voice` hardcoded. Non configurabile.
- **Fix:** Usare la stessa derivazione base URL del chat WebSocket.

---

## MINOR (20+)

### m1 — `protocols.py`: `synthesize_stream` dichiarato `def` ma implementato `async def`
- **File:** `backend/core/protocols.py`
- **Fix:** Cambiare la firma del protocollo a `async def synthesize_stream`.

### m2 — `voice.py`: nessuna emissione EventBus per voice lifecycle events
- **File:** `backend/api/routes/voice.py`
- **Fix:** Emettere `VOICE_SESSION_START/END`, `STT_STARTED/STOPPED/ERROR` dove appropriato.

### m3 — `voice.py`: `sample_rate` non validato per tipo
- **File:** `backend/api/routes/voice.py`
- **Fix:** Wrappare `int(data.get("sample_rate", 16000))` in try/except.

### m4 — `voice.py`: nessun `recording_stopped` event su path di successo
- **File:** `backend/api/routes/voice.py`
- **Fix:** Inviare `recording_stopped` anche quando c'è audio (prima di `stt_processing`).

### m5 — `voice.py`: `_voice_connections` defaultdict crea phantom entries
- **File:** `backend/api/routes/voice.py`
- **Fix:** Usare `.get(client_ip, 0)` invece di accesso diretto.

### m6 — `vram_monitor.py`: `_read_vram_nvidia_smi` non gestisce multi-GPU
- **File:** `backend/services/vram_monitor.py`
- **Fix:** Usare `--id=0` nel comando nvidia-smi o renderlo configurabile.

### m7 — `vram_monitor.py`: nessuna de-duplicazione eventi nel poll loop
- **File:** `backend/services/vram_monitor.py`
- **Fix:** Aggiungere flag `_already_warned`/`_already_critical` per evitare flooding.

### m8 — `tts_service.py`: sentence splitter rompe abbreviazioni italiane
- **File:** `backend/services/tts_service.py`
- **Fix:** Migliorare regex per gestire "Dott.", "Sig.", "Prof.", numeri decimali, etc.

### m9 — `tts_service.py`: `_XTTSEngine` non valida `speaker_wav` a startup
- **File:** `backend/services/tts_service.py`
- **Fix:** Validare path in `__init__` e loggare warning se vuoto o inesistente.

### m10 — `tts_service.py`: stdlib imports dentro method body
- **File:** `backend/services/tts_service.py`
- **Fix:** Spostare `import tempfile, pathlib, os` a module-level.

### m11 — `useVoice.ts`: `playNextChunk` catch silenzioso + ricorsione stretta
- **File:** `frontend/src/renderer/src/composables/useVoice.ts`
- **Fix:** Aggiungere `console.warn` e usare `setTimeout(() => playNextChunk(), 0)`.

### m12 — `useVoice.ts`: module-level `voiceWs` singleton — rischio handler duplicati
- **File:** `frontend/src/renderer/src/composables/useVoice.ts`
- **Fix:** Aggiungere flag di inizializzazione per prevenire handler duplicati.

### m13 — `useVoice.ts`: TTS sample rate hardcoded `22050`
- **File:** `frontend/src/renderer/src/composables/useVoice.ts`
- **Fix:** Leggere sample rate dal messaggio `voice_ready` o `tts_start` del backend.

### m14 — `useVoice.ts`: PCM frame logging verboso in produzione
- **File:** `frontend/src/renderer/src/composables/useVoice.ts`
- **Fix:** Gating dietro flag debug o rimuovere.

### m15 — `voice.ts`: `STTResult.isFinal` definito ma mai inviato dal backend
- **File:** `frontend/src/renderer/src/types/voice.ts`
- **Fix:** Rimuovere `isFinal` dal tipo o farlo inviare dal backend.

### m16 — `voice.ts`: `STTResult.confidence` documentato "0-1" ma riceve log-prob negativi
- **File:** `frontend/src/renderer/src/types/voice.ts`
- **Fix:** Aggiornare documentazione dopo fix M3 backend.

### m17 — `config.py`: `STTConfig.model` default `"large-v3"` vs YAML `"small"` — mismatch
- **File:** `backend/core/config.py`
- **Fix:** Allineare default Pydantic a `"small"`.

### m18 — `pyproject.toml`: `sounddevice` dead dependency
- **File:** `backend/pyproject.toml`
- **Fix:** Rimuovere da optional deps.

### m19 — `pyproject.toml`: nessun upper bound su `faster-whisper`, `nvidia-*`
- **File:** `backend/pyproject.toml`
- **Fix:** Aggiungere upper bounds (`<2`, `<13`, `<10`).

### m20 — `pyproject.toml`: `[voice]` group forza CUDA su macchine CPU-only
- **File:** `backend/pyproject.toml`
- **Fix:** Separare in `voice` (CPU) e `voice-gpu` groups.

### m21 — `tts_service.py`: test expects `ValueError` per empty text, prod returns `b""`
- **File:** `backend/services/tts_service.py`
- **Fix:** Lanciare `ValueError` per testo vuoto (matching test contract).

### m22 — `tts_service.py`: nessun thread safety per engine concorrenti
- **File:** `backend/services/tts_service.py`
- **Fix:** Aggiungere `asyncio.Lock` o `threading.Lock` per serializzare synthesis.

### m23 — `voice.py`: `_cancel_tts` race condition con nuovo TTS task
- **File:** `backend/api/routes/voice.py`
- **Fix:** Attendere completamento cancellazione prima di avviare nuovo task.

### m24 — `app.py`: shutdown order — DB dispose prima di voice services
- **File:** `backend/core/app.py`
- **Fix:** Spostare voice service shutdown PRIMA di `engine.dispose()`.

---

## BUILD (2)

### B1 — PyInstaller: hook personalizzati necessari
- **Files:** `ctranslate2`, `piper-phonemize`, `nvidia.*`
- **Problema:** Richiedono hook PyInstaller custom per `hiddenimports` e `datas`/`binaries`.
- **Fix:** Creare hook scripts in `scripts/pyinstaller_hooks/`.

### B2 — PyInstaller: model files e CUDA DLLs
- **Files:** `models/tts/*.onnx`, Whisper models, NVIDIA DLLs
- **Problema:** Vanno inclusi come data files nel bundle PyInstaller.
- **Fix:** Documentare nel setup e aggiungere al `.spec` file.

---

## Riepilogo Numerico

| Severity | Count |
|----------|-------|
| CRITICAL | 6 |
| MAJOR | 18 |
| MINOR | 24 |
| BUILD | 2 |
| **TOTALE** | **50** |
