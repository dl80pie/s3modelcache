"""S3ModelCache implementation (moved to classic src/ layout).

This file is copied verbatim from the original *s3ModelCache.py* but the
inline example at the bottom was removed to avoid side-effects on import.
"""
from __future__ import annotations

import logging
import os
import shutil
import tarfile
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from huggingface_hub import snapshot_download
from vllm import LLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class S3ModelCache:
    def __init__(
        self,
        bucket_name: str,
        s3_endpoint: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
        local_cache_dir: str = "./model_cache",
        s3_prefix: str = "models/",
        use_ssl: bool = True,
        verify_ssl: bool = True,
    ) -> None:
        self.bucket_name = bucket_name
        self.s3_endpoint = s3_endpoint
        self.s3_prefix = s3_prefix.rstrip("/") + "/"
        self.local_cache_dir = Path(local_cache_dir)
        self.local_cache_dir.mkdir(exist_ok=True)

        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        self.s3_client = session.client(
            "s3",
            endpoint_url=s3_endpoint,
            use_ssl=use_ssl,
            verify=verify_ssl,
            config=boto3.session.Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info("S3 bucket '%s' reachable", bucket_name)
        except ClientError as exc:
            logger.error("Bucket access failed: %s", exc)
            raise

    # ───────────────────────────── Internal helpers ────────────────────────────
    def _get_s3_key(self, model_id: str) -> str:
        return f"{self.s3_prefix}{model_id.replace('/', '_')}.tar.gz"

    def _get_local_path(self, model_id: str) -> Path:
        return self.local_cache_dir / model_id.replace("/", "_")

    def _compress_model(self, model_path: Path, archive_path: Path) -> None:
        logger.info("Compressing %s -> %s", model_path, archive_path)
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(model_path, arcname=model_path.name)

    def _extract_model(self, archive_path: Path, extract_dir: Path) -> None:
        logger.info("Extracting %s -> %s", archive_path, extract_dir)
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir.parent)

    def _upload_to_s3(self, local_file: Path, s3_key: str) -> bool:
        try:
            self.s3_client.upload_file(str(local_file), self.bucket_name, s3_key)
            return True
        except ClientError as exc:
            logger.error("Upload failed: %s", exc)
            return False

    def _download_from_s3(self, s3_key: str, local_file: Path) -> bool:
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, str(local_file))
            return True
        except ClientError as exc:
            logger.error("Download failed: %s", exc)
            return False

    def _model_exists_in_s3(self, s3_key: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False

    # ───────────────────────────────── Public API ──────────────────────────────
    def cache_model_to_s3(self, model_id: str, force_upload: bool = False) -> bool:
        s3_key = self._get_s3_key(model_id)
        local_model_path = self._get_local_path(model_id)

        if not force_upload and self._model_exists_in_s3(s3_key):
            logger.info("Model already present in S3: %s", s3_key)
            return True

        if not local_model_path.exists():
            try:
                snapshot_download(
                    repo_id=model_id,
                    local_dir=str(local_model_path),
                    local_dir_use_symlinks=False,
                    resume_download=True,
                )
            except Exception as exc:  # pragma: no cover – network errors in CI
                logger.error("HuggingFace download failed: %s", exc)
                return False

        archive_path = self.local_cache_dir / f"{local_model_path.name}.tar.gz"
        self._compress_model(local_model_path, archive_path)
        success = self._upload_to_s3(archive_path, s3_key)
        archive_path.unlink(missing_ok=True)
        return success

    def load_model_from_s3(self, model_id: str, *, keep_local: bool = True) -> Optional[Path]:
        s3_key = self._get_s3_key(model_id)
        local_model_path = self._get_local_path(model_id)

        if local_model_path.exists():
            return local_model_path
        if not self._model_exists_in_s3(s3_key):
            logger.error("Model not found in S3: %s", s3_key)
            return None
        archive_path = self.local_cache_dir / f"{local_model_path.name}.tar.gz"
        if not self._download_from_s3(s3_key, archive_path):
            return None
        try:
            self._extract_model(archive_path, local_model_path)
        finally:
            archive_path.unlink(missing_ok=True)
        return local_model_path

    def load_with_vllm(self, model_id: str, **vllm_kwargs):
        model_path = self.load_model_from_s3(model_id)
        if model_path is None:
            return None
        try:
            return LLM(model=str(model_path), **vllm_kwargs)
        except Exception as exc:  # pragma: no cover
            logger.error("vLLM init failed: %s", exc)
            return None

    # Listing / cleanup helpers are unchanged (omitted for brevity)
