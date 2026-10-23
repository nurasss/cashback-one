"""LAN-only QR bridge. No ONE, state store, cursor or HMAC dependencies."""

from __future__ import annotations

import hmac
import json
import logging
import re
import socket
import threading
import time
from collections import deque
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address

import httpx

from poscenter_loyalty_agent.config import AgentSettings

logger = logging.getLogger(__name__)
QR_PATTERN = re.compile(r"C1[A-Z2-7]{20,120}", re.ASCII)
BARCODE_PATTERN = re.compile(r"[0-9]{4,13}", re.ASCII)
MAX_BODY_BYTES = 1024
SOCKET_TIMEOUT_SECONDS = 2.0


class PosError(Exception):
    """An explicitly safe error; never includes upstream text or request data."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


class PosRateLimiter:
    """Thread-safe rolling windows, including unsuccessful authentication attempts."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[deque[float], deque[float]]] = {}

    def allow(self, address: str, authenticated: bool) -> bool:
        now = self.clock()
        with self._lock:
            # Bound memory even when many addresses on an allowed network send traffic.
            for key, (requests, failures) in list(self._windows.items()):
                for window in (requests, failures):
                    while window and window[0] <= now - 60:
                        window.popleft()
                if not requests and not failures:
                    del self._windows[key]
            if address not in self._windows:
                if len(self._windows) >= 4096:
                    return False
                self._windows[address] = (deque(), deque())
            requests, failures = self._windows[address]
            if len(requests) >= 60 or (not authenticated and len(failures) >= 10):
                return False
            requests.append(now)
            if not authenticated:
                failures.append(now)
            return True


class _PosHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False

    def __init__(
        self,
        address: tuple[str, int],
        settings: AgentSettings,
        transport: httpx.BaseTransport | None,
    ) -> None:
        self.settings = settings
        self.networks = settings.pos_allowed_networks
        self.transport = transport
        self.limiter = PosRateLimiter()
        self.address_family = socket.AF_INET6 if ip_address(address[0]).version == 6 else socket.AF_INET
        super().__init__(address, _PosHandler)

    def handle_error(self, request: object, client_address: object) -> None:
        # The default implementation prints a traceback which can contain secrets.
        logger.error("POS request handler failed")

    def resolve(self, token: str) -> str:
        logger.info("POS QR received (prefix=%s, length=%d)", token[:4], len(token))
        try:
            # A client per request avoids sharing resources with the async sync client.
            # Closing the listener never closes another thread's active cloud request.
            with httpx.Client(
                base_url=self.settings.agent_cloud_base_url,
                headers={"X-Agent-Key": self.settings.agent_api_key},
                timeout=httpx.Timeout(self.settings.agent_pos_cloud_timeout_seconds),
                verify=self.settings.cloud_api_verify_ssl,
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = client.post("/agent/qr/resolve", json={"token": token})
        except httpx.TimeoutException:
            raise PosError(504, "CLOUD_TIMEOUT", "Облако не ответило вовремя.") from None
        except httpx.RequestError:
            raise PosError(503, "CLOUD_UNAVAILABLE", "Облако недоступно.") from None
        if response.status_code == 422:
            raise PosError(422, "QR_TOKEN_INVALID", "Попросите покупателя обновить QR.")
        if response.status_code in (401, 403):
            raise PosError(502, "AGENT_NOT_AUTHORIZED", "Ключ агента не принят облаком.")
        if response.status_code != 200:
            raise PosError(502, "CLOUD_ERROR", "Ошибка ответа облака.")
        try:
            body = response.json()
        except ValueError:
            raise PosError(502, "CLOUD_ERROR", "Ошибка ответа облака.") from None
        barcode = body.get("barcode") if isinstance(body, dict) else None
        if not isinstance(barcode, str) or BARCODE_PATTERN.fullmatch(barcode) is None:
            raise PosError(502, "CLOUD_ERROR", "Ошибка ответа облака.")
        logger.info("POS QR resolved (barcode suffix=%s)", barcode[-4:])
        return barcode


class _PosHandler(BaseHTTPRequestHandler):
    server: _PosHTTPServer

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(SOCKET_TIMEOUT_SECONDS)

    def version_string(self) -> str:
        return "POSCENTER-POS"

    def log_message(self, format: str, *args: object) -> None:
        # No access log: request line, headers and body are untrusted/sensitive.
        pass

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        self._error(PosError(code, "POS_BAD_REQUEST", "Некорректный HTTP-запрос."))

    def _json(self, status: int, body: dict[str, object]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(data)

    def _error(self, error: PosError) -> None:
        self._json(error.status, {"error": {"code": error.code, "message": error.message}})

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        try:
            self._dispatch()
        except PosError as exc:
            self._error(exc)
        except TimeoutError:
            self._error(PosError(408, "POS_REQUEST_TIMEOUT", "Время чтения запроса истекло."))
        except OSError:
            # A disconnected cashier must not affect other requests or sync.
            pass
        except Exception as exc:
            logger.error("POS request failed (type=%s)", type(exc).__name__)
            self._error(PosError(500, "POS_INTERNAL_ERROR", "Ошибка POS-сервиса."))

    def _dispatch(self) -> None:
        address = ip_address(self.client_address[0])
        if not any(address in network for network in self.server.networks):
            raise PosError(403, "POS_FORBIDDEN", "Адрес кассы не разрешён.")
        supplied = self.headers.get_all("X-Pos-Token", [])
        expected = self.server.settings.agent_pos_token.get_secret_value().encode("utf-8")
        authenticated = len(supplied) == 1 and hmac.compare_digest(
            supplied[0].encode("utf-8"), expected,
        )
        # Password is compared first. Failed attempts must also reach the limiter,
        # otherwise it could never return 429 for an incorrect password.
        if not self.server.limiter.allow(str(address), authenticated):
            raise PosError(429, "POS_RATE_LIMITED", "Слишком много запросов. Подождите минуту.")
        if not authenticated:
            raise PosError(401, "POS_UNAUTHORIZED", "Неверный пароль кассы.")
        if self.command == "GET" and self.path == "/v1/health":
            self._json(200, {"status": "ok"})
            return
        if self.command != "POST" or self.path != "/v1/qr/resolve":
            raise PosError(404, "POS_NOT_FOUND", "Маршрут не найден.")
        if self.headers.get("Transfer-Encoding") is not None:
            raise PosError(400, "POS_BAD_REQUEST", "Передайте тело с Content-Length.")
        lengths = self.headers.get_all("Content-Length", [])
        if not lengths:
            raise PosError(411, "POS_LENGTH_REQUIRED", "Требуется Content-Length.")
        if len(lengths) != 1 or re.fullmatch(r"[0-9]{1,10}", lengths[0]) is None:
            raise PosError(400, "POS_BAD_REQUEST", "Некорректная длина тела.")
        length = int(lengths[0])
        if length > MAX_BODY_BYTES:
            raise PosError(413, "POS_BODY_TOO_LARGE", "Тело запроса больше 1 КБ.")
        if self.headers.get_content_type() != "application/json":
            raise PosError(415, "POS_UNSUPPORTED_MEDIA_TYPE", "Требуется application/json.")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise PosError(400, "POS_BAD_REQUEST", "Неполное тело запроса.")
        try:
            body = json.loads(raw)
        except ValueError:
            raise PosError(400, "POS_BAD_REQUEST", "Некорректный JSON.") from None
        token = body.get("token") if isinstance(body, dict) else None
        if not isinstance(token, str) or QR_PATTERN.fullmatch(token) is None:
            raise PosError(400, "QR_TOKEN_MALFORMED", "Некорректный формат QR.")
        self._json(200, {"barcode": self.server.resolve(token)})


class PosServer:
    """Optional independent daemon listener, owned by AgentRuntime.

    listen_port=0 is a test-only injection; configured production ports are 1..65535.
    The module itself neither reads config files nor opens any state files.
    """

    def __init__(
        self,
        settings: AgentSettings,
        *,
        listen_port: int | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._port = settings.agent_pos_listen_port if listen_port is None else listen_port
        self._transport = transport
        self._server: _PosHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int] | None:
        if self._server is None:
            return None
        return str(self._server.server_address[0]), int(self._server.server_address[1])

    def start(self) -> bool:
        if not self.settings.agent_pos_server_enabled:
            return False
        if self._server is not None:
            return True
        try:
            self._server = _PosHTTPServer(
                (self.settings.agent_pos_listen_host, self._port), self.settings, self._transport,
            )
            self._thread = threading.Thread(target=self._serve, name="PosServer", daemon=True)
            self._thread.start()
        except Exception as exc:
            if self._server is not None:
                self._server.server_close()
            self._server = None
            self._thread = None
            logger.error("POS service could not start (type=%s); sync continues", type(exc).__name__)
            return False
        logger.info("POS service started")
        return True

    def _serve(self) -> None:
        assert self._server is not None
        try:
            self._server.serve_forever(poll_interval=0.1)
        except Exception as exc:
            logger.error("POS listener failed (type=%s); sync continues", type(exc).__name__)

    def stop(self) -> None:
        server, thread = self._server, self._thread
        if server is None:
            return
        # shutdown() is only called from outside serve_forever's daemon thread.
        if thread is not None and thread.is_alive():
            server.shutdown()
            thread.join(timeout=2)
        server.server_close()
        self._server = None
        self._thread = None
        logger.info("POS service stopped")
