"""Structured application errors. Every error carries a stable code and an actionable message."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_FAILED"


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class PermissionDenied(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"


class AuthRequired(AppError):
    status_code = 401
    code = "AUTH_REQUIRED"


class ImmutableRecord(Conflict):
    code = "IMMUTABLE_RECORD"


class ApprovalBlocked(AppError):
    """Raised when an action is blocked by the human-approval policy."""

    status_code = 409
    code = "APPROVAL_BLOCKED"
