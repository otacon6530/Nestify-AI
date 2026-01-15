from __future__ import annotations
import logging
from ..functions.logger_init import init_jsonl_logger, log_event


class Logger:
    def __init__(self):
        self._logger: logging.Logger = init_jsonl_logger()

    def log(self, level: str, message: str, **extra):
        """
        Log a message with the given level and optional extra fields.
        """
        log_event(self._logger, level, message, **extra)

    # Expose underlying logger if needed
    @property
    def raw(self) -> logging.Logger:
        return self._logger
