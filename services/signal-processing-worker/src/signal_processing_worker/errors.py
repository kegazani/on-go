from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WorkerError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        if self.details:
            return f"{self.code}: {self.message} ({self.details})"
        return f"{self.code}: {self.message}"


class NotFoundError(WorkerError):
    pass


class ConflictError(WorkerError):
    pass


class ValidationError(WorkerError):
    pass
