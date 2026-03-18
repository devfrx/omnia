<!-- ### Fase 6 — Plugin: Domotica / IoT

#### 6.1 — Home Assistant Client
- [ ] `HomeAssistantService`: singleton con persistent `httpx.AsyncClient` (connection pool, non nuova connessione per ogni tool call)
- [ ] REST API: `GET /api/states`, `POST /api/services/{domain}/{service}` con retry + backoff
- [ ] WebSocket HA: subscribe state changes (real-time device updates)
- [ ] **Credential management**: `SecretStr` per token HA; config attuale usa plaintext → migrare; ideale: OS keyring (`keyring` library)
- [ ] **Connectivity validation**: test connessione a startup, emit `plugin.status_changed` se offline
- [ ] **Rate limiting**: max 10 req/s verso HA API (evitare flood)

#### 6.2 — MQTT Client
- [ ] `MQTTService`: `paho-mqtt` con persistent connection + auto-reconnect (backoff esponenziale)
- [ ] **TLS obbligatorio di default**: porta 8883, verifica certificato, TLS 1.2+
- [ ] **Credenziali sicure**: `SecretStr` per password MQTT; no plaintext in config YAML
- [ ] **QoS 1** (at least once) per comandi dispositivi
- [ ] Background task per `loop_start()` — non bloccare event loop
- [ ] **Command validation whitelist**: solo comandi conosciuti per tipo dispositivo (light, switch, lock, climate, sensor)
- [ ] **IoT command sanitization**: no caratteri speciali (`;`, `|`, `&`, backtick) nei parametri

#### 6.3 — Device Registry
- [ ] DB model: `Device(id, name, device_type, area, capabilities, protocol, last_seen, state)`
- [ ] Sync automatico da Home Assistant → device registry locale
- [ ] Filtro per area/tipo → tool descriptions contestuali per LLM
- [ ] **Device access control**: lista dispositivi "protetti" non controllabili da LLM (es. serrature, telecamere di sicurezza, allarme)
- [ ] Config: `iot.protected_devices: list[str]` — nomi/ID dispositivi mai auto-controllabili

#### 6.4 — Event-Driven Updates
- [ ] **Unsolicited messages**: quando un dispositivo cambia stato, inviare al frontend:
  - `{"type": "iot_state_update", "device_id": "...", "new_state": "...", "changed_by": "external|omnia"}`
- [ ] **Notification vs message**: gli update IoT NON finiscono nella chat history; sono notifiche separate
- [ ] Frontend: notification toast per state changes (opzionale, configurabile per dispositivo)

#### 6.5 — Test Suite Fase 6
- [ ] Test HA client: mock httpx, autenticazione, retry su errore, rate limiting
- [ ] Test MQTT: mock paho-mqtt, TLS, reconnect, QoS
- [ ] Test command validation: whitelist, sanitization, device access control
- [ ] Test device registry: sync, filtro, dispositivi protetti

--- -->

