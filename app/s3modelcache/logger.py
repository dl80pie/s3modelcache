"""Logging utilities for S3ModelCache.

Contains `HCPLogger` for structured log output and `LoggedHCPCache`, a thin
mixin that plugs logging into every cache operation.  Implementation mirrors
original *HCPLogger.py*.
"""
from __future__ import annotations

import logging
from datetime import datetime

from .model_cache import S3ModelCache

__all__ = ["HCPLogger", "LoggedHCPCache"]


class HCPLogger:
    """Write cache operations to *hcp_model_cache.log* and stdout."""

    def __init__(self, log_file: str = "hcp_model_cache.log") -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )
        self.logger = logging.getLogger("HCPModelCache")

    def log_operation(self, operation: str, model_id: str, success: bool, details: str | None = None) -> None:
        status = "SUCCESS" if success else "FAILED"
        msg = f"[{datetime.now().isoformat()}] {operation} - {model_id} - {status}"
        if details:
            msg += f" - {details}"
        (self.logger.info if success else self.logger.error)(msg)


class LoggedHCPCache(S3ModelCache):
    """S3ModelCache subclass that records each cache operation via HCPLogger."""

    def __init__(self, *args, **kwargs):  # noqa: D401, ANN001
        super().__init__(*args, **kwargs)
        self._logger = HCPLogger()

    # Override a single public entry-point -> use rest of functionality untouched.
    def cache_model_to_s3(self, model_id: str, force_upload: bool = False):  # type: ignore[override]
        from time import perf_counter

        start = perf_counter()
        success = super().cache_model_to_s3(model_id, force_upload)
        duration = perf_counter() - start
        self._logger.log_operation("CACHE_TO_S3", model_id, success, f"{duration:.2f}s")
        return success
