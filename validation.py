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
