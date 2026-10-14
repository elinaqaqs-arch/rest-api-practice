#!/usr/bin/env python3
"""Локальный REST API для тренировки запросов в Postman.

Запуск:
    python3 server.py
"""

from __future__ import annotations

import json
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from errors import ApiError
from store import find_product, load_state

HOST = "127.0.0.1"
PORT = 8080


class Handler(BaseHTTPRequestHandler):
    server_version = "RestPractice/1.0"

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def do_PUT(self) -> None:
        self.dispatch("PUT")

    def do_PATCH(self) -> None:
        self.dispatch("PATCH")

    def do_DELETE(self) -> None:
        self.dispatch("DELETE")

    def do_OPTIONS(self) -> None:
        self.dispatch("OPTIONS")

    def dispatch(self, method: str) -> None:
        try:
            self.route(method)
        except ApiError as error:
            self.respond(error.status, error.body(), error.headers)
        except Exception:
            self.respond(
                500,
                {
                    "error": {
                        "code": "server_error",
                        "message": "Внутренняя ошибка сервера.",
                    }
                },
            )

    def route(self, method: str) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if method == "OPTIONS":
            self.respond(204, None, {"Allow": "GET, POST, PUT, PATCH, DELETE, OPTIONS"})
            return

        if path == "/" and method == "GET":
            self.respond(
                200,
                {
                    "data": {
                        "name": "REST practice API",
                        "base_url": f"http://{HOST}:{PORT}",
                        "endpoints": [
                            "GET /health",
                            "GET /products",
                            "GET /products/{id}",
                        ],
                    }
                },
            )
            return

        if path == "/health" and method == "GET":
            self.respond(200, {"data": {"status": "ok", "service": "rest-practice"}})
            return

        if path == "/products" and method == "GET":
            self.list_products()
            return

        product_match = re.fullmatch(r"/products/([^/]+)", path)
        if product_match:
            self.show_product_route(method, product_match.group(1))
            return

        if path in {"/", "/health", "/products"}:
            raise ApiError(
                405,
                "method_not_allowed",
                "Этот метод для этого маршрута не поддерживается.",
                headers={"Allow": "GET"},
            )

        raise ApiError(404, "not_found", "Маршрут не найден.")

    def list_products(self) -> None:
        state = load_state()
        items = sorted(state["items"], key=lambda item: item["id"])
        self.respond(
            200,
            {
                "data": items,
                "meta": {"count": len(items), "total": len(state["items"])},
            },
        )

    def show_product_route(self, method: str, raw_id: str) -> None:
        if method != "GET":
            raise ApiError(
                405,
                "method_not_allowed",
                "Этот метод для этого маршрута не поддерживается.",
                headers={"Allow": "GET"},
            )

        self.respond(200, {"data": self.product_or_404(self.parse_product_id(raw_id))})

    def parse_product_id(self, raw_id: str) -> int:
        if re.fullmatch(r"[1-9]\d{0,8}", raw_id) is None:
            raise ApiError(400, "bad_request", "Id товара должен быть целым числом больше 0.")
        return int(raw_id)

    def product_or_404(self, product_id: int) -> dict:
        product = find_product(load_state(), product_id)
        if product is None:
            raise ApiError(404, "not_found", "Товар не найден.")
        return product

    def respond(self, status: int, body: dict | None, extra_headers: dict[str, str] | None = None) -> None:
        payload = b""
        if body is not None and status != 204:
            payload = json.dumps(body, ensure_ascii=False, indent=4).encode("utf-8") + b"\n"

        self.send_response(status)
        self.send_header("X-Request-Id", self.request_id())
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-Id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Expose-Headers", "Location, X-Request-Id")

        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)

        if payload:
            self.send_header("Content-Type", "application/json; charset=utf-8")

        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()

        if payload:
            self.wfile.write(payload)

    def request_id(self) -> str:
        if hasattr(self, "_request_id"):
            return self._request_id

        incoming = self.headers.get("X-Request-Id", "").strip()
        if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", incoming):
            self._request_id = incoming
        else:
            self._request_id = secrets.token_hex(8)

        return self._request_id


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Сервер: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
