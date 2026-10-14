class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []
        self.headers = headers or {}

    def body(self) -> dict:
        error: dict = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"error": error}
