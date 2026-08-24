"""Error hierarchy shared by every layer.

Lives at the package root so the Artia client and the spreadsheet reader can
import it without depending on each other.
"""

from __future__ import annotations


class WorklogError(Exception):
    """Handled failure with a message meant for the user."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail


class ArtiaError(WorklogError):
    """Failure talking to the Artia API."""


class ConfigError(WorklogError):
    """Missing or invalid configuration."""


class SpreadsheetError(WorklogError):
    """The spreadsheet could not be read or written."""
