### Fase 15 — Email Assistant (IMAP/SMTP locale)

> **Obiettivo**: aggiungere a AL\CE un assistente email locale che usa IMAP/SMTP
> per leggere, cercare, rispondere e inviare email senza dipendenze da API cloud.
> L'LLM elabora contenuto e bozze; le credenziali rimangono esclusivamente locali
> (OS keyring o env var). Con Fase 15 AL\CE diventa anche un hub di comunicazione
> personale locale-first.

- [x] §15.1 `EmailConfig` in `config.py` + `default.yaml`
- [x] §15.2 `EmailServiceProtocol` in `protocols.py`
- [x] §15.3 `AppContext.email_service` field + `AliceEvent.EMAIL_*`
- [x] §15.4 `EmailService` (`aioimaplib` + `aiosmtplib` + cache in-memory)
- [x] §15.5 App lifespan wiring (startup init + shutdown close)
- [x] §15.6 `EmailPlugin` (6 tool LLM)
- [x] §15.7 REST API `/api/email` (6 endpoint)
- [x] §15.8 System prompt aggiornato
- [x] §15.9 Frontend: `types/email.ts` + `stores/email.ts` + `EmailPageView.vue` + componenti
- [x] §15.10 Dipendenze (`aioimaplib`, `aiosmtplib`, `keyring`)
- [x] §15.11 Struttura file
- [x] §15.12 Test suite (3 file, 30+ test case)
- [x] §15.13 Ordine di implementazione
- [x] §15.14 Verifiche

---

#### 15.0 — Analisi Vincoli e Scelte Architetturali

**Perché `EmailService` è un `BaseService` nell'AppContext e NON un plugin standalone:**
- Il service gestisce connessioni IMAP/SMTP persistenti con lifecycle (connect/disconnect)
  e un background task per IMAP IDLE — esattamente come `NoteService` o `MemoryService`
- Il plugin `email_assistant` delega tutta la logica di I/O a `ctx.email_service`,
  esponendo solo il layer tool LLM senza conoscere socket o protocolli
- Separazione responsabilità pulita: service = connessione + cache, plugin = tool calls

**Perché NO a un database SQLite dedicato:**
- A differenza di `NoteService` (storage permanente) e `MemoryService` (vettori coseno),
  le email risiedono sul server IMAP — non occorre duplicarle localmente
- Il service usa una **cache in-memory LRU-TTL** per intestazioni e corpi recenti
  (evita round-trip IMAP ripetuti) e un **contatore in-memory** per il rate-limit invii
- Zero migration, zero DDL extra, zero file `data/email.db`

**Perché `keyring` per le credenziali:**
- L'idea portante della feature è "credenziali mai in plaintext in `default.yaml`"
- `keyring` usa Windows Credential Manager (o macOS Keychain, Linux Secret Service)
  per archiviare la password in modo sicuro e recuperarla a runtime
- Flusso: `EmailService.initialize()` chiama `keyring.get_password("alice", email_username)`
  se `use_keyring=True`; fallback a `SecretStr` dal config (impostabile via env var
  `ALICE_EMAIL__PASSWORD`) se `use_keyring=False`
- La password non viene mai inclusa nei log (`SecretStr` non è serializzabile come str
  dalla loguru formatter standard — `logger.info("cfg={}", cfg)` stampa `'**'`)

**Perché `aioimaplib` + `aiosmtplib` e non librerie sync:**
- Tutto I/O in AL\CE è async-first — regola di progetto
- `aioimaplib` supporta IMAP4 SSL nativo + IDLE (push di nuove email senza polling)
- `aiosmtplib` è il wrapper async di `smtplib` stdlib — STARTTLS, SSL, App Password

**HTML sanitizzazione (anti prompt injection via email):**
- Prima di passare il body email all'LLM: strip HTML completo via `bs4.get_text(separator=" ")`
  (`beautifulsoup4` già in pyproject.toml)
- `max_email_body_chars` (default 8000) tronca i body lunghi — anti-flooding del context
- Solo testo plain viene incluso nei tool result dell'LLM

**`send_email`: `risk_level="dangerous"`, `requires_confirmation=True`:**
- Inviare email è irreversibile — l'utente deve sempre confermare esplicitamente
- Rate limit lato service: contatore in-memory max N invii/ora (default 10)
- `allowed_recipients: list[str]` opzionale: se non vuoto, l'invio a indirizzi non nella
  whitelist è bloccato a livello di service (anti-exfiltration)

**IMAP IDLE — background watcher:**
- Se `imap_idle_enabled=True`, `EmailService.initialize()` avvia un task asyncio
  `_idle_watcher_task` che mantiene l'IDLE IMAP attivo e, alla ricezione di un EXISTS
  notification, emette `AliceEvent.EMAIL_RECEIVED` → il gateway WebSocket
  lo forwardata come `{ "type": "email.received", "folder": "INBOX" }` a tutti i client
- Identico al pattern `TimerManager` (Fase 7.5.2) e `asyncio.create_task()` in
  `MemoryService`

**Perché nessuna VRAM e nessun embedding:**
- L'assistente email non usa ricerca semantica — le query di ricerca vengono tradotte
  in criteri IMAP standard (FROM, SUBJECT, TEXT, SINCE, BEFORE)
- Zero dipendenza da LM Studio per embedding → il service funziona anche se l'LLM è
  offline (l'utente può comunque fare `read_emails` e `search_emails`)

---

#### 15.1 — `EmailConfig` (`backend/core/config.py`)

```python
# Aggiungere SecretStr all'import pydantic esistente in config.py:
# from pydantic import ..., SecretStr

class EmailConfig(BaseSettings):
    """Email assistant (IMAP / SMTP) configuration."""

    model_config = SettingsConfigDict(env_prefix="ALICE_EMAIL__")

    enabled: bool = False
    """Enable the email assistant. False by default (opt-in esplicito)."""

    imap_host: str = ""
    """IMAP server hostname (e.g. 'imap.gmail.com', 'imap.outlook.com')."""

    imap_port: int = 993
    """IMAP port. 993 = IMAPS (SSL), 143 = STARTTLS."""

    imap_ssl: bool = True
    """Use implicit SSL for IMAP (port 993). Set False for STARTTLS (port 143)."""

    smtp_host: str = ""
    """SMTP server hostname (e.g. 'smtp.gmail.com', 'smtp.office365.com')."""

    smtp_port: int = 587
    """SMTP port. 587 = STARTTLS, 465 = SSL, 25 = plain (not recommended)."""

    smtp_ssl: bool = False
    """Use implicit SSL for SMTP (port 465). False = STARTTLS (port 587)."""

    username: str = ""
    """Email address / login used for both IMAP and SMTP auth."""

    use_keyring: bool = True
    """Retrieve password from OS keyring instead of config.
    If True: keyring.get_password('alice', username) is called at startup.
    If False: falls back to the 'password' field below (env var recommended)."""

    password: SecretStr = Field(default=SecretStr(""))
    """Password or App Password. Used only when use_keyring=False.
    Set via env var ALICE_EMAIL__PASSWORD — never commit to default.yaml."""

    fetch_last_n: int = 20
    """Default number of emails fetched per inbox listing request."""

    max_fetch: int = 50
    """Hard cap on emails fetched in a single request (anti-flooding)."""

    max_email_body_chars: int = 8_000
    """Maximum characters of email body passed to the LLM (HTML stripped)."""

    cache_ttl_s: int = 300
    """TTL in seconds for in-memory email cache (headers + bodies)."""

    rate_limit_send_per_hour: int = 10
    """Maximum emails the LLM can send per rolling hour (anti-abuse)."""

    allowed_recipients: list[str] = Field(default_factory=list)
    """Whitelist of allowed recipient addresses. Empty list = no restriction."""

    imap_idle_enabled: bool = True
    """Enable IMAP IDLE for real-time new-email notifications."""

    connection_timeout_s: int = 30
    """Timeout in seconds for IMAP/SMTP connection establishment."""

    archive_folder: str = "Archive"
    """IMAP folder name used for archiving (Gmail uses '[Gmail]/All Mail')."""
```

Aggiunta a `AliceConfig` (dopo il campo `chart`):
```python
email: EmailConfig = Field(default_factory=EmailConfig)
```

---

#### 15.2 — `EmailServiceProtocol` (`backend/core/protocols.py`)

```python
# ---------------------------------------------------------------------------
# Email service
# ---------------------------------------------------------------------------


@runtime_checkable
class EmailServiceProtocol(Protocol):
    """Protocol for the async IMAP/SMTP email assistant service."""

    async def initialize(self) -> None:
        """Connect to IMAP, load credentials, start IDLE watcher."""
        ...

    async def fetch_inbox(
        self,
        *,
        folder: str = "INBOX",
        limit: int = 20,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return a list of email header dicts, most recent first.

        Each dict: {uid, subject, from, to, date, is_read, has_attachments}.
        """
        ...

    async def fetch_email(
        self,
        uid: str,
        *,
        folder: str = "INBOX",
    ) -> dict[str, Any] | None:
        """Return the full email dict (headers + body_text + attachments list).

        body_text is HTML-stripped and truncated to max_email_body_chars.
        Returns None if UID not found.
        """
        ...

    async def search(
        self,
        query: str,
        *,
        folder: str = "INBOX",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search emails using IMAP SEARCH criteria.

        query is interpreted as an IMAP search string
        (e.g. 'SUBJECT "fattura" FROM "amazon"').
        Returns header dicts sorted by date descending.
        """
        ...

    async def send(
        self,
        to: list[str],
        subject: str,
        body: str,
        *,
        reply_to_uid: str | None = None,
        folder: str = "INBOX",
    ) -> dict[str, Any]:
        """Send an email via SMTP.

        Returns {'success': True, 'message_id': '...'} on success.
        """
        ...

    async def mark_read(
        self,
        uid: str,
        *,
        folder: str = "INBOX",
        read: bool = True,
    ) -> bool:
        """Set or clear the \\Seen IMAP flag. Returns True on success."""
        ...

    async def archive(
        self,
        uid: str,
        *,
        from_folder: str = "INBOX",
    ) -> bool:
        """Move email to the configured archive_folder. Returns True on success."""
        ...

    async def list_folders(self) -> list[str]:
        """Return available IMAP folder names."""
        ...

    async def close(self) -> None:
        """Cancel IDLE task, close IMAP connection."""
        ...
```

---

#### 15.3 — `AppContext` e `AliceEvent`

**`backend/core/context.py`** — aggiungere import e campo:
```python
from backend.core.protocols import (
    ...
    EmailServiceProtocol,   # aggiungere — alfabeticamente dopo ConversationFileManagerProtocol
)

@dataclass
class AppContext:
    ...
    # Inserire il campo email_service dopo note_service e prima di ws_connection_manager:
    email_service: EmailServiceProtocol | None = None
    """Async IMAP/SMTP email assistant service."""
```

**`backend/core/event_bus.py`** — aggiungere nel blocco `AliceEvent`:
```python
# -- Email Assistant (Phase 15) --
EMAIL_RECEIVED = "email.received"
EMAIL_SENT = "email.sent"
```

---

#### 15.4 — `EmailService` (`backend/services/email_service.py`)

**Ruolo**: layer di connessione IMAP/SMTP. Non conosce tool, LLM o plugin — solo I/O email.

```
EmailService
├── initialize()          — risolve password (keyring/config), connette IMAP, avvia IDLE
├── fetch_inbox()         — LIST/FETCH IMAP, popola cache
├── fetch_email(uid)      — FETCH IMAP full, strip HTML, tronca
├── search(query)         — IMAP SEARCH → UIDs → fetch headers
├── send(to, subject, ...) — SMTP STARTTLS, rate-limit check, whitelist check
├── mark_read(uid)        — IMAP STORE \Seen
├── archive(uid)          — IMAP COPY + STORE \Deleted → EXPUNGE
├── list_folders()        — IMAP LIST
└── close()               — cancella IDLE task, logout IMAP
```

```python
"""AL\CE — Async email service (IMAP read + SMTP send)."""

from __future__ import annotations

import asyncio
import email
import email.header
import email.utils
import html
import re
import time
import uuid
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aioimaplib
import aiosmtplib
from bs4 import BeautifulSoup
from loguru import logger

from backend.core.config import EmailConfig
from backend.core.event_bus import EventBus, AliceEvent

_TRUNCATION_SUFFIX = "\n[…troncato]"


class _LRUCache:
    """Minimal async-safe TTL cache (LRU eviction at max_size)."""

    def __init__(self, max_size: int = 200, ttl_s: int = 300) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size
        self._ttl = ttl_s

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if key not in self._store and len(self._store) >= self._max_size:
            oldest = min(self._store, key=lambda k: self._store[k][1])
            del self._store[oldest]
        self._store[key] = (value, time.monotonic())

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


class EmailService:
    """Async IMAP/SMTP service for reading and sending emails locally.

    Credentials are never stored in plaintext; they are retrieved from
    the OS keyring (``use_keyring=True``, default) or from the
    ``ALICE_EMAIL__PASSWORD`` environment variable (``use_keyring=False``).

    The service owns:
    - A persistent ``aioimaplib`` client for inbox operations
    - An ``aiosmtplib`` connection created per-send (stateless, avoids
      long-lived SMTP connections that many providers drop after 5 min)
    - An in-memory TTL cache for recently fetched headers and bodies
    - An ``asyncio.Task`` for IMAP IDLE when ``imap_idle_enabled=True``
    """

    def __init__(self, config: EmailConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus
        self._imap: aioimaplib.IMAP4_SSL | aioimaplib.IMAP4 | None = None
        self._password_resolved: str = ""
        self._cache = _LRUCache(max_size=200, ttl_s=config.cache_ttl_s)
        self._idle_task: asyncio.Task | None = None
        # Rolling send counter: list of monotonic timestamps of recent sends
        self._send_log: list[float] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Resolve credentials, connect IMAP, start IDLE watcher."""
        if not self._config.imap_host:
            raise RuntimeError(
                "email.imap_host is required — configure it in default.yaml"
            )

        # Resolve password
        self._password_resolved = await self._resolve_password()

        # Connect IMAP
        self._imap = await self._connect_imap()
        logger.info(
            "EmailService connected to {}:{} as {}",
            self._config.imap_host, self._config.imap_port, self._config.username,
        )

        # Start IMAP IDLE background watcher
        if self._config.imap_idle_enabled:
            self._idle_task = asyncio.create_task(
                self._idle_watcher(), name="email-idle-watcher"
            )

    async def close(self) -> None:
        """Cancel IDLE task and close IMAP connection."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
        if self._imap:
            try:
                await self._imap.logout()
            except Exception:
                pass
            self._imap = None
        self._cache.clear()
        logger.info("EmailService closed")

    # ------------------------------------------------------------------
    # IMAP operations
    # ------------------------------------------------------------------

    async def fetch_inbox(
        self,
        *,
        folder: str = "INBOX",
        limit: int = 20,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch and return email headers from the specified folder."""
        limit = min(limit, self._config.max_fetch)
        cache_key = f"inbox:{folder}:{limit}:{unread_only}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        imap = await self._get_imap()
        await imap.select(folder)
        criteria = "UNSEEN" if unread_only else "ALL"
        result, data = await imap.uid("SEARCH", None, criteria)
        uids = data[0].split() if result == "OK" and data and data[0] else []

        # Most recent N UIDs
        uids = uids[-limit:][::-1]

        headers = []
        for uid_bytes in uids:
            uid = uid_bytes.decode() if isinstance(uid_bytes, bytes) else uid_bytes
            hdr = await self._fetch_header(uid, folder)
            if hdr:
                headers.append(hdr)

        self._cache.set(cache_key, headers)
        return headers

    async def fetch_email(
        self, uid: str, *, folder: str = "INBOX",
    ) -> dict[str, Any] | None:
        """Fetch the full email (headers + plain-text body)."""
        cache_key = f"email:{folder}:{uid}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        imap = await self._get_imap()
        await imap.select(folder)
        result, data = await imap.uid("FETCH", uid, "(FLAGS RFC822)")
        if result != "OK" or not data or data[0] is None:
            return None

        raw = data[1] if len(data) > 1 else data[0]
        if isinstance(raw, (list, tuple)):
            raw = b"".join(chunk for chunk in raw if isinstance(chunk, bytes))

        result = self._parse_email(uid, raw)
        if result:
            self._cache.set(cache_key, result)
        return result

    async def search(
        self,
        query: str,
        *,
        folder: str = "INBOX",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search emails using IMAP SEARCH criteria.

        ``query`` must be a valid IMAP SEARCH expression,
        e.g. ``'SUBJECT "fattura" FROM "amazon"'``.
        The LLM is instructed to use standard IMAP keywords only.
        """
        limit = min(limit, self._config.max_fetch)
        imap = await self._get_imap()
        await imap.select(folder)

        # Safety: strip characters that could inject extra IMAP commands
        safe_query = re.sub(r"[^\w \"@.:\-]", "", query)

        result, data = await imap.uid("SEARCH", None, safe_query)
        uids = data[0].split() if result == "OK" and data and data[0] else []
        uids = uids[-limit:][::-1]

        headers = []
        for uid_bytes in uids:
            uid = uid_bytes.decode() if isinstance(uid_bytes, bytes) else uid_bytes
            hdr = await self._fetch_header(uid, folder)
            if hdr:
                headers.append(hdr)
        return headers

    async def send(
        self,
        to: list[str],
        subject: str,
        body: str,
        *,
        reply_to_uid: str | None = None,
        folder: str = "INBOX",
    ) -> dict[str, Any]:
        """Send an email via SMTP with STARTTLS.

        Checks rate limit and allowed_recipients whitelist before sending.
        Raises ValueError on policy violations, RuntimeError on SMTP failure.
        """
        # Rate limit check
        now = time.monotonic()
        self._send_log = [t for t in self._send_log if now - t < 3600]
        if len(self._send_log) >= self._config.rate_limit_send_per_hour:
            raise ValueError(
                f"Limite invii orari raggiunto ({self._config.rate_limit_send_per_hour}/ora). "
                "Riprova tra qualche minuto."
            )

        # Whitelist check
        if self._config.allowed_recipients:
            blocked = [r for r in to if r not in self._config.allowed_recipients]
            if blocked:
                raise ValueError(
                    f"Destinatari non nella whitelist: {', '.join(blocked)}. "
                    "Modifica email.allowed_recipients in default.yaml per abilitarli."
                )

        # Build message headers
        in_reply_to: str | None = None
        if reply_to_uid:
            original = await self.fetch_email(reply_to_uid, folder=folder)
            if original:
                in_reply_to = original.get("message_id")

        msg = MIMEMultipart("alternative")
        msg["From"] = self._config.username
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        message_id = f"<alice-{uuid.uuid4()}@{self._config.smtp_host}>"
        msg["Message-ID"] = message_id
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            smtp_kwargs: dict[str, Any] = dict(
                hostname=self._config.smtp_host,
                port=self._config.smtp_port,
                username=self._config.username,
                password=self._password_resolved,
                timeout=self._config.connection_timeout_s,
                use_tls=self._config.smtp_ssl,
                start_tls=not self._config.smtp_ssl,
            )
            await aiosmtplib.send(msg, **smtp_kwargs)
        except Exception as exc:
            raise RuntimeError(f"SMTP error: {exc}") from exc

        self._send_log.append(now)
        logger.info("Email inviata a {} — subject: {}", to, subject)
        await self._bus.emit(
            AliceEvent.EMAIL_SENT,
            to=to,
            subject=subject,
            message_id=message_id,
        )
        return {"success": True, "message_id": message_id}

    async def mark_read(
        self, uid: str, *, folder: str = "INBOX", read: bool = True,
    ) -> bool:
        """Set or clear the \\Seen flag."""
        imap = await self._get_imap()
        await imap.select(folder)
        flag_cmd = "+FLAGS" if read else "-FLAGS"
        result, _ = await imap.uid("STORE", uid, flag_cmd, "\\Seen")
        self._cache.invalidate(f"email:{folder}:{uid}")
        self._cache.invalidate(f"inbox:{folder}:{self._config.fetch_last_n}:False")
        self._cache.invalidate(f"inbox:{folder}:{self._config.fetch_last_n}:True")
        return result == "OK"

    async def archive(self, uid: str, *, from_folder: str = "INBOX") -> bool:
        """Copy email to archive folder then delete from source."""
        imap = await self._get_imap()
        await imap.select(from_folder)
        result, _ = await imap.uid("COPY", uid, self._config.archive_folder)
        if result != "OK":
            return False
        await imap.uid("STORE", uid, "+FLAGS", "\\Deleted")
        await imap.expunge()
        self._cache.invalidate(f"email:{from_folder}:{uid}")
        self._cache.invalidate(f"inbox:{from_folder}:{self._config.fetch_last_n}:False")
        return True

    async def list_folders(self) -> list[str]:
        """Return list of IMAP folder names."""
        imap = await self._get_imap()
        _, data = await imap.list()
        folders = []
        for line in data:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            # IMAP LIST response: (\HasNoChildren) "/" "INBOX"
            parts = line.rsplit('"', 2)
            if len(parts) >= 2:
                folders.append(parts[-1].strip().strip('"'))
        return [f for f in folders if f]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _resolve_password(self) -> str:
        """Retrieve password from keyring or config field."""
        if self._config.use_keyring:
            try:
                import keyring
                pwd = await asyncio.to_thread(
                    keyring.get_password, "alice", self._config.username
                )
                if pwd:
                    return pwd
                logger.warning(
                    "Password non trovata nel keyring per '{}'. "
                    "Esegui: keyring set alice {}",
                    self._config.username, self._config.username,
                )
            except ImportError:
                logger.warning(
                    "Libreria 'keyring' non installata — "
                    "fallback a email.password dal config"
                )
        return self._config.password.get_secret_value()

    async def _connect_imap(
        self,
    ) -> aioimaplib.IMAP4_SSL | aioimaplib.IMAP4:
        """Open and authenticate an IMAP connection."""
        if self._config.imap_ssl:
            imap = aioimaplib.IMAP4_SSL(
                host=self._config.imap_host,
                port=self._config.imap_port,
                timeout=self._config.connection_timeout_s,
            )
        else:
            imap = aioimaplib.IMAP4(
                host=self._config.imap_host,
                port=self._config.imap_port,
                timeout=self._config.connection_timeout_s,
            )
        await imap.wait_hello_from_server()
        if not self._config.imap_ssl:
            await imap.starttls()
        await imap.login(self._config.username, self._password_resolved)
        return imap

    async def _get_imap(self) -> aioimaplib.IMAP4_SSL | aioimaplib.IMAP4:
        """Return the active IMAP connection, reconnecting if needed."""
        if self._imap is None:
            self._imap = await self._connect_imap()
        return self._imap

    async def _fetch_header(
        self, uid: str, folder: str,
    ) -> dict[str, Any] | None:
        """Fetch envelope headers for one UID."""
        cache_key = f"hdr:{folder}:{uid}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        imap = await self._get_imap()
        result, data = await imap.uid("FETCH", uid, "(FLAGS RFC822.HEADER)")
        if result != "OK" or not data or data[0] is None:
            return None

        raw = data[1] if len(data) > 1 else data[0]
        if isinstance(raw, (list, tuple)):
            raw = b"".join(
                chunk for chunk in raw if isinstance(chunk, bytes)
            )

        msg = email.message_from_bytes(raw if isinstance(raw, bytes) else raw.encode())
        flags_raw = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
        is_read = "\\Seen" in flags_raw

        result = {
            "uid": uid,
            "subject": self._decode_header(msg.get("Subject", "")),
            "from": self._decode_header(msg.get("From", "")),
            "to": self._decode_header(msg.get("To", "")),
            "date": msg.get("Date", ""),
            "message_id": msg.get("Message-ID", ""),
            "is_read": is_read,
            "has_attachments": False,
        }
        self._cache.set(cache_key, result)
        return result

    def _parse_email(self, uid: str, raw: bytes) -> dict[str, Any]:
        """Parse a raw RFC822 email into a structured dict with plain-text body."""
        msg = email.message_from_bytes(raw)
        body = ""
        has_attachments = False

        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
                if "attachment" in disp:
                    has_attachments = True
                    continue
                if ct == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(
                        charset, errors="replace"
                    )
                    break
                if ct == "text/html" and not body:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = part.get_payload(decode=True).decode(
                        charset, errors="replace"
                    )
                    body = BeautifulSoup(html_body, "html.parser").get_text(
                        separator=" "
                    )
        else:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                ct = msg.get_content_type()
                raw_body = payload.decode(charset, errors="replace")
                if ct == "text/html":
                    body = BeautifulSoup(raw_body, "html.parser").get_text(
                        separator=" "
                    )
                else:
                    body = raw_body

        # Truncate and sanitize
        body = html.unescape(body).strip()
        if len(body) > self._config.max_email_body_chars:
            body = body[: self._config.max_email_body_chars] + _TRUNCATION_SUFFIX

        return {
            "uid": uid,
            "subject": self._decode_header(msg.get("Subject", "")),
            "from": self._decode_header(msg.get("From", "")),
            "to": self._decode_header(msg.get("To", "")),
            "cc": self._decode_header(msg.get("Cc", "")),
            "date": msg.get("Date", ""),
            "message_id": msg.get("Message-ID", ""),
            "body": body,
            "has_attachments": has_attachments,
        }

    @staticmethod
    def _decode_header(raw: str) -> str:
        """Decode RFC2047-encoded email header (e.g. =?UTF-8?…?)."""
        parts = email.header.decode_header(raw)
        decoded = []
        for part, enc in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    async def _idle_watcher(self) -> None:
        """Background task: keep IMAP IDLE active and emit EMAIL_RECEIVED on new mail."""
        while True:
            imap = None
            try:
                imap = await self._get_imap()
                await imap.select("INBOX")
                await imap.idle_start(timeout=28 * 60)  # 28 min keep-alive
                new_mail = False
                try:
                    # Wait for server push (new mail) or timeout (keepalive cycle)
                    await asyncio.wait_for(
                        imap.wait_server_push(), timeout=29 * 60
                    )
                    new_mail = True
                except asyncio.TimeoutError:
                    pass  # Normal keepalive cycle — not an error
                finally:
                    await imap.idle_done()

                if new_mail:
                    logger.debug("EMAIL_RECEIVED notification from IMAP IDLE")
                    await self._bus.emit(
                        AliceEvent.EMAIL_RECEIVED,
                        folder="INBOX",
                    )
                    # Invalidate inbox cache
                    self._cache.clear()
            except asyncio.CancelledError:
                if imap:
                    try:
                        await imap.idle_done()
                    except Exception:
                        pass
                return
            except Exception as exc:
                logger.warning("IMAP IDLE error (retrying in 60s): {}", exc)
                self._imap = None  # force reconnect
                await asyncio.sleep(60)
```

---

#### 15.5 — App Lifespan Wiring (`backend/core/app.py`)

**Startup** — aggiungere dopo il blocco `# -- Note service (Phase 13) --`:

```python
# -- Email service (Phase 15) ------------------------------------------
if config.email.enabled:
    from backend.services.email_service import EmailService

    email_service = EmailService(config.email, ctx.event_bus)
    try:
        await email_service.initialize()
        ctx.email_service = email_service
        logger.info("Email service started ({})", config.email.username)
    except Exception as exc:
        logger.warning("Email service failed to start: {}", exc)
        await email_service.close()
```

**Event forwarding** — aggiungere nel blocco dei forward MCP → WebSocket (dopo `_forward_mcp_disconnected`):

```python
async def _forward_email_received(**kwargs):
    if ctx.ws_connection_manager:
        await ctx.ws_connection_manager.broadcast({
            "type": "email.received",
            "folder": kwargs.get("folder", "INBOX"),
        })

async def _forward_email_sent(**kwargs):
    if ctx.ws_connection_manager:
        await ctx.ws_connection_manager.broadcast({
            "type": "email.sent",
            "message_id": kwargs.get("message_id"),
        })

ctx.event_bus.subscribe(AliceEvent.EMAIL_RECEIVED, _forward_email_received)
ctx.event_bus.subscribe(AliceEvent.EMAIL_SENT, _forward_email_sent)
```

**Shutdown** — aggiungere dopo il blocco `note_service`:

```python
if ctx.email_service:
    try:
        await ctx.email_service.close()
    except Exception as exc:
        logger.error("Email service shutdown error: {}", exc)
```

---

#### 15.6 — `EmailPlugin` (`backend/plugins/email_assistant/plugin.py`)

```python
"""AL\CE Email Assistant plugin — expose email tools to the LLM."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from backend.core.plugin_base import BasePlugin
from backend.core.plugin_models import ExecutionContext, ToolDefinition, ToolResult

if TYPE_CHECKING:
    from backend.core.context import AppContext

# JSON schema parameter blocks (abbreviated — see full definitions below)

_READ_EMAILS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "folder":      {"type": "string", "default": "INBOX",
                        "description": "IMAP folder name (default: INBOX)."},
        "limit":       {"type": "integer", "default": 20, "minimum": 1, "maximum": 50,
                        "description": "Number of emails to fetch (max 50)."},
        "unread_only": {"type": "boolean", "default": False,
                        "description": "If true, return only unread emails."},
    },
    "required": [],
}

_GET_EMAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "uid":    {"type": "string",
                   "description": "UID of the email to read (from read_emails list)."},
        "folder": {"type": "string", "default": "INBOX",
                   "description": "IMAP folder containing the email."},
    },
    "required": ["uid"],
}

_SEARCH_EMAILS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query":  {"type": "string",
                   "description": (
                       "IMAP SEARCH expression using standard keywords: "
                       "FROM, TO, SUBJECT, TEXT, SINCE, BEFORE, UNSEEN, SEEN. "
                       "Example: 'SUBJECT \"fattura\" FROM \"amazon.it\"'. "
                       "Use only alphanumeric characters and IMAP keywords."
                   )},
        "folder": {"type": "string", "default": "INBOX"},
        "limit":  {"type": "integer", "default": 20, "minimum": 1, "maximum": 50},
    },
    "required": ["query"],
}

_SEND_EMAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "to":           {"type": "array", "items": {"type": "string"},
                         "description": "List of recipient email addresses."},
        "subject":      {"type": "string", "description": "Email subject line."},
        "body":         {"type": "string",
                         "description": "Plain-text email body (no HTML)."},
        "reply_to_uid": {"type": "string",
                         "description": "UID of the email being replied to (optional). "
                                        "Sets In-Reply-To and References headers."},
        "folder":       {"type": "string", "default": "INBOX",
                         "description": "Folder containing the email being replied to."},
    },
    "required": ["to", "subject", "body"],
}

_MARK_READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "uid":    {"type": "string", "description": "Email UID to mark."},
        "folder": {"type": "string", "default": "INBOX"},
        "read":   {"type": "boolean", "default": True,
                   "description": "True = mark as read, False = mark as unread."},
    },
    "required": ["uid"],
}

_ARCHIVE_EMAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "uid":         {"type": "string", "description": "Email UID to archive."},
        "from_folder": {"type": "string", "default": "INBOX"},
    },
    "required": ["uid"],
}


class EmailPlugin(BasePlugin):
    """Plugin email — espone 6 tool LLM per gestire la posta elettronica.

    Si appoggia a ctx.email_service per tutta la logica I/O.
    Non importa socket né protocolli — solo delega al service.
    """

    plugin_name: str = "email_assistant"
    plugin_version: str = "1.0.0"
    plugin_description: str = "Leggi, cerca e invia email via IMAP/SMTP locale."
    plugin_dependencies: list[str] = []
    plugin_priority: int = 30

    def get_tools(self) -> list[ToolDefinition]:
        if not self.ctx.config.email.enabled:
            return []
        return [
            ToolDefinition(
                name="read_emails",
                description=(
                    "Elenca le email più recenti nella cartella specificata. "
                    "Restituisce una lista di intestazioni: uid, subject, from, to, date, is_read. "
                    "Usa uid per leggere il corpo completo con get_email."
                ),
                parameters=_READ_EMAILS_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=15_000,
            ),
            ToolDefinition(
                name="get_email",
                description=(
                    "Legge il corpo completo di una email dato l'uid. "
                    "Il corpo HTML è convertito automaticamente in testo plain. "
                    "Usa read_emails o search_emails per ottenere gli uid."
                ),
                parameters=_GET_EMAIL_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=15_000,
            ),
            ToolDefinition(
                name="search_emails",
                description=(
                    "Cerca email usando criteri IMAP standard (FROM, TO, SUBJECT, TEXT, "
                    "SINCE, BEFORE, UNSEEN, SEEN). "
                    "Restituisce le intestazioni delle email corrispondenti."
                ),
                parameters=_SEARCH_EMAILS_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=20_000,
            ),
            ToolDefinition(
                name="send_email",
                description=(
                    "Invia una email via SMTP. "
                    "Usa reply_to_uid per rispondere a una email esistente. "
                    "ATTENZIONE: operazione irreversibile — richiede conferma esplicita."
                ),
                parameters=_SEND_EMAIL_SCHEMA,
                risk_level="dangerous",
                requires_confirmation=True,
                timeout_ms=30_000,
            ),
            ToolDefinition(
                name="mark_as_read",
                description=(
                    "Segna una email come letta o non letta. "
                    "Usa read=false per marcarla come non letta."
                ),
                parameters=_MARK_READ_SCHEMA,
                risk_level="safe",
                requires_confirmation=False,
                timeout_ms=10_000,
            ),
            ToolDefinition(
                name="archive_email",
                description=(
                    "Sposta una email nella cartella di archivio configurata. "
                    "L'operazione rimuove l'email dalla cartella di origine. "
                    "Richiede conferma prima dell'esecuzione."
                ),
                parameters=_ARCHIVE_EMAIL_SCHEMA,
                risk_level="medium",
                requires_confirmation=True,
                timeout_ms=15_000,
            ),
        ]

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """Dispatch al metodo privato corrispondente."""
        if not self.ctx.config.email.enabled:
            return ToolResult.error("Plugin email_assistant non abilitato.")

        svc = self.ctx.email_service
        if svc is None:
            return ToolResult.error(
                "Email service non disponibile. Controlla la configurazione IMAP."
            )

        handlers = {
            "read_emails":   self._read_emails,
            "get_email":     self._get_email,
            "search_emails": self._search_emails,
            "send_email":    self._send_email,
            "mark_as_read":  self._mark_as_read,
            "archive_email": self._archive_email,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return ToolResult.error(f"Tool sconosciuto: {tool_name}")
        return await handler(args)

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _read_emails(self, args: dict[str, Any]) -> ToolResult:
        svc = self.ctx.email_service
        emails = await svc.fetch_inbox(
            folder=args.get("folder", "INBOX"),
            limit=int(args.get("limit", 20)),
            unread_only=bool(args.get("unread_only", False)),
        )
        return ToolResult.ok(json.dumps(emails, ensure_ascii=False, default=str))

    async def _get_email(self, args: dict[str, Any]) -> ToolResult:
        svc = self.ctx.email_service
        mail = await svc.fetch_email(
            args["uid"], folder=args.get("folder", "INBOX")
        )
        if mail is None:
            return ToolResult.error(f"Email non trovata: {args['uid']}")
        return ToolResult.ok(json.dumps(mail, ensure_ascii=False, default=str))

    async def _search_emails(self, args: dict[str, Any]) -> ToolResult:
        svc = self.ctx.email_service
        results = await svc.search(
            args["query"],
            folder=args.get("folder", "INBOX"),
            limit=int(args.get("limit", 20)),
        )
        return ToolResult.ok(json.dumps(results, ensure_ascii=False, default=str))

    async def _send_email(self, args: dict[str, Any]) -> ToolResult:
        svc = self.ctx.email_service
        try:
            result = await svc.send(
                to=args["to"],
                subject=args["subject"],
                body=args["body"],
                reply_to_uid=args.get("reply_to_uid"),
                folder=args.get("folder", "INBOX"),
            )
            return ToolResult.ok(json.dumps(result, ensure_ascii=False))
        except ValueError as exc:
            return ToolResult.error(str(exc))
        except RuntimeError as exc:
            self.logger.error("SMTP send failed: {}", exc)
            return ToolResult.error(f"Errore SMTP: {exc}")

    async def _mark_as_read(self, args: dict[str, Any]) -> ToolResult:
        svc = self.ctx.email_service
        ok = await svc.mark_read(
            args["uid"],
            folder=args.get("folder", "INBOX"),
            read=bool(args.get("read", True)),
        )
        status = "letta" if args.get("read", True) else "non letta"
        if ok:
            return ToolResult.ok(f"Email {args['uid']} marcata come {status}.")
        return ToolResult.error(f"Impossibile aggiornare email {args['uid']}.")

    async def _archive_email(self, args: dict[str, Any]) -> ToolResult:
        svc = self.ctx.email_service
        ok = await svc.archive(
            args["uid"],
            from_folder=args.get("from_folder", "INBOX"),
        )
        if ok:
            return ToolResult.ok(f"Email {args['uid']} archiviata.")
        return ToolResult.error(f"Impossibile archiviare email {args['uid']}.")


from backend.core.plugin_manager import PLUGIN_REGISTRY
PLUGIN_REGISTRY["email_assistant"] = EmailPlugin
```

**`backend/plugins/email_assistant/__init__.py`:**
```python
from backend.core.plugin_manager import PLUGIN_REGISTRY
from .plugin import EmailPlugin

PLUGIN_REGISTRY["email_assistant"] = EmailPlugin

__all__ = ["EmailPlugin"]
```

---

#### 15.7 — REST API `/api/email` (`backend/api/routes/email.py`)

**Ruolo**: proxy dal browser/frontend al service via AppContext.
Non espone la password né i segreti IMAP — solo ID e metadati.

```python
"""REST API per l'Email Assistant (lettura, ricerca, gestione)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/email", tags=["email"])


def _get_svc(request: Request):
    """Recupera EmailService dal contesto; 503 se non disponibile."""
    ctx = request.app.state.context
    if not ctx.config.email.enabled or ctx.email_service is None:
        raise HTTPException(status_code=503, detail="Email service non disponibile.")
    return ctx.email_service


# ── Inbox ──────────────────────────────────────────────────────────────────


@router.get("/inbox", summary="Lista email recenti")
async def get_inbox(
    request: Request,
    folder: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    """Restituisce le intestazioni delle email più recenti."""
    svc = _get_svc(request)
    return await svc.fetch_inbox(
        folder=folder,
        limit=min(limit, 50),
        unread_only=unread_only,
    )


@router.get("/{uid}", summary="Leggi email completa")
async def get_email(
    uid: str, request: Request, folder: str = "INBOX",
) -> dict[str, Any]:
    """Restituisce headers + body plain-text di una email."""
    svc = _get_svc(request)
    mail = await svc.fetch_email(uid, folder=folder)
    if mail is None:
        raise HTTPException(status_code=404, detail=f"Email non trovata: {uid}")
    return mail


# ── Search ─────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    folder: str = "INBOX"
    limit: int = 20


@router.post("/search", summary="Cerca email (IMAP SEARCH)")
async def search_emails(
    body: SearchRequest, request: Request,
) -> list[dict[str, Any]]:
    """Cerca email con criteri IMAP standard."""
    svc = _get_svc(request)
    return await svc.search(
        body.query, folder=body.folder, limit=min(body.limit, 50),
    )


# ── Actions ────────────────────────────────────────────────────────────────


@router.put("/{uid}/read", summary="Segna come letta/non letta")
async def mark_read(
    uid: str, request: Request, folder: str = "INBOX", read: bool = True,
) -> dict[str, bool]:
    """Imposta o rimuove il flag \\Seen."""
    svc = _get_svc(request)
    ok = await svc.mark_read(uid, folder=folder, read=read)
    if not ok:
        logger.warning("mark_read failed for uid={} folder={}", uid, folder)
        raise HTTPException(
            status_code=502, detail=f"Impossibile aggiornare flag per {uid}"
        )
    return {"success": True}


@router.put("/{uid}/archive", summary="Archivia email")
async def archive_email(
    uid: str, request: Request, from_folder: str = "INBOX",
) -> dict[str, bool]:
    """Sposta l'email nella cartella di archivio configurata."""
    svc = _get_svc(request)
    ok = await svc.archive(uid, from_folder=from_folder)
    if not ok:
        logger.warning("archive failed for uid={} from_folder={}", uid, from_folder)
        raise HTTPException(
            status_code=502, detail=f"Archiviazione fallita per {uid}"
        )
    return {"success": True}


# ── Folders moved to top of file (before /{uid}) ────────────────────────────────
```

**Registrazione in `backend/api/routes/__init__.py`** — aggiungere import e router:
```python
from backend.api.routes import (
    ..., email,   # aggiungere
)
router.include_router(email.router)
```

---

#### 15.8 — System Prompt (`config/system_prompt.md`)

Aggiungere sezione:

```yaml
email_assistant:
  principio: gestisci email tramite IMAP/SMTP locale — mai condividere credenziali o contenuto privato
  workflow_lettura:
    - "usa read_emails(limit=20) per ottenere la lista recente → restituisce uid, subject, from, date, is_read"
    - "usa get_email(uid) per leggere il corpo completo di un'email specifica"
    - "usa search_emails(query) con sintassi IMAP: 'SUBJECT \"fattura\"', 'FROM \"nome\"', 'SINCE 1-Jan-2025'"
  workflow_invio:
    - "redigi la bozza nel contesto, poi chiama send_email(to=[...], subject=..., body=...)"
    - "per rispondere a un'email usa send_email con il parametro reply_to_uid=<uid_originale>"
    - "send_email richiede conferma esplicita dell'utente — non inviare mai senza approvazione"
  workflow_gestione:
    - "usa mark_as_read(uid, read=true|false) per aggiornare lo stato letta/non letta di un'email"
    - "usa archive_email(uid) per spostare un'email nella cartella di archivio configurata"
    - "archive_email richiede conferma prima dell'esecuzione"
    - "le modifiche (flagging, archiviazione) sono riflesse immediatamente nella cache lato client"
  sicurezza:
    - "non includere mai password, token o credenziali nei tool call o nelle risposte"
    - "non estrarre né ripetere interi messaggi email privati fuori contesto"
    - "rispetta il limite di 10 invii/ora — avvisa l'utente se raggiunto"
  limiti:
    - "max 50 email per chiamata (usa offset logico con date SINCE/BEFORE se servono finestre)"
    - "corpo email troncato a 8000 caratteri — segnala se il messaggio era più lungo"
  gestione_errori:
    - "IMAP timeout o disconnect: comunica 'Connessione email temporaneamente non disponibile'"
    - "SMTP rifiuto: mostra il messaggio di errore SMTP per diagnostica"
```

---

#### 15.9 — Frontend

##### `frontend/src/renderer/src/types/email.ts` (nuovo file)

```typescript
/**
 * Email-related types aligned with EmailService REST API.
 * Mirrors the dict shapes returned by EmailService methods.
 */

/** Email header returned by GET /api/email/inbox and search. */
export interface EmailHeader {
  uid: string
  subject: string
  from: string
  to: string
  date: string
  message_id: string
  is_read: boolean
}

/** Full email with body returned by GET /api/email/{uid}. */
export interface EmailDetail extends EmailHeader {
  cc: string
  body: string
  has_attachments: boolean
}

/** Payload for POST /api/email/search. */
export interface EmailSearchRequest {
  query: string
  folder?: string
  limit?: number
}

/** WebSocket event emitted when a new email arrives via IMAP IDLE. */
export interface WsEmailReceivedMessage {
  type: 'email.received'
  folder: string
}

/** WebSocket event emitted after a successful send. */
export interface WsEmailSentMessage {
  type: 'email.sent'
  message_id?: string
}
```

##### `frontend/src/renderer/src/stores/email.ts` (nuovo file)

> **Prerequisito**: aggiungere prima i metodi email a `services/api.ts` (vedi sotto).

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../services/api'
import type { EmailHeader, EmailDetail, EmailSearchRequest } from '../types/email'

export const useEmailStore = defineStore('email', () => {
  const inbox = ref<EmailHeader[]>([])
  const currentEmail = ref<EmailDetail | null>(null)
  const folders = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentFolder = ref('INBOX')
  const unreadCount = computed(
    () => inbox.value.filter((e) => !e.is_read).length,
  )

  async function fetchInbox(
    folder = 'INBOX',
    limit = 20,
    unreadOnly = false,
  ): Promise<void> {
    loading.value = true
    error.value = null
    try {
      inbox.value = await api.getEmailInbox({ folder, limit, unread_only: unreadOnly })
      currentFolder.value = folder
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function fetchEmail(uid: string, folder = 'INBOX'): Promise<void> {
    loading.value = true
    error.value = null
    try {
      currentEmail.value = await api.getEmail(uid, folder)
      // Update is_read in inbox list
      const idx = inbox.value.findIndex((e) => e.uid === uid)
      if (idx !== -1) inbox.value[idx].is_read = true
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function searchEmails(req: EmailSearchRequest): Promise<void> {
    loading.value = true
    error.value = null
    try {
      inbox.value = await api.searchEmails(req)
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function markRead(uid: string, read = true, folder = 'INBOX'): Promise<void> {
    await api.markEmailRead(uid, folder, read)
    const idx = inbox.value.findIndex((e) => e.uid === uid)
    if (idx !== -1) inbox.value[idx].is_read = read
  }

  async function archiveEmail(uid: string, fromFolder = 'INBOX'): Promise<void> {
    await api.archiveEmail(uid, fromFolder)
    inbox.value = inbox.value.filter((e) => e.uid !== uid)
    if (currentEmail.value?.uid === uid) currentEmail.value = null
  }

  async function fetchFolders(): Promise<void> {
    try {
      folders.value = await api.getEmailFolders()
    } catch { /* non critico */ }
  }

  function handleEmailReceived(folder: string): void {
    if (folder === currentFolder.value) {
      void fetchInbox(currentFolder.value)
    }
  }

  function clearCurrentEmail(): void {
    currentEmail.value = null
  }

  return {
    inbox,
    currentEmail,
    folders,
    loading,
    error,
    currentFolder,
    unreadCount,
    fetchInbox,
    fetchEmail,
    searchEmails,
    markRead,
    archiveEmail,
    fetchFolders,
    handleEmailReceived,
    clearCurrentEmail,
  }
})
```

##### Aggiunta a `frontend/src/renderer/src/services/api.ts`

Aggiungere i metodi email nell'oggetto `api` esistente (accanto ai metodi notes/calendar):

```typescript
// ── Email Assistant (Phase 15) ─────────────────────────────────────────────────────────────
  getEmailInbox: (params: {
    folder?: string
    limit?: number
    unread_only?: boolean
  }): Promise<EmailHeader[]> =>
    request<EmailHeader[]>(
      `/email/inbox?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)]),
        ),
      )}`,
    ),
  getEmail: (uid: string, folder = 'INBOX'): Promise<EmailDetail> =>
    request<EmailDetail>(`/email/${encodeURIComponent(uid)}?folder=${folder}`),
  searchEmails: (req: EmailSearchRequest): Promise<EmailHeader[]> =>
    request<EmailHeader[]>('/email/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),
  markEmailRead: (uid: string, folder: string, read: boolean): Promise<{ success: boolean }> =>
    request<{ success: boolean }>(
      `/email/${encodeURIComponent(uid)}/read?folder=${folder}&read=${read}`,
      { method: 'PUT' },
    ),
  archiveEmail: (uid: string, fromFolder: string): Promise<{ success: boolean }> =>
    request<{ success: boolean }>(
      `/email/${encodeURIComponent(uid)}/archive?from_folder=${fromFolder}`,
      { method: 'PUT' },
    ),
  getEmailFolders: (): Promise<string[]> => request<string[]>('/email/folders'),
```

Importare i tipi nella firma `api.ts`:
```typescript
import type { EmailHeader, EmailDetail, EmailSearchRequest } from '../types/email'
```

##### `EmailPageView.vue` — `frontend/src/renderer/src/views/EmailPageView.vue` (nuovo file)

```vue
<script setup lang="ts">
/**
 * EmailPageView.vue — Vista principale Email Assistant.
 *
 * Layout a tre colonne: sidebar cartelle | InboxList | EmailViewer.
 * Le notifiche EMAIL_RECEIVED arrivano tramite useEventsWebSocket.ts (singleton).
 * Aggiungere in useEventsWebSocket.ts:
 *   if (data.type === 'email.received') {
 *     const emailStore = useEmailStore()
 *     emailStore.handleEmailReceived(data.folder as string)
 *   }
 */
import { onMounted } from 'vue'
import { useEmailStore } from '../stores/email'
import InboxList from '../components/email/InboxList.vue'
import EmailViewer from '../components/email/EmailViewer.vue'

const emailStore = useEmailStore()

onMounted(async () => {
  await emailStore.fetchInbox()
  await emailStore.fetchFolders()
})
</script>

<template>
  <div class="email-page">
    <aside class="email-page__folders">
      <div class="email-page__folder-title">Cartelle</div>
      <ul class="email-page__folder-list">
        <li
          v-for="folder in emailStore.folders"
          :key="folder"
          :class="{ active: emailStore.currentFolder === folder }"
          @click="emailStore.fetchInbox(folder)"
        >
          {{ folder }}
        </li>
      </ul>
    </aside>

    <section class="email-page__inbox">
      <InboxList />
    </section>

    <section class="email-page__viewer">
      <EmailViewer v-if="emailStore.currentEmail" />
      <div v-else class="email-page__empty">
        Seleziona un'email per leggerla
      </div>
    </section>
  </div>
</template>

<style scoped>
.email-page {
  display: grid;
  grid-template-columns: 180px 1fr 1.6fr;
  height: 100%;
  overflow: hidden;
  background: var(--surface-0);
}
.email-page__folders {
  border-right: 1px solid var(--border);
  padding: 12px 0;
  overflow-y: auto;
}
.email-page__folder-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  padding: 0 12px 8px;
}
.email-page__folder-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.email-page__folder-list li {
  padding: 6px 12px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  border-radius: 4px;
  margin: 0 4px;
}
.email-page__folder-list li:hover,
.email-page__folder-list li.active {
  background: var(--surface-2);
}
.email-page__inbox {
  border-right: 1px solid var(--border);
  overflow-y: auto;
}
.email-page__viewer {
  overflow-y: auto;
  padding: 20px;
}
.email-page__empty {
  padding: 32px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}
</style>
```

##### `InboxList.vue` — `frontend/src/renderer/src/components/email/InboxList.vue` (nuovo file)

```vue
<script setup lang="ts">
import { useEmailStore } from '../../stores/email'

const emailStore = useEmailStore()
</script>

<template>
  <div class="inbox-list">
    <div class="inbox-list__toolbar">
      <span class="inbox-list__count">
        {{ emailStore.inbox.length }} email
        <span v-if="emailStore.unreadCount > 0" class="inbox-list__unread">
          · {{ emailStore.unreadCount }} non lette
        </span>
      </span>
      <button
        class="inbox-list__refresh"
        :disabled="emailStore.loading"
        @click="emailStore.fetchInbox(emailStore.currentFolder)"
      >
        ↻
      </button>
    </div>

    <div v-if="emailStore.loading" class="inbox-list__loading">Caricamento…</div>
    <div v-else-if="emailStore.error" class="inbox-list__error">
      {{ emailStore.error }}
    </div>
    <div v-else-if="emailStore.inbox.length === 0" class="inbox-list__empty">
      Nessuna email
    </div>

    <ul v-else class="inbox-list__items">
      <li
        v-for="mail in emailStore.inbox"
        :key="mail.uid"
        class="inbox-list__item"
        :class="{ unread: !mail.is_read }"
        @click="emailStore.fetchEmail(mail.uid, emailStore.currentFolder)"
      >
        <div class="inbox-list__item-from">{{ mail.from }}</div>
        <div class="inbox-list__item-subject">{{ mail.subject }}</div>
        <div class="inbox-list__item-date">{{ mail.date }}</div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.inbox-list { display: flex; flex-direction: column; height: 100%; }
.inbox-list__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.inbox-list__count { font-size: 0.8rem; color: var(--text-secondary); }
.inbox-list__unread { color: var(--accent); font-weight: 600; }
.inbox-list__refresh {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 1rem;
}
.inbox-list__loading, .inbox-list__error, .inbox-list__empty {
  padding: 24px;
  text-align: center;
  font-size: 0.875rem;
  color: var(--text-secondary);
}
.inbox-list__error { color: var(--danger); }
.inbox-list__items { list-style: none; margin: 0; padding: 0; overflow-y: auto; flex: 1; }
.inbox-list__item {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}
.inbox-list__item:hover { background: var(--surface-2); }
.inbox-list__item.unread .inbox-list__item-subject { font-weight: 700; }
.inbox-list__item-from { font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 2px; }
.inbox-list__item-subject { font-size: 0.875rem; color: var(--text-primary); }
.inbox-list__item-date { font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px; }
</style>
```

##### `EmailViewer.vue` — `frontend/src/renderer/src/components/email/EmailViewer.vue` (nuovo file)

```vue
<script setup lang="ts">
import { useEmailStore } from '../../stores/email'

const emailStore = useEmailStore()

async function handleArchive() {
  if (!emailStore.currentEmail) return
  await emailStore.archiveEmail(
    emailStore.currentEmail.uid,
    emailStore.currentFolder,
  )
}

async function handleMarkRead(read: boolean) {
  if (!emailStore.currentEmail) return
  await emailStore.markRead(
    emailStore.currentEmail.uid,
    read,
    emailStore.currentFolder,
  )
}
</script>

<template>
  <div v-if="emailStore.currentEmail" class="email-viewer">
    <div class="email-viewer__header">
      <div class="email-viewer__subject">
        {{ emailStore.currentEmail.subject }}
      </div>
      <div class="email-viewer__meta">
        <span><b>Da:</b> {{ emailStore.currentEmail.from }}</span>
        <span><b>A:</b> {{ emailStore.currentEmail.to }}</span>
        <span v-if="emailStore.currentEmail.cc">
          <b>Cc:</b> {{ emailStore.currentEmail.cc }}
        </span>
        <span>{{ emailStore.currentEmail.date }}</span>
      </div>
      <div class="email-viewer__actions">
        <button @click="handleMarkRead(!emailStore.currentEmail?.is_read)">
          {{ emailStore.currentEmail.is_read ? 'Segna non letta' : 'Segna letta' }}
        </button>
        <button class="btn-archive" @click="handleArchive">Archivia</button>
        <button @click="emailStore.clearCurrentEmail()">Chiudi</button>
      </div>
    </div>
    <div class="email-viewer__body">{{ emailStore.currentEmail.body }}</div>
  </div>
</template>

<style scoped>
.email-viewer { display: flex; flex-direction: column; gap: 16px; }
.email-viewer__subject { font-size: 1.1rem; font-weight: 700; color: var(--text-primary); }
.email-viewer__meta {
  display: flex; flex-direction: column; gap: 4px;
  font-size: 0.8rem; color: var(--text-secondary);
}
.email-viewer__actions { display: flex; gap: 8px; flex-wrap: wrap; }
.email-viewer__actions button {
  padding: 4px 10px; border-radius: 4px; border: 1px solid var(--border);
  background: var(--surface-2); cursor: pointer; font-size: 0.8rem;
  color: var(--text-primary);
}
.btn-archive { border-color: var(--accent); color: var(--accent); }
.email-viewer__body {
  white-space: pre-wrap; font-size: 0.875rem; line-height: 1.6;
  color: var(--text-primary); background: var(--surface-2);
  padding: 16px; border-radius: 6px;
}
</style>
```

##### Router e sidebar — aggiornamenti

**`frontend/src/renderer/src/router/index.ts`** — aggiungere route:
```typescript
{
  path: '/email',
  name: 'email',
  component: () => import('../views/EmailPageView.vue'),
}
```

**`AppSidebar.vue`** — aggiornamenti:

`<script setup>` — aggiungere (accanto agli altri store imports):
```typescript
import { computed } from 'vue'
import { useEmailStore } from '../../stores/email'
const emailStore = useEmailStore()
const unreadCount = computed(() => emailStore.unreadCount)
```

Template — aggiungere voce di navigazione:
```vue
<router-link
  to="/email"
  class="sidebar__link"
  active-class="sidebar__link--active"
  :title="`Email${unreadCount ? ` (${unreadCount})` : ''}`"
>
  <span class="sidebar__link-icon" aria-hidden="true">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  </span>
  <span class="sidebar__link-label">Email</span>
  <span v-if="unreadCount" class="sidebar__badge">{{ unreadCount }}</span>
</router-link>
```

`<style scoped>` — aggiungere:
```css
.sidebar__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--accent);
  color: var(--bg-primary);
  font-size: 0.65rem;
  font-weight: 700;
  line-height: 1;
  margin-left: auto;
}
```

---

#### 15.10 — Dipendenze

##### Backend — `backend/pyproject.toml`

Aggiungere nel blocco `dependencies`:
```toml
# Email Assistant (Phase 15)
"aioimaplib>=1.0.1",
"aiosmtplib>=3.0",
```

Aggiungere la chiave `email` nella sezione `[project.optional-dependencies]` **esistente**
(non creare un secondo blocco — TOML non ammette table header duplicati):
```toml
# Dentro la sezione [project.optional-dependencies] gia' esistente, aggiungere dopo `memory`:
email = [
    "keyring>=24.0",
]
```

`keyring` è optional perché:
- Funziona su Windows (Credential Manager), macOS (Keychain), Linux (Secret Service / kwallet)
- Su Linux server senza GUI potrebbe non essere disponibile → `use_keyring=False` + env var
- `beautifulsoup4` è già in `dependencies` (usato da web_search)

Installazione completa:
```powershell
cd backend
uv pip install -e ".[dev,email]"
```

##### Frontend

Nessuna nuova dipendenza npm — Vue 3 + Pinia + fetch API nativa sono sufficienti.

---

#### 15.11 — Struttura File

```
backend/
  services/
    email_service.py              # EmailService: IMAP/SMTP + LRU cache + IDLE watcher
  plemail_assistant/
      __init__.py                 # Registra EmailPlugin nel PLUGIN_REGISTRY globale
      __init__.py                 # Esporta EmailPlugin
      plugin.py                   # EmailPlugin: 6 tool LLM
  api/
    routes/
      email.py                    # REST: GET inbox, GET uid, POST search, PUT read, PUT archive, GET folders
      __init__.py                 # + email.router
  core/
    config.py                     # + EmailConfig + AliceConfig.email
    protocols.py                  # + EmailServiceProtocol
    context.py                    # + email_service: EmailServiceProtocol | None
    event_bus.py                  # + EMAIL_RECEIVED, EMAIL_SENT in AliceEvent
    app.py                        # + startup init + event forwarding + shutdown close
  tests/
    test_email_service.py         # Unit test EmailService (IMAP/SMTP mocked)
    test_email_plugin.py          # Unit test EmailPlugin tool dispatch
    test_email_route.py           # Integration test REST endpoints

config/
  default.yaml                    # + sezione email:
  system_prompt.md                # + sezione email_assistant:

frontend/
  src/renderer/src/
    types/
      email.ts                    # TypeScript interfaces (EmailHeader, EmailDetail, WsEmail*)
    stores/
    services/
      api.ts                      # + metodi email (getEmailInbox, getEmail, searchEmails, ...)
    views/
      EmailPageView.vue           # Layout 3 colonne: folders | inbox | viewer
    components/
      email/
        InboxList.vue             # Lista email con toolbar e badge non lette
        EmailViewer.vue           # Viewer email completo con azioni
      AppSidebar.vue              # + voce navigazione /email + badge + CSS .sidebar__badge
    router/
      index.ts                    # + route { path: '/email', component: EmailPageView }
    composables/
      useEventsWebSocket.ts       # + handler email.received → emailStore.handleEmailReceived()non lette
        EmailViewer.vue           # Viewer email completo con azioni
```

---

#### 15.12 — Test Suite

**`backend/tests/test_email_service.py`**

```python
"""Test EmailService — operazioni IMAP/SMTP con mock."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.config import EmailConfig
from backend.core.event_bus import EventBus
from backend.services.email_service import EmailService, _LRUCache


# --------------------------------------------------------------------------
# _LRUCache unit tests
# --------------------------------------------------------------------------


def test_lru_cache_set_and_get():
    cache = _LRUCache(max_size=3, ttl_s=60)
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"


def test_lru_cache_miss_returns_none():
    cache = _LRUCache()
    assert cache.get("nonexistent") is None


def test_lru_cache_eviction_at_max_size():
    cache = _LRUCache(max_size=2, ttl_s=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # evicts oldest
    assert len(cache._store) == 2


def test_lru_cache_invalidate():
    cache = _LRUCache()
    cache.set("k", "v")
    cache.invalidate("k")
    assert cache.get("k") is None


def test_lru_cache_clear():
    cache = _LRUCache()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None


# --------------------------------------------------------------------------
# EmailService unit tests (IMAP/SMTP mocked)
# --------------------------------------------------------------------------


@pytest.fixture
def cfg():
    return EmailConfig(
        enabled=True,
        imap_host="imap.test.local",
        imap_port=993,
        smtp_host="smtp.test.local",
        smtp_port=587,
        username="user@test.local",
        use_keyring=False,
        fetch_last_n=20,
        rate_limit_send_per_hour=5,
        allowed_recipients=[],
        imap_idle_enabled=False,  # disable background task in tests
    )


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def service(cfg, bus):
    return EmailService(cfg, bus)


async def test_resolve_password_secret_str(service):
    """Password should be resolved from SecretStr when use_keyring=False."""
    pwd = await service._resolve_password()
    assert isinstance(pwd, str)


async def test_send_rate_limit(service):
    """Service should raise ValueError when rate limit is exceeded."""
    import time
    service._send_log = [time.monotonic()] * 5  # equals rate_limit_send_per_hour
    with pytest.raises(ValueError, match="Limite"):
        await service.send(to=["a@b.com"], subject="Test", body="hello")


async def test_send_blocked_recipient(service):
    """Service should raise ValueError when recipient is not in whitelist."""
    service._config = service._config.model_copy(
        update={"allowed_recipients": ["allowed@example.com"]}
    )
    with pytest.raises(ValueError, match="whitelist"):
        await service.send(to=["blocked@evil.com"], subject="Test", body="body")


async def test_send_allowed_recipient(service):
    """Service should send when recipient is in whitelist."""
    service._config = service._config.model_copy(
        update={"allowed_recipients": ["ok@example.com"]}
    )
    service._password_resolved = "fake-password"
    with patch("backend.services.email_service.aiosmtplib.send", new=AsyncMock(return_value=None)):
        result = await service.send(to=["ok@example.com"], subject="Hi", body="Hello")
    assert result["success"] is True
    assert "message_id" in result


async def test_send_empty_whitelist_allows_all(service):
    """Empty allowed_recipients means no restriction."""
    service._config = service._config.model_copy(update={"allowed_recipients": []})
    service._password_resolved = "pw"
    with patch("backend.services.email_service.aiosmtplib.send", new=AsyncMock(return_value=None)):
        result = await service.send(to=["anyone@anywhere.com"], subject="X", body="Y")
    assert result["success"] is True


def test_decode_header_plain(service):
    """Plain ASCII header should be returned as-is."""
    assert service._decode_header("Hello World") == "Hello World"


def test_decode_header_encoded(service):
    """RFC2047 encoded header should be decoded correctly."""
    encoded = "=?utf-8?b?Q2lhbyBNb25kbw==?="  # "Ciao Mondo"
    assert service._decode_header(encoded) == "Ciao Mondo"


def test_parse_email_strips_html(service):
    """HTML body should be converted to plain text."""
    from email.mime.text import MIMEText
    msg = MIMEText("<p>Hello <b>world</b></p>", "html", "utf-8")
    msg["Subject"] = "Test"
    msg["From"] = "a@b.com"
    msg["To"] = "c@d.com"
    msg["Date"] = "Mon, 1 Jan 2025 00:00:00 +0000"
    msg["Message-ID"] = "<test-id>"
    result = service._parse_email("1", msg.as_bytes())
    assert "Hello" in result["body"]
    assert "<p>" not in result["body"]
    assert "<b>" not in result["body"]


def test_parse_email_body_truncation(service):
    """Bodies longer than max_email_body_chars should be truncated."""
    from email.mime.text import MIMEText
    from backend.services.email_service import _TRUNCATION_SUFFIX
    service._config = service._config.model_copy(update={"max_email_body_chars": 10})
    msg = MIMEText("A" * 100, "plain", "utf-8")
    msg["Subject"] = "X"
    msg["From"] = "a@b.com"
    msg["To"] = "c@d.com"
    msg["Date"] = "Mon"
    msg["Message-ID"] = "<x>"
    result = service._parse_email("2", msg.as_bytes())
    assert len(result["body"]) <= 10 + len(_TRUNCATION_SUFFIX)
    assert "troncato" in result["body"]


async def test_close_without_imap_does_not_raise(service):
    """Close should be safe to call before initialize."""
    await service.close()  # no IMAP connection — should not raise
```

**`backend/tests/test_email_plugin.py`**

```python
"""Test EmailPlugin — dispatch tool LLM."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.core.plugin_models import ExecutionContext
from backend.plugins.email_assistant.plugin import EmailPlugin


@pytest.fixture
def exec_ctx() -> ExecutionContext:
    return ExecutionContext(
        session_id="test-session",
        conversation_id="test-conv",
        execution_id="test-exec",
    )


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.config.email.enabled = True
    ctx.config.email.rate_limit_send_per_hour = 10
    ctx.email_service = AsyncMock()
    return ctx


@pytest.fixture
def plugin(mock_ctx):
    p = EmailPlugin()
    p._ctx = mock_ctx
    return p


async def test_read_emails_returns_json(plugin, exec_ctx):
    plugin.ctx.email_service.fetch_inbox.return_value = [
        {"uid": "1", "subject": "Test", "from": "a@b.com", "is_read": False}
    ]
    result = await plugin.execute_tool("read_emails", {}, context=exec_ctx)
    assert result.success is True


async def test_get_email_not_found(plugin, exec_ctx):
    plugin.ctx.email_service.fetch_email.return_value = None
    result = await plugin.execute_tool("get_email", {"uid": "999"}, context=exec_ctx)
    assert result.success is False
    assert "999" in result.content


async def test_get_email_found(plugin, exec_ctx):
    plugin.ctx.email_service.fetch_email.return_value = {
        "uid": "5", "subject": "Hi", "from": "x@y.com", "body": "Ciao",
    }
    result = await plugin.execute_tool("get_email", {"uid": "5"}, context=exec_ctx)
    assert result.success is True


async def test_search_emails(plugin, exec_ctx):
    plugin.ctx.email_service.search.return_value = []
    result = await plugin.execute_tool(
        "search_emails", {"query": "SUBJECT test"}, context=exec_ctx
    )
    assert result.success is True


async def test_send_email_success(plugin, exec_ctx):
    plugin.ctx.email_service.send.return_value = {
        "success": True, "message_id": "<x>"
    }
    result = await plugin.execute_tool(
        "send_email",
        {"to": ["a@b.com"], "subject": "Hi", "body": "Hello"},
        context=exec_ctx,
    )
    assert result.success is True


async def test_send_email_rate_limit(plugin, exec_ctx):
    plugin.ctx.email_service.send.side_effect = ValueError("Limite invii")
    result = await plugin.execute_tool(
        "send_email",
        {"to": ["a@b.com"], "subject": "X", "body": "Y"},
        context=exec_ctx,
    )
    assert result.success is False


async def test_mark_as_read(plugin, exec_ctx):
    plugin.ctx.email_service.mark_read.return_value = True
    result = await plugin.execute_tool(
        "mark_as_read", {"uid": "3", "read": True}, context=exec_ctx
    )
    assert result.success is True


async def test_archive_email_success(plugin, exec_ctx):
    plugin.ctx.email_service.archive.return_value = True
    result = await plugin.execute_tool(
        "archive_email", {"uid": "7"}, context=exec_ctx
    )
    assert result.success is True


async def test_archive_email_not_found(plugin, exec_ctx):
    plugin.ctx.email_service.archive.return_value = False
    result = await plugin.execute_tool(
        "archive_email", {"uid": "ghost"}, context=exec_ctx
    )
    assert result.success is False


def test_plugin_disabled_returns_no_tools(mock_ctx):
    mock_ctx.config.email.enabled = False
    p = EmailPlugin()
    p._ctx = mock_ctx
    assert p.get_tools() == []


async def test_unknown_tool_returns_failure(plugin, exec_ctx):
    result = await plugin.execute_tool("nonexistent", {}, context=exec_ctx)
    assert result.success is False


async def test_service_unavailable(plugin, exec_ctx):
    plugin.ctx.email_service = None
    result = await plugin.execute_tool("read_emails", {}, context=exec_ctx)
    assert result.success is False
    assert "non disponibile" in result.content
```

**`backend/tests/test_email_route.py`**

```python
"""Test REST route /api/email/ — service unavailable path."""

import pytest


async def test_inbox_service_unavailable(client) -> None:
    """GET /api/email/inbox should return 503 when service is not running."""
    response = await client.get("/api/email/inbox")
    assert response.status_code == 503


async def test_get_email_service_unavailable(client) -> None:
    response = await client.get("/api/email/some-uid")
    assert response.status_code == 503


async def test_search_service_unavailable(client) -> None:
    response = await client.post(
        "/api/email/search",
        json={"query": "SUBJECT test"},
    )
    assert response.status_code == 503


async def test_list_folders_service_unavailable(client) -> None:
    response = await client.get("/api/email/folders")
    assert response.status_code == 503


async def test_mark_read_service_unavailable(client) -> None:
    response = await client.put("/api/email/some-uid/read")
    assert response.status_code == 503


async def test_archive_service_unavailable(client) -> None:
    response = await client.put("/api/email/some-uid/archive")
    assert response.status_code == 503
```

---

#### 15.13 — Ordine di Implementazione

1. `backend/pyproject.toml` — dipendenze `aioimaplib`, `aiosmtplib` in `dependencies` + extra `email` per `keyring`; installare con `uv pip install -e ".[dev,email]"`
2. `backend/core/config.py` — `EmailConfig` + `AliceConfig.email`
3. `config/default.yaml` — sezione `email:` (disabled di default)
4. `backend/core/protocols.py` — `EmailServiceProtocol`
5. `backend/core/context.py` — campo `email_service`
6. `backend/core/event_bus.py` — `EMAIL_RECEIVED`, `EMAIL_SENT` in `AliceEvent`
7. `backend/services/email_service.py` — `_LRUCache` + `EmailService` completo
8. `backend/core/app.py` — startup init + event forwarding + shutdown close
9. `backend/plugins/email_assistant/plugin.py` — `EmailPlugin`
10. `backend/plugins/email_assistant/__init__.py` — registrazione in `PLUGIN_REGISTRY` globale
11. `backend/api/routes/email.py` — 6 endpoint REST
12. `backend/api/routes/__init__.py` — registrazione `email.router`
13. `frontend/src/renderer/src/types/email.ts` — interfacce TypeScript
14. `frontend/src/renderer/src/services/api.ts` — aggiunta metodi email
15. `frontend/src/renderer/src/stores/email.ts` — Pinia store
16. `frontend/src/renderer/src/components/email/InboxList.vue`
17. `frontend/src/renderer/src/components/email/EmailViewer.vue`
18. `frontend/src/renderer/src/views/EmailPageView.vue`
19. Router entry `/email` + `AppSidebar.vue` voce navigazione + badge CSS
20. `frontend/src/renderer/src/composables/useEventsWebSocket.ts` — handler `email.received`
21. `config/system_prompt.md` — sezione `email_assistant:`
22. Test: `test_email_service.py`, `test_email_plugin.py`, `test_email_route.py`

---

#### 15.14 — Verifiche

| Scenario | Risultato atteso |
|---|---|
| `email.enabled=True` + credenziali IMAP valide → avvio backend | `"Email service started (user@example.com)"` nei log, plugin `email_assistant` caricato |
| `email.enabled=False` | Service non inizializzato, plugin non caricato, `GET /api/email/inbox` → 503, zero impatto su altri test |
| `use_keyring=True`, password in Windows Credential Manager | `EmailService._resolve_password()` recupera la password da keyring senza esposizione nel log |
| `use_keyring=True`, keyring vuoto + `keyring` installato | Log warning "Password non trovata nel keyring", servizio NON si avvia, AL\CE resta funzionante |
| `use_keyring=False`, `ALICE_EMAIL__PASSWORD=mypassword` | Password letta da env var tramite `SecretStr`, mai stampata nei log |
| `read_emails(limit=20)` → IMAP valido | Lista JSON di EmailHeader (uid, subject, from, to, date, is_read) |fallback a config password (se vuota → IMAP auth error → service non si avvia, AL\CE resta funzionante)
| `get_email(uid)` → email con body HTML | Corpo convertito in plain-text via bs4, HTML strip, max 8000 char |
| `search_emails(query="SUBJECT fattura")` | IMAP SEARCH eseguita, risultati ordinati per data |
| Input injection in query `" OR 1=1 LOGOUT "` | Caratteri non IMAP-safe rimossi da `re.sub` prima della chiamata IMAP |
| `send_email(to=[...], ...)` → utente approva conferma | Email inviata via `aiosmtplib`, log `EMAIL_SENT`, `WsEmailSentMessage` broadcast |
| `send_email` → utente rifiuta conferma | Email Il carattere `=` viene rimosso da `re.sub` (pattern `[^\w \"@.:\-]`); la stringa risultante `OR 11 LOGOUT` è passata ad IMAP (nota: parole chiave IMAP come `LOGOUT` non sono bloccate dal regex — il rischio residuo è accettato a livello di design)
| Superato `rate_limit_send_per_hour` | `ToolResult(success=False, content="Limite invii orari raggiunto…")` |
| `allowed_recipients=["ok@example.com"]`, invio a `evil@bad.com` | `ToolResult(success=False, content="Destinatari non nella whitelist…")` |
| `archive_email(uid)` → approvazione | Email spostata nella cartella `archive_folder`, rimossa da INBOX, cache invalidata |
| IMAP IDLE → nuova email arriva | `AliceEvent.EMAIL_RECEIVED` emesso, `ws_connection_manager` broadcasta `{"type": "email.received", "folder": "INBOX"}`, frontend `EmailPageView` refresh automatico |
| IMAP connection drop durante IDLE | Background task riprova dopo 60s di sleep, ricrea connessione IMAP |
| Backend riavviato (hot-reload) | `EmailService.close()` chiamato nello shutdown, IDLE task cancellato senza errori |
| `GET /api/email/inbox` con service disabilitato | HTTP 503 con `{"detail": "Email service non disponibile."}` |
| Frontend: apri `/email` | `EmailPageView` carica inbox e lista cartelle; badge "non lette" aggiornato |
| Clic su email → fetch body | `get_email` chiamato, `EmailViewer` mostra headers + corpo plain-text |
| `GET /api/email/folders` (service abilitato) | HTTP 200, lista JSON cartelle IMAP (es. `["INBOX", "Sent", "Archive"]`) |
| `use_keyring=True` + libreria `keyring` non installata (solo `.[dev]`) | Log warning "Libreria 'keyring' non installata", fallback a config password; se anche questa è vuota, IMAP login fallisce e service non si avvia |
| `send_email` → SMTP server rifiuta (auth/TLS error) | `ToolResult(success=False, content="Errore SMTP: ...")` — nessuna email inviata, nessun `EMAIL_SENT` emesso |
| `fetch_inbox()` chiamato due volte entro TTL (300s) | Seconda chiamata restituisce dati da cache senza round-trip IMAP |
| Bottone "Segna non letta" | `PUT /api/email/{uid}/read?read=false`, flag nell'inbox list aggiornato |
| Bottone "Archivia" | `PUT /api/email/{uid}/archive`, email scompare dall'inbox |
