"""Discord local RPC client.

Talks to the desktop client over the IPC socket it exposes (``discord-ipc-N``)
to read the self-mute state, change it, and hear about changes made anywhere
else (Discord's own button, its keybinds, another device). It also follows
which voice channel the user is in, when their own voice is transmitted, and
the notifications Discord shows for new messages.

Access needs an OAuth2 token for the user's own Developer Portal application.
The first connection asks for permission inside Discord; later ones reuse the
stored token, refreshing it when it expires.
"""

import json
import logging
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtNetwork import QLocalSocket

import constants

logger = logging.getLogger("livedot.discord")

# IPC frame opcodes. Every frame is <opcode:u32 LE><length:u32 LE><JSON>.
OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4

TOKEN_URL = "https://discord.com/api/oauth2/token"
REDIRECT_URI = "http://localhost"
SCOPES = ["rpc", "rpc.voice.read", "rpc.voice.write", "rpc.notifications.read"]
USER_AGENT = "livedot (https://github.com/kahd0/livedot)"

# Channel types whose every message is addressed to the user.
DM_CHANNEL_TYPES = (1, 3)  # DM, group DM


def ipc_candidates():
    """Socket paths (Linux) or pipe names (Windows) Discord may listen on."""
    names = [f"discord-ipc-{i}" for i in range(10)]
    if sys.platform == "win32":
        # QLocalSocket turns a bare name into \\.\pipe\<name> on Windows.
        return names
    base = (os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR")
            or os.environ.get("TMP") or os.environ.get("TEMP") or "/tmp")
    # Flatpak and Snap builds put the socket in a sandbox subdirectory.
    dirs = [base,
            os.path.join(base, "app", "com.discordapp.Discord"),
            os.path.join(base, "snap.discord")]
    paths = (os.path.join(d, n) for d in dirs for n in names)
    return [p for p in paths if os.path.exists(p)]


class TokenError(Exception):
    """A token request failed. ``permanent`` means retrying the same grant is
    pointless (revoked, wrong secret); otherwise it was likely the network."""

    def __init__(self, message, permanent):
        super().__init__(message)
        self.permanent = permanent


def request_token(fields):
    """POSTs a grant to the OAuth2 token endpoint and returns the JSON reply."""
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(TOKEN_URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        # Cloudflare in front of discord.com rejects urllib's default agent.
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise TokenError(f"HTTP {e.code}: {detail}", permanent=400 <= e.code < 500)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise TokenError(str(e), permanent=False)


class DiscordRPC(QObject):
    voice_changed = pyqtSignal(bool, bool)  # mute, deaf
    call_changed = pyqtSignal(bool)         # in a voice channel or not
    call_joined = pyqtSignal()              # just joined or moved into a voice channel
    speaking_changed = pyqtSignal(bool)     # the user's own voice is being transmitted
    notified = pyqtSignal(str, str, bool)   # channel id, title, addressed to the user directly
    connection_changed = pyqtSignal(bool)   # True once authenticated and subscribed
    status_changed = pyqtSignal(str)        # human-readable status, in Portuguese
    _token_done = pyqtSignal(object, str, bool)  # reply, error, permanent

    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.status = ""
        self.ready = False
        self.mute = False
        self.deaf = False
        self.user_id = None
        self.channel_id = None   # voice channel the user is in, if any
        self.speaking = False
        self._direct_channels = {}   # channel id -> is a DM, as GET_CHANNEL said
        self._channel_lookups = {}   # GET_CHANNEL nonce -> (channel id, title)

        self._socket = None
        self._buffer = b""
        # The permission prompt pops up inside Discord, so it is shown at most
        # once per app start or explicit "Conectar"; a denial must not turn
        # the reconnect loop into a prompt loop.
        self._may_authorize = True
        self._token_pending = False
        self._auth_failures = 0

        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._connect)

        self._token_done.connect(self._on_token_done)

    # Public API
    @property
    def configured(self):
        cfg = self.state_manager.config
        return bool(cfg["discord_client_id"] and cfg["discord_client_secret"])

    @property
    def in_call(self):
        return self.channel_id is not None

    def start(self):
        self._connect()

    @pyqtSlot()
    def reconnect(self):
        """Connects from scratch, allowing a new permission prompt."""
        self._may_authorize = True
        self._drop_socket()
        self._connect()

    @pyqtSlot()
    def toggle_mute(self):
        if not self.ready:
            # A click on a disconnected dot is a request to try again.
            if self._socket is None:
                self.reconnect()
            return
        if self.mute or self.deaf:
            # Opening the mic also undeafens, like Discord's own mic button.
            self._command("SET_VOICE_SETTINGS", {"mute": False, "deaf": False})
        else:
            self._command("SET_VOICE_SETTINGS", {"mute": True})

    @pyqtSlot()
    def toggle_deaf(self):
        if self.ready:
            self._command("SET_VOICE_SETTINGS", {"deaf": not self.deaf})

    def set_voice(self, mute, deaf):
        if self.ready:
            self._command("SET_VOICE_SETTINGS", {"mute": mute, "deaf": deaf})

    def select_text_channel(self, channel_id):
        if self.ready:
            self._command("SELECT_TEXT_CHANNEL", {"channel_id": channel_id})

    def close(self):
        self._retry_timer.stop()
        self._drop_socket()

    # Connection lifecycle
    def _connect(self):
        self._retry_timer.stop()
        if self._socket is not None:
            return
        if not self.configured:
            self._set_status("Discord não configurado")
            return

        sock = None
        for name in ipc_candidates():
            candidate = QLocalSocket(self)
            candidate.connectToServer(name)
            if candidate.waitForConnected(500):
                sock = candidate
                logger.info(f"Connected to Discord IPC at {name}")
                break
            candidate.deleteLater()

        if sock is None:
            self._set_status("Discord fechado")
            self._retry_timer.start(constants.DISCORD_RECONNECT_MS)
            return

        self._socket = sock
        self._buffer = b""
        self._auth_failures = 0
        sock.readyRead.connect(self._on_ready_read)
        sock.disconnected.connect(self._on_disconnected)
        self._set_status("Conectando…")
        self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.state_manager.config["discord_client_id"]})

    def _drop_socket(self):
        sock, self._socket = self._socket, None
        self._buffer = b""
        if sock is not None:
            # Detach first so abort() doesn't re-enter _on_disconnected.
            sock.readyRead.disconnect(self._on_ready_read)
            sock.disconnected.disconnect(self._on_disconnected)
            sock.abort()
            sock.deleteLater()
        self._channel_lookups.clear()
        self._set_channel(None, joined=False)
        if self.ready:
            self.ready = False
            self.connection_changed.emit(False)

    def _lose(self, status, retry):
        """Drops the connection, shows why, and optionally tries again later."""
        self._drop_socket()
        self._set_status(status)
        if retry:
            self._retry_timer.start(constants.DISCORD_RECONNECT_MS)

    def _on_disconnected(self):
        logger.info("Discord IPC connection closed.")
        self._lose("Discord fechado", retry=True)

    # Wire protocol
    def _send(self, op, payload):
        if self._socket is None:
            return
        data = json.dumps(payload).encode("utf-8")
        self._socket.write(struct.pack("<II", op, len(data)) + data)
        self._socket.flush()

    def _command(self, cmd, args=None, evt=None):
        """Sends a command and returns its nonce, which the reply echoes."""
        message = {"cmd": cmd, "args": args or {}, "nonce": str(uuid.uuid4())}
        if evt:
            message["evt"] = evt
        self._send(OP_FRAME, message)
        return message["nonce"]

    def _on_ready_read(self):
        self._buffer += bytes(self._socket.readAll())
        while self._socket is not None and len(self._buffer) >= 8:
            op, length = struct.unpack("<II", self._buffer[:8])
            if len(self._buffer) < 8 + length:
                break
            payload = self._buffer[8:8 + length]
            self._buffer = self._buffer[8 + length:]
            try:
                message = json.loads(payload)
            except ValueError:
                logger.warning(f"Ignoring malformed Discord frame (op {op}).")
                continue
            self._on_message(op, message)

    def _on_message(self, op, message):
        if op == OP_PING:
            self._send(OP_PONG, message)
            return
        if op == OP_CLOSE:
            # Discord refused us outright (bad client ID, rate limit...).
            # Retrying on a timer would only repeat the refusal.
            reason = message.get("message") or message.get("code")
            logger.warning(f"Discord closed the connection: {message}")
            self._lose(f"Discord recusou a conexão: {reason}", retry=False)
            return
        if op != OP_FRAME:
            return

        cmd = message.get("cmd")
        evt = message.get("evt")
        data = message.get("data") or {}

        if evt == "ERROR":
            self._on_error(cmd, data, message.get("nonce"))
        elif cmd == "DISPATCH" and evt == "READY":
            self._authenticate_or_authorize()
        elif cmd == "DISPATCH" and evt == "VOICE_SETTINGS_UPDATE":
            self._apply_voice(data)
        elif cmd == "DISPATCH" and evt == "VOICE_CHANNEL_SELECT":
            self._set_channel(data.get("channel_id"), joined=True)
        elif cmd == "DISPATCH" and evt in ("SPEAKING_START", "SPEAKING_STOP"):
            if data.get("user_id") == self.user_id and data.get("channel_id") in (None, self.channel_id):
                self._set_speaking(evt == "SPEAKING_START")
        elif cmd == "DISPATCH" and evt == "NOTIFICATION_CREATE":
            self._on_notification(data)
        elif cmd == "GET_CHANNEL":
            self._finish_lookup(message.get("nonce"), data)
        elif cmd == "AUTHORIZE":
            self._request_token({"grant_type": "authorization_code",
                                 "code": data.get("code", ""),
                                 "redirect_uri": REDIRECT_URI})
        elif cmd == "AUTHENTICATE":
            logger.info("Authenticated with Discord.")
            self.user_id = (data.get("user") or {}).get("id")
            self._command("SUBSCRIBE", evt="VOICE_SETTINGS_UPDATE")
            self._command("SUBSCRIBE", evt="VOICE_CHANNEL_SELECT")
            self._command("SUBSCRIBE", evt="NOTIFICATION_CREATE")
            self._command("GET_SELECTED_VOICE_CHANNEL")
            self._command("GET_VOICE_SETTINGS")
        elif cmd == "GET_SELECTED_VOICE_CHANNEL":
            self._set_channel(data.get("id"), joined=False)
        elif cmd in ("GET_VOICE_SETTINGS", "SET_VOICE_SETTINGS"):
            self._apply_voice(data)

    def _on_error(self, cmd, data, nonce):
        message = data.get("message") or data.get("code")
        logger.warning(f"Discord RPC error on {cmd}: {data}")
        if cmd == "AUTHENTICATE":
            self._auth_failures += 1
            if self._auth_failures > 1:
                # Even a freshly issued token was refused, so refreshing
                # again would just loop.
                self._lose(f"Discord recusou o acesso: {message}", retry=False)
                return
            # Expired or revoked access token: forget it and fall back to the
            # refresh token, or to a fresh authorization.
            cfg = self.state_manager.config
            self.state_manager.set_discord_tokens("", cfg["discord_refresh_token"], 0,
                                                  cfg["discord_token_scopes"])
            self._authenticate_or_authorize()
        elif cmd == "AUTHORIZE":
            cfg = self.state_manager.config
            if cfg["discord_access_token"] or cfg["discord_refresh_token"]:
                # Only the request for extra scopes was turned down: carry on
                # with the older grant and without the features it lacks.
                logger.info("Extra scopes refused; using the existing grant.")
                self._authenticate_or_authorize()
            else:
                self._lose(f"Autorização negada: {message}", retry=False)
        elif cmd == "GET_CHANNEL":
            self._finish_lookup(nonce, {})
        elif cmd in ("SUBSCRIBE", "UNSUBSCRIBE"):
            pass  # Only the feature fed by that event is lost; the log has it.
        else:
            self._set_status(f"Erro do Discord: {message}")

    def _authenticate_or_authorize(self):
        cfg = self.state_manager.config
        # A grant from before some feature needed more scopes still works for
        # the rest, but while a prompt is allowed, ask for the full set first.
        granted = set(cfg["discord_token_scopes"].split())
        upgrade = self._may_authorize and not set(SCOPES) <= granted
        if not upgrade and cfg["discord_access_token"] and cfg["discord_token_expires"] > time.time() + 60:
            self._set_status("Autenticando…")
            self._command("AUTHENTICATE", {"access_token": cfg["discord_access_token"]})
        elif not upgrade and cfg["discord_refresh_token"]:
            self._set_status("Renovando acesso…")
            self._request_token({"grant_type": "refresh_token",
                                 "refresh_token": cfg["discord_refresh_token"]})
        elif self._may_authorize:
            self._may_authorize = False
            self._set_status("Autorize o LiveDot na janela do Discord")
            self._command("AUTHORIZE", {"client_id": cfg["discord_client_id"],
                                        "scopes": SCOPES})
        else:
            self._lose("Autorização necessária: clique em Conectar", retry=False)

    def _apply_voice(self, data):
        if "mute" not in data and "deaf" not in data:
            return
        self.mute = bool(data.get("mute", self.mute))
        self.deaf = bool(data.get("deaf", self.deaf))
        self.voice_changed.emit(self.mute, self.deaf)
        if not self.ready:
            self.ready = True
            self._set_status("Conectado")
            self.connection_changed.emit(True)

    def _set_channel(self, channel_id, joined):
        """Tracks the voice channel. ``joined`` marks a change Discord just
        reported, as opposed to the channel we found on connecting."""
        channel_id = channel_id or None
        if channel_id == self.channel_id:
            return
        was_in_call = self.in_call
        if self.channel_id:
            self._subscribe_speaking("UNSUBSCRIBE", self.channel_id)
        self.channel_id = channel_id
        self._set_speaking(False)
        if channel_id:
            self._subscribe_speaking("SUBSCRIBE", channel_id)
        logger.info(f"Voice channel: {channel_id or 'none'}")
        if self.in_call != was_in_call:
            self.call_changed.emit(self.in_call)
        if channel_id and joined:
            self.call_joined.emit()

    def _subscribe_speaking(self, cmd, channel_id):
        for evt in ("SPEAKING_START", "SPEAKING_STOP"):
            self._command(cmd, {"channel_id": channel_id}, evt=evt)

    def _set_speaking(self, speaking):
        if speaking != self.speaking:
            self.speaking = speaking
            self.speaking_changed.emit(speaking)

    def _on_notification(self, data):
        """Passes on a notification Discord showed, without the message text.
        A mention of the user is direct; so is anything in a DM, which
        mentions nobody, so the channel type is looked up once per channel."""
        message = data.get("message") or {}
        channel_id = data.get("channel_id") or ""
        title = data.get("title") or ""
        mentioned = any((user or {}).get("id") == self.user_id
                        for user in message.get("mentions") or [])
        logger.info(f"Notification in channel {channel_id} (mentions us: {mentioned})")
        if mentioned or channel_id in self._direct_channels:
            self.notified.emit(channel_id, title,
                               mentioned or self._direct_channels[channel_id])
            return
        nonce = self._command("GET_CHANNEL", {"channel_id": channel_id})
        self._channel_lookups[nonce] = (channel_id, title)

    def _finish_lookup(self, nonce, channel):
        pending = self._channel_lookups.pop(nonce, None)
        if pending is None:
            return
        channel_id, title = pending
        direct = channel.get("type") in DM_CHANNEL_TYPES
        if channel:
            self._direct_channels[channel_id] = direct
        self.notified.emit(channel_id, title, direct)

    # OAuth2 token exchange (runs off the GUI thread)
    def _request_token(self, grant):
        if self._token_pending:
            return
        self._token_pending = True
        cfg = self.state_manager.config
        fields = {"client_id": cfg["discord_client_id"],
                  "client_secret": cfg["discord_client_secret"], **grant}
        threading.Thread(target=self._token_worker, args=(fields,), daemon=True).start()

    def _token_worker(self, fields):
        try:
            try:
                reply = request_token(fields)
            except TokenError as e:
                # Whether Discord wants the redirect URI for RPC codes is not
                # documented; if it objects to it, try once without.
                if "redirect_uri" not in str(e) or "redirect_uri" not in fields:
                    raise
                fields = {k: v for k, v in fields.items() if k != "redirect_uri"}
                reply = request_token(fields)
            if "access_token" not in reply:
                raise TokenError(f"resposta sem token: {reply}", permanent=True)
            self._token_done.emit(reply, "", False)
        except TokenError as e:
            self._token_done.emit(None, str(e), e.permanent)

    def _on_token_done(self, reply, error, permanent):
        self._token_pending = False
        if reply is None:
            logger.error(f"Discord token request failed: {error}")
            if not permanent:
                self._lose("Sem acesso a discord.com; tentando de novo", retry=True)
                return
            # The grant is dead (revoked, wrong secret): start over, which
            # prompts again if this session still may.
            self.state_manager.set_discord_tokens("", "", 0, "")
            if self._socket is not None and self._may_authorize:
                self._authenticate_or_authorize()
            else:
                self._lose(f"Falha ao obter acesso: {error}", retry=False)
            return

        self.state_manager.set_discord_tokens(
            reply["access_token"],
            reply.get("refresh_token", ""),
            time.time() + int(reply.get("expires_in", 0)),
            reply.get("scope", ""))
        if self._socket is not None:
            self._set_status("Autenticando…")
            self._command("AUTHENTICATE", {"access_token": reply["access_token"]})

    def _set_status(self, status):
        if status != self.status:
            self.status = status
            logger.info(f"Discord status: {status}")
            self.status_changed.emit(status)
