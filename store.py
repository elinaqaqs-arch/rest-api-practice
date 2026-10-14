import json
from pathlib import Path

from errors import ApiError

DATA_FILE = Path(__file__).resolve().parent / "data" / "products.json"


def seed_state() -> dict:
    return {
        "next_id": 4,
        "items": [
            {"id": 1, "name": "Notebook", "price": 10, "stock": 5},
            {"id": 2, "name": "Pen", "price": 1, "stock": 100},
            {"id": 3, "name": "Lamp", "price": 40, "stock": 2},
        ],
    }


def load_state() -> dict:
    ensure_data_dir()
    if not DATA_FILE.exists():
        state = seed_state()
        DATA_FILE.write_text(encode_state(state), encoding="utf-8")
        return state

    return decode_state(DATA_FILE.read_text(encoding="utf-8"))


def find_product(state: dict, product_id: int) -> dict | None:
    for item in state["items"]:
        if item["id"] == product_id:
            return item
    return None


def decode_state(raw: str) -> dict:
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ApiError(
            500,
            "server_error",
            "Локальное хранилище повреждено. Вызови POST /reset.",
        ) from error

    if not isinstance(state, dict) or not isinstance(state.get("items"), list) or not isinstance(state.get("next_id"), int):
        raise ApiError(
            500,
            "server_error",
            "Локальное хранилище имеет неожиданную форму. Вызови POST /reset.",
        )

    return state


def encode_state(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, indent=4) + "\n"


def ensure_data_dir() -> None:
    directory = DATA_FILE.parent
    if not directory.is_dir():
        directory.mkdir(parents=True, exist_ok=True)
