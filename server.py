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
from urllib.parse import parse_qs, urlparse

from auth import MENTOR_TOKEN, STUDENT_TOKEN, require_user
from errors import ApiError
from store import assert_unique_name, load_state, product_index, seed_state, update_state
from validation import validate_product, validate_product_query

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
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        self.query = parse_qs(parsed.query, keep_blank_values=True)

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
                        "tokens": {
                            "student": STUDENT_TOKEN,
                            "mentor": MENTOR_TOKEN,
                        },
                        "auth_header": "Authorization: Bearer <token>",
                        "product_rules": {
                            "name": "строка от 2 до 40 символов, уникальная без учета регистра",
                            "price": "целое число от 0 до 10000",
                            "stock": "целое число от 0 до 100",
                        },
                        "endpoints": [
                            "GET /health",
                            "GET /echo",
                            "GET /products",
                            "GET /products/{id}",
                            "POST /products",
                            "PUT /products/{id}",
                            "PATCH /products/{id}",
                            "DELETE /products/{id}",
                            "POST /reset",
                            "GET /demo/server-error",
                        ],
                        "practice": [
                            "GET /health и посмотри код и тело ответа.",
                            "GET /echo с заголовком X-Request-Id: demo-1. Тот же id вернется в ответе.",
                            "GET /products и GET /products/1.",
                            "GET /products/999 ожидает 404. GET /products/abc ожидает 400.",
                            "GET /products?limit=20 работает. limit=0 и limit=21 ожидают 422.",
                            "POST /products без Authorization ожидает 401. С токеном student-token и верным JSON ожидает 201.",
                            "Повтори то же name: ожидается 409. Name из 1 символа и из 41 символа ожидают 422.",
                            "POST без Content-Type: application/json ожидает 415. Пустое или сломанное тело ожидает 400.",
                            "PATCH /products/1 меняет только price. PUT без одного из полей ожидает 422.",
                            "DELETE /products/1 с student-token ожидает 403. С mentor-token ожидает 204.",
                            "GET /demo/server-error ожидает 500. POST /reset возвращает начальные товары.",
                        ],
                    }
                },
            )
            return

        if path == "/health" and method == "GET":
            self.respond(200, {"data": {"status": "ok", "service": "rest-practice"}})
            return

        if path == "/echo":
            self.show_echo(method, path)
            return

        if path == "/reset" and method == "POST":
            self.reset_products()
            return

        if path == "/demo/server-error" and method == "GET":
            raise ApiError(
                500,
                "server_error",
                "Учебная ошибка сервера. Процесс не упал: этот маршрут всегда отвечает 500.",
            )

        if path == "/products" and method == "GET":
            self.list_products()
            return

        if path == "/products" and method == "POST":
            self.create_product()
            return

        product_match = re.fullmatch(r"/products/([^/]+)", path)
        if product_match:
            self.route_one_product(method, product_match.group(1))
            return

        if path in {"/", "/health", "/demo/server-error"}:
            self.method_not_allowed("GET")

        if path == "/reset":
            self.method_not_allowed("POST")

        if path == "/products":
            self.method_not_allowed("GET, POST")

        raise ApiError(404, "not_found", "Маршрут не найден.")

    def list_products(self) -> None:
        filters = validate_product_query(self.query)
        state = load_state()
        items = sorted(state["items"], key=lambda item: item["id"])

        if filters["min_price"] is not None:
            items = [item for item in items if item["price"] >= filters["min_price"]]
        if filters["max_price"] is not None:
            items = [item for item in items if item["price"] <= filters["max_price"]]
        if filters["limit"] is not None:
            items = items[: filters["limit"]]

        self.respond(
            200,
            {
                "data": items,
                "meta": {"count": len(items), "total": len(state["items"])},
            },
        )

    def show_echo(self, method: str, path: str) -> None:
        raw = self.read_raw_body()
        query = {key: values[0] if len(values) == 1 else values for key, values in self.query.items()}
        self.respond(
            200,
            {
                "data": {
                    "method": method,
                    "path": path,
                    "query": query,
                    "headers": {key: value for key, value in self.headers.items()},
                    "body": raw.decode("utf-8", errors="replace") if raw else None,
                }
            },
        )

    def reset_products(self) -> None:
        state = seed_state()

        def mutate(current: dict) -> None:
            current.clear()
            current.update(state)

        update_state(mutate)
        self.respond(200, {"data": state["items"], "meta": {"count": len(state["items"])}})

    def route_one_product(self, method: str, raw_id: str) -> None:
        product_id = self.parse_product_id(raw_id)

        if method == "GET":
            self.show_product(product_id)
            return
        if method == "PUT":
            self.replace_product(product_id)
            return
        if method == "PATCH":
            self.update_product(product_id)
            return
        if method == "DELETE":
            self.delete_product(product_id)
            return

        self.method_not_allowed("GET, PUT, PATCH, DELETE")

    def show_product(self, product_id: int) -> None:
        state = load_state()
        index = product_index(state, product_id)
        if index is None:
            raise ApiError(404, "not_found", "Товар не найден.")
        self.respond(200, {"data": state["items"][index]})

    def create_product(self) -> None:
        require_user(self.headers.get("Authorization", ""))
        fields = validate_product(self.read_json_object(), partial=False)
        created = update_state(lambda state: self.insert_product(state, fields))
        self.respond(201, {"data": created}, {"Location": f"{self.base_url()}/products/{created['id']}"})

    def replace_product(self, product_id: int) -> None:
        require_user(self.headers.get("Authorization", ""))
        fields = validate_product(self.read_json_object(), partial=False)
        product = update_state(lambda state: self.write_product(state, product_id, fields, partial=False))
        self.respond(200, {"data": product})

    def update_product(self, product_id: int) -> None:
        require_user(self.headers.get("Authorization", ""))
        fields = validate_product(self.read_json_object(), partial=True)
        product = update_state(lambda state: self.write_product(state, product_id, fields, partial=True))
        self.respond(200, {"data": product})

    def delete_product(self, product_id: int) -> None:
        require_user(self.headers.get("Authorization", ""), role="mentor")

        def mutate(state: dict) -> None:
            index = product_index(state, product_id)
            if index is None:
                raise ApiError(404, "not_found", "Товар не найден.")
            del state["items"][index]

        update_state(mutate)
        self.respond(204, None)

    def insert_product(self, state: dict, fields: dict) -> dict:
        assert_unique_name(state, fields["name"], None)
        product = {
            "id": state["next_id"],
            "name": fields["name"],
            "price": fields["price"],
            "stock": fields["stock"],
        }
        state["next_id"] += 1
        state["items"].append(product)
        return product

    def write_product(self, state: dict, product_id: int, fields: dict, partial: bool) -> dict:
        index = product_index(state, product_id)
        if index is None:
            raise ApiError(404, "not_found", "Товар не найден.")

        current = state["items"][index]
        if partial:
            product = {**current, **fields}
        else:
            product = {
                "id": product_id,
                "name": fields["name"],
                "price": fields["price"],
                "stock": fields["stock"],
            }

        if "name" in fields:
            assert_unique_name(state, product["name"], product_id)

        state["items"][index] = product
        return product

    def read_json_object(self) -> dict:
        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise ApiError(
                415,
                "unsupported_media_type",
                "Заголовок Content-Type должен быть application/json.",
            )

        raw = self.read_raw_body()
        if not raw.strip():
            raise ApiError(400, "bad_request", "Тело запроса пустое. Ожидается JSON-объект.")

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ApiError(400, "bad_request", "Тело запроса не является корректным JSON.") from error

        if not isinstance(decoded, dict):
            raise ApiError(400, "bad_request", 'JSON должен быть объектом, например {"name": "Pen"}.')

        return decoded

    def read_raw_body(self) -> bytes:
        length_header = self.headers.get("Content-Length", "0")
        try:
            length = int(length_header)
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def parse_product_id(self, raw_id: str) -> int:
        if re.fullmatch(r"[1-9]\d{0,8}", raw_id) is None:
            raise ApiError(400, "bad_request", "Id товара должен быть целым числом больше 0.")
        return int(raw_id)

    def base_url(self) -> str:
        host = self.headers.get("Host", f"{HOST}:{PORT}")
        if re.fullmatch(r"[A-Za-z0-9.-]+(:\d+)?", host) is None:
            host = f"{HOST}:{PORT}"
        return f"http://{host}"

    def method_not_allowed(self, allow: str) -> None:
        raise ApiError(
            405,
            "method_not_allowed",
            "Этот метод для этого маршрута не поддерживается.",
            headers={"Allow": allow},
        )

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
