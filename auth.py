import re

from errors import ApiError

STUDENT_TOKEN = "student-token"
MENTOR_TOKEN = "mentor-token"

USERS = {
    STUDENT_TOKEN: {"name": "student", "role": "student"},
    MENTOR_TOKEN: {"name": "mentor", "role": "mentor"},
}


def require_user(header: str, role: str | None = None) -> dict:
    if header.strip() == "":
        raise unauthorized("Нужен заголовок Authorization: Bearer <token>.")

    match = re.fullmatch(r"Bearer\s+(\S+)", header.strip())
    if match is None:
        raise unauthorized("Формат заголовка: Authorization: Bearer <token>.")

    user = USERS.get(match.group(1))
    if user is None:
        raise unauthorized("Неизвестный token.")

    if role is not None and user["role"] != role:
        raise ApiError(403, "forbidden", f"Это действие может выполнить только роль {role}.")

    return user


def unauthorized(message: str) -> ApiError:
    return ApiError(401, "unauthorized", message, headers={"WWW-Authenticate": "Bearer"})
