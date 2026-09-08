class AppError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    def __init__(self, detail: str = "Not found") -> None:
        super().__init__(404, detail)


class ConflictError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(409, detail)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(401, detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Not allowed") -> None:
        super().__init__(403, detail)
