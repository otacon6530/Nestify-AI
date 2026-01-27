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

    def error(self, message: str, **extra):
        self.log("ERROR", message, **extra)

    def warning(self, message: str, **extra):
        self.log("WARNING", message, **extra)

    def info(self, message: str, **extra):
        self.log("INFO", message, **extra)

    # Expose underlying logger if needed
    @property
    def raw(self) -> logging.Logger:
        return self._logger
