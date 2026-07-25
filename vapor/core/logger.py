"""
Centralized logging configuration for Vapor ROM Manager.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


class ContextFilter(logging.Filter):
    """Add context (device, operation) to log records."""

    def __init__(self):
        super().__init__()
        self.context = {}

    def filter(self, record):
        if self.context:
            if "device" in self.context:
                record.device = self.context["device"]
            if "operation" in self.context:
                record.operation = self.context["operation"]
        return True


# Global context filter
_context_filter = ContextFilter()


def set_context(**kwargs):
    """Set contextual information for logging (device, operation, etc.)."""
    _context_filter.context.update(kwargs)


def clear_context():
    """Clear contextual information."""
    _context_filter.context.clear()


def setup_logger(name, log_file=None, level=logging.INFO):
    """
    Setup and return a logger with console and optional file output.

    Args:
        name: Logger name (usually __name__)
        log_file: Optional path to log file
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addFilter(_context_filter)

    # Console handler
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Format: [TIMESTAMP] [LEVEL] [DEVICE] [OPERATION] message
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(device)s | %(operation)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
