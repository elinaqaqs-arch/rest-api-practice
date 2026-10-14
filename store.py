import fcntl
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


def update_state(mutator):
    ensure_data_dir()
    DATA_FILE.touch(exist_ok=True)

    with DATA_FILE.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            raw = handle.read()
            state = seed_state() if not raw.strip() else decode_state(raw)
            result = mutator(state)
            handle.seek(0)
            handle.truncate()
            handle.write(encode_state(state))
            handle.flush()
            return result
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def find_product(state: dict, product_id: int) -> dict | None:
    index = product_index(state, product_id)
    if index is None:
        return None
    return state["items"][index]


def product_index(state: dict, product_id: int) -> int | None:
    for index, item in enumerate(state["items"]):
        if item["id"] == product_id:
            return index
    return None


def assert_unique_name(state: dict, name: str, ignore_id: int | None) -> None:
    needle = name.casefold()
    for item in state["items"]:
        if ignore_id is not None and item["id"] == ignore_id:
            continue
        if str(item["name"]).casefold() == needle:
            raise ApiError(
                409,
                "conflict",
                "Товар с таким названием уже есть.",
                [{"field": "name", "message": "Название должно быть уникальным."}],
            )


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
