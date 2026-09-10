from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        content: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.content: dict[str, Any] = content or {"detail": detail}


class NotFoundError(AppError):
    def __init__(self, detail: str = "Not found") -> None:
        super().__init__(404, detail)


class ConflictError(AppError):
    def __init__(self, detail: str, content: dict[str, Any] | None = None) -> None:
        super().__init__(409, detail, content)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(401, detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Not allowed") -> None:
        super().__init__(403, detail)


class ValidationError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(400, detail)


class UnprocessableError(AppError):
    def __init__(self, detail: str, content: dict[str, Any] | None = None) -> None:
        super().__init__(422, detail, content)


class ProviderNotConfiguredError(AppError):
    def __init__(
        self,
        detail: str = "AI provider is not configured",
        content: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(503, detail, content)


class ProviderError(AppError):
    def __init__(
        self,
        detail: str = "AI provider request failed",
        content: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(502, detail, content)
