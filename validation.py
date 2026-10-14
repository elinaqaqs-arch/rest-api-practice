import re

from errors import ApiError


def validate_product(data: dict, partial: bool) -> dict:
    details: list[dict[str, str]] = []
    fields: dict[str, str | int] = {}
    allowed = {"name", "price", "stock"}
    unknown = [key for key in data if key not in allowed]

    for field in unknown:
        details.append({"field": field, "message": "Неизвестное поле."})

    known = [key for key in data if key in allowed]
    if partial and not known and not unknown:
        details.append(
            {
                "field": "body",
                "message": "Передай хотя бы одно поле: name, price или stock.",
            }
        )

    validate_name(data, required=not partial, details=details, fields=fields)
    validate_int_field(data, "price", required=not partial, minimum=0, maximum=10000, details=details, fields=fields)
    validate_int_field(data, "stock", required=not partial, minimum=0, maximum=100, details=details, fields=fields)

    if details:
        raise ApiError(422, "validation_error", "Проверь поля запроса.", details)

    return fields


def validate_name(data: dict, required: bool, details: list[dict[str, str]], fields: dict) -> None:
    if "name" not in data:
        if required:
            details.append({"field": "name", "message": "Поле обязательно."})
        return

    value = data["name"]
    if not isinstance(value, str):
        details.append({"field": "name", "message": "Должно быть строкой от 2 до 40 символов."})
        return

    name = value.strip()
    if len(name) < 2 or len(name) > 40:
        details.append({"field": "name", "message": "Должно быть строкой от 2 до 40 символов."})
        return

    fields["name"] = name


def validate_int_field(
    data: dict,
    field: str,
    required: bool,
    minimum: int,
    maximum: int,
    details: list[dict[str, str]],
    fields: dict,
) -> None:
    if field not in data:
        if required:
            details.append({"field": field, "message": "Поле обязательно."})
        return

    value = data[field]
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        details.append(
            {
                "field": field,
                "message": f"Должно быть целым числом от {minimum} до {maximum}.",
            }
        )
        return

    fields[field] = value


def validate_product_query(query: dict[str, list[str]]) -> dict[str, int | None]:
    details: list[dict[str, str]] = []

    for key in query:
        if key not in {"min_price", "max_price", "limit"}:
            details.append({"field": key, "message": "Неизвестный query-параметр."})

    min_price = read_bound(query, "min_price", 0, 10000, details)
    max_price = read_bound(query, "max_price", 0, 10000, details)
    limit = read_bound(query, "limit", 1, 20, details)

    if min_price is not None and max_price is not None and min_price > max_price:
        details.append(
            {
                "field": "min_price",
                "message": "min_price не может быть больше max_price.",
            }
        )

    if details:
        raise ApiError(422, "validation_error", "Проверь query-параметры.", details)

    return {"min_price": min_price, "max_price": max_price, "limit": limit}


def read_bound(
    query: dict[str, list[str]],
    key: str,
    minimum: int,
    maximum: int,
    details: list[dict[str, str]],
) -> int | None:
    if key not in query:
        return None

    value = query[key][0] if len(query[key]) == 1 else ""
    if re.fullmatch(r"0|[1-9]\d*", value) is None:
        details.append(
            {
                "field": key,
                "message": f"Должно быть целым числом от {minimum} до {maximum}.",
            }
        )
        return None

    number = int(value)
    if number < minimum or number > maximum:
        details.append(
            {
                "field": key,
                "message": f"Должно быть целым числом от {minimum} до {maximum}.",
            }
        )
        return None

    return number
