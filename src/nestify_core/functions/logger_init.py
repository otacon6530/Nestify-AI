import logging
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path


def init_jsonl_logger(name: str = "nestify", max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # Remove all handlers to avoid duplicate or blocking handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)
    log_path: Path = Path.cwd() / "log.txt"
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
