from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] | None = None


class NotFoundError(ApiError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=404, code=code, message=message, details=details)


class ConflictError(ApiError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=409, code=code, message=message, details=details)


class ValidationError(ApiError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=422, code=code, message=message, details=details)
