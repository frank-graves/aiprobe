"""Custom exception hierarchy for aiprobe."""

from __future__ import annotations


class AiprobeError(Exception):
    """Base exception for all aiprobe errors."""

    exit_code: int = 1
    hint: str | None = None

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint or self.hint


class ConfigError(AiprobeError):
    """Raised when the configuration is invalid."""

    exit_code = 3


class NetworkError(AiprobeError):
    """Raised when a network operation fails."""

    exit_code = 1


class ChallengeBlockedError(AiprobeError):
    """Raised when an anti-bot system blocks the request."""

    exit_code = 1


class AuthError(AiprobeError):
    """Raised when authentication fails."""

    exit_code = 1


class ParseError(AiprobeError):
    """Raised when parsing a response fails."""

    exit_code = 1


class DriftDetectedError(AiprobeError):
    """Raised when drift is detected during validation."""

    exit_code = 2


def exit_code_for(exc: Exception) -> int:
    """Map an exception to its corresponding exit code."""
    if isinstance(exc, AiprobeError):
        return exc.exit_code
    return 1
