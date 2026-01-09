import logging
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path
from .logger_path import get_log_dir


def init_jsonl_logger(name: str = "nestify", max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    log_path: Path = get_log_dir() / "log.jsonl"
    handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")

    class JsonlFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload = {
                "datetime": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "file": record.pathname,
                "line": record.lineno,
                "message": record.getMessage(),
            }
            if hasattr(record, "extra") and isinstance(record.extra, dict):
                payload.update(record.extra)
            return json.dumps(payload)

    handler.setFormatter(JsonlFormatter())
    logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, level: str, message: str, **extra):
    lvl = getattr(logging, level.upper(), logging.INFO)
    logger.log(lvl, message, extra={"extra": extra} if extra else {"extra": {}})
