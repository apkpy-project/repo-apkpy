"""Real-time WebSocket client shared by ApkPy applications and the Previewer."""

from __future__ import annotations

import base64
import collections
import hashlib
import os
import random
import socket
import ssl
import struct
import threading
import time
import urllib.parse


class WebSocketAPI:
    """WebSocket em tempo real sem dependências externas no Previewer.

    ``connect`` abre a ligação em background. ``send`` pode ser chamado logo a
    seguir: enquanto o handshake decorre, as mensagens ficam numa fila limitada
    a 64 entradas. Por omissão, falhas transitórias usam reconexão com backoff.
    """

    _MAX_PENDING = 64
    _MAX_FRAME_BYTES = 8 * 1024 * 1024
    _MAX_MESSAGE_BYTES = 16 * 1024 * 1024

    def __init__(self):
        self._lock = threading.RLock()
        self._connections = {}

    @staticmethod
    def _deliver(callback, *args):
        if callback is None:
            return
        root = None
        try:
            # Import tardio: evita uma dependência circular durante
            # ``from apkpy_lib import websocket``.
            from . import ui
            instance = getattr(ui._app, "_instance", None)
            root = getattr(instance, "root", None)
        except Exception:
            root = None
        if root is not None:
            try:
                root.after(0, lambda: callback(*args))
                return
            except Exception:
                pass
        callback(*args)

    @staticmethod
    def _safe_header(value):
        return str(value).replace("\r", "").replace("\n", "").strip()

    @staticmethod
    def _recv_exact(record, size):
        data = bytearray()
        prefetched = record.get("prefetched", b"")
        if prefetched:
            take = min(size, len(prefetched))
            data.extend(prefetched[:take])
            record["prefetched"] = prefetched[take:]
        while len(data) < size:
            chunk = record["socket"].recv(size - len(data))
            if not chunk:
                raise ConnectionError("WebSocket connection closed")
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def _write_frame(record, opcode, payload=b"", final=True):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        length = len(payload)
        first = (0x80 if final else 0) | (opcode & 0x0F)
        mask = os.urandom(4)
        if length < 126:
            header = bytes((first, 0x80 | length))
        elif length <= 0xFFFF:
            header = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
        else:
            header = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)
        masked = bytes(
            value ^ mask[index % 4] for index, value in enumerate(payload)
        )
        with record["send_lock"]:
            record["socket"].sendall(header + mask + masked)

    def _read_frame(self, record):
        head = self._recv_exact(record, 2)
        final = bool(head[0] & 0x80)
        opcode = head[0] & 0x0F
        masked = bool(head[1] & 0x80)
        length = head[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(record, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(record, 8))[0]
        if length > self._MAX_FRAME_BYTES:
            raise ValueError("WebSocket frame is too large")
        mask = self._recv_exact(record, 4) if masked else None
        payload = self._recv_exact(record, length)
        if mask:
            payload = bytes(
                value ^ mask[index % 4]
                for index, value in enumerate(payload)
            )
        return final, opcode, payload

    def _handshake(self, record):
        parsed = urllib.parse.urlsplit(record["url"])
        if parsed.scheme not in ("ws", "wss") or not parsed.hostname:
            raise ValueError("WebSocket URL must use ws:// or wss://")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        raw_socket = socket.create_connection(
            (parsed.hostname, port), timeout=15
        )
        if parsed.scheme == "wss":
            raw_socket = ssl.create_default_context().wrap_socket(
                raw_socket, server_hostname=parsed.hostname
            )
        raw_socket.settimeout(1.0)
        record["socket"] = raw_socket

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        default_port = 443 if parsed.scheme == "wss" else 80
        host = (
            parsed.hostname
            if port == default_port
            else f"{parsed.hostname}:{port}"
        )
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        lines = [
            f"GET {target} HTTP/1.1",
            f"Host: {host}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            "User-Agent: ApkPyPreviewer",
        ]
        protocols = record.get("protocols") or []
        if protocols:
            lines.append(
                "Sec-WebSocket-Protocol: "
                + ", ".join(self._safe_header(item) for item in protocols)
            )
        protected = {
            "host",
            "upgrade",
            "connection",
            "sec-websocket-key",
            "sec-websocket-version",
            "sec-websocket-protocol",
        }
        for name, value in (record.get("headers") or {}).items():
            header_name = self._safe_header(name)
            if header_name.lower() not in protected:
                lines.append(
                    f"{header_name}: {self._safe_header(value)}"
                )
        raw_socket.sendall(
            ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
        )

        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = raw_socket.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket handshake closed")
            response.extend(chunk)
            if len(response) > 65536:
                raise ValueError("WebSocket handshake is too large")
        raw_headers, prefetched = bytes(response).split(b"\r\n\r\n", 1)
        header_lines = raw_headers.decode("iso-8859-1").split("\r\n")
        if not header_lines or " 101 " not in f" {header_lines[0]} ":
            status = header_lines[0] if header_lines else "empty response"
            raise ConnectionError(
                "WebSocket handshake rejected: " + status
            )
        response_headers = {}
        for line in header_lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                response_headers[name.lower().strip()] = value.strip()
        expected = base64.b64encode(
            hashlib.sha1(
                (
                    key
                    + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                ).encode("ascii")
            ).digest()
        ).decode("ascii")
        if response_headers.get("sec-websocket-accept") != expected:
            raise ConnectionError("Invalid WebSocket handshake response")
        record["prefetched"] = prefetched

    def _flush_pending(self, record):
        while True:
            with self._lock:
                if not record["pending"]:
                    return
                message = record["pending"].popleft()
            self._write_frame(record, 0x1, message)

    def _listen(self, record):
        fragments = bytearray()
        fragment_opcode = None
        ping_interval = record.get("ping_interval", 0.0)
        next_ping = (
            time.monotonic() + ping_interval
            if ping_interval > 0 else None
        )
        while not record["cancel"].is_set():
            try:
                final, opcode, payload = self._read_frame(record)
            except (TimeoutError, socket.timeout):
                if next_ping is not None and time.monotonic() >= next_ping:
                    self._write_frame(record, 0x9, os.urandom(4))
                    next_ping = time.monotonic() + ping_interval
                continue
            if opcode == 0x8:
                code, reason = 1000, ""
                if len(payload) >= 2:
                    code = struct.unpack("!H", payload[:2])[0]
                    reason = payload[2:].decode(
                        "utf-8", errors="replace"
                    )
                try:
                    self._write_frame(record, 0x8, payload)
                except Exception:
                    pass
                return code, reason
            if opcode == 0x9:
                self._write_frame(record, 0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2):
                fragments = bytearray(payload)
                fragment_opcode = opcode
            elif opcode == 0x0 and fragment_opcode is not None:
                fragments.extend(payload)
            else:
                continue
            if len(fragments) > self._MAX_MESSAGE_BYTES:
                raise ValueError("WebSocket message is too large")
            if final and fragment_opcode is not None:
                if fragment_opcode == 0x1:
                    self._deliver(
                        record["on_message"],
                        bytes(fragments).decode(
                            "utf-8", errors="replace"
                        ),
                    )
                fragments = bytearray()
                fragment_opcode = None
        return 1000, "closed"

    def _worker(self, record):
        attempt = 0
        code, reason = 1000, "closed"
        while not record["cancel"].is_set():
            code, reason = 1006, "connection lost"
            try:
                self._handshake(record)
                with self._lock:
                    record["connected"] = True
                attempt = 0
                self._deliver(record["on_open"])
                self._flush_pending(record)
                code, reason = self._listen(record)
            except Exception as exc:
                reason = str(exc)
                if not record["cancel"].is_set():
                    print(f"[websocket] '{record['id']}': {reason}")
                    self._deliver(record["on_error"], reason)
            finally:
                with self._lock:
                    record["connected"] = False
                sock = record.get("socket")
                record["socket"] = None
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

            if record["cancel"].is_set() or not record["reconnect"]:
                break
            self._deliver(record["on_close"], str(code), str(reason))
            delay = min(
                record["max_reconnect_delay"],
                record["reconnect_delay"] * (2 ** min(attempt, 8)),
            )
            attempt += 1
            delay += random.uniform(0, min(0.5, delay * 0.2))
            if record["cancel"].wait(delay):
                break

        if not record["close_delivered"]:
            record["close_delivered"] = True
            self._deliver(record["on_close"], str(code), str(reason))
        with self._lock:
            if self._connections.get(record["id"]) is record:
                self._connections.pop(record["id"], None)

    def connect(
        self,
        connection_id,
        url,
        headers=None,
        protocols=None,
        on_open=None,
        on_message=None,
        on_close=None,
        on_error=None,
        reconnect=True,
        reconnect_delay=1.0,
        max_reconnect_delay=15.0,
        ping_interval=25.0,
    ):
        """Abre uma ligação; um ID repetido substitui a ligação anterior."""
        key = str(connection_id)
        self.close(key)
        reconnect_delay = max(0.1, float(reconnect_delay))
        record = {
            "id": key,
            "url": str(url),
            "headers": dict(headers or {}),
            "protocols": list(protocols or []),
            "on_open": on_open,
            "on_message": on_message,
            "on_close": on_close,
            "on_error": on_error,
            "reconnect": bool(reconnect),
            "reconnect_delay": reconnect_delay,
            "max_reconnect_delay": max(
                reconnect_delay, float(max_reconnect_delay)
            ),
            # Conservado para paridade com Android. O Previewer responde
            # imediatamente a pings iniciados pelo servidor.
            "ping_interval": max(0.0, float(ping_interval)),
            "cancel": threading.Event(),
            "send_lock": threading.Lock(),
            "pending": collections.deque(maxlen=self._MAX_PENDING),
            "socket": None,
            "prefetched": b"",
            "connected": False,
            "close_delivered": False,
        }
        with self._lock:
            self._connections[key] = record
        threading.Thread(
            target=self._worker,
            args=(record,),
            name=f"apkpy-websocket-{key}",
            daemon=True,
        ).start()
        return key

    def send(self, connection_id, message):
        """Envia texto; durante o handshake, guarda até 64 mensagens."""
        key = str(connection_id)
        text = str(message)
        with self._lock:
            record = self._connections.get(key)
            if record is None or record["cancel"].is_set():
                return False
            if not record["connected"] or record.get("socket") is None:
                record["pending"].append(text)
                return True
        try:
            self._write_frame(record, 0x1, text)
            return True
        except Exception as exc:
            self._deliver(record["on_error"], str(exc))
            return False

    def close(self, connection_id, code=1000, reason="closed"):
        """Fecha intencionalmente e impede novas tentativas de reconexão."""
        key = str(connection_id)
        with self._lock:
            record = self._connections.pop(key, None)
        if record is None:
            return False
        record["reconnect"] = False
        record["cancel"].set()
        sock = record.get("socket")
        if sock is not None:
            try:
                clean_reason = str(reason).encode("utf-8")[:123]
                safe_code = max(1000, min(4999, int(code)))
                self._write_frame(
                    record,
                    0x8,
                    struct.pack("!H", safe_code) + clean_reason,
                )
            except Exception:
                pass
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
        return True

    def is_connected(self, connection_id):
        with self._lock:
            record = self._connections.get(str(connection_id))
            return bool(record and record["connected"])

    def close_all(self):
        with self._lock:
            connection_ids = list(self._connections)
        for connection_id in connection_ids:
            self.close(connection_id)


websocket = WebSocketAPI()
