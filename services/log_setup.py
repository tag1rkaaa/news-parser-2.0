"""Shared logging setup used by all entry points.

Usage:
    from services.log_setup import setup_logging
    setup_logging("starter")

Creates a rotating file handler at ``./logs/{service_name}.log`` and a console
handler. The formatter includes any ``extra=`` fields passed to log calls.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path


class ExtraFieldsFormatter(logging.Formatter):
    """Appends ``extra`` dict fields to the formatted message."""

    _BASE_ATTRS: frozenset[str] = frozenset()

    def __init__(self, fmt: str | None = None) -> None:
        super().__init__(fmt or "%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        if not self._BASE_ATTRS:
            dummy = logging.LogRecord("", 0, "", 0, "", (), None)
            base = set(vars(dummy))
            base.update(("message", "asctime", "exc_text", "stack_info"))
            ExtraFieldsFormatter._BASE_ATTRS = frozenset(base)

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        extra = {k: v for k, v in record.__dict__.items()
                 if k not in self._BASE_ATTRS and not k.startswith("_")}
        if extra:
            parts = " ".join(f"{k}={v!r}" for k, v in extra.items())
            msg = f"{msg} | {parts}"
        return msg


_LOG_DIR = Path(os.getcwd()) / "logs"


def _get_env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def setup_logging(
    service_name: str,
    *,
    level: str | None = None,
    log_dir: str | None = None,
) -> None:
    """Configure root logger with console + rotating file handlers.

    Parameters
    ----------
    service_name:
        Used as the log file name: ``{log_dir}/{service_name}.log``.
    level:
        Log level string (e.g. ``"DEBUG"``). Falls back to ``LOG_LEVEL`` env
        var, then ``"INFO"``.
    log_dir:
        Directory for log files. Falls back to ``os.getcwd() / "logs"``.
    """
    logger = logging.getLogger()
    logger.setLevel(level or _get_env("LOG_LEVEL", "WARNING"))

    fmt = ExtraFieldsFormatter()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir_path = Path(log_dir) if log_dir else _LOG_DIR
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_file = log_dir_path / f"{service_name}.log"

    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=int(_get_env("LOG_ROTATION_BYTES", str(10 * 1024 * 1024))),
        backupCount=int(_get_env("LOG_ROTATION_BACKUPS", "5")),
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
