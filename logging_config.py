"""Structured JSON logging for production."""

import json
import logging
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        obj = {
            "ts": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "module": record.module,
        }
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj)


def setup_logging(level: str = "INFO"):
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(
        getattr(logging, level.upper(), logging.INFO)
    )
