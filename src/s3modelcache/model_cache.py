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

try:
    from vllm import LLM
except ImportError:
    LLM = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class S3ModelCache:
    """Cache HuggingFace models locally and in an S3-compatible object store.

    The directory used for the *local* cache can be configured in three ways, in
    order of precedence:

    1. By passing the ``local_cache_dir`` argument explicitly when
       instantiating :class:`S3ModelCache`.
    2. By setting the ``MODEL_CACHE_DIR`` environment variable.
    3. Falling back to the default value ``"./model_cache"``.

    You can also pass ``root_ca_path`` to specify a custom root CA bundle for
    HTTPS connections to your S3 endpoint (e.g. when using self-signed certs).
    """
    def __init__(
        self,
        bucket_name: str,
        s3_endpoint: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
        local_cache_dir: Optional[str] = None,
        s3_prefix: str = "models/",
        use_ssl: bool = True,
        verify_ssl: bool = True,
        root_ca_path: Optional[str] = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.s3_endpoint = s3_endpoint
        self.s3_prefix = s3_prefix.rstrip("/") + "/"
        # Resolve the local cache directory with the following precedence:
        #   1. Explicit `local_cache_dir` argument
        #   2. Environment variable `MODEL_CACHE_DIR`
        #   3. Default "./model_cache"
        _cache_dir = local_cache_dir or os.getenv("MODEL_CACHE_DIR", "./model_cache")
        self.local_cache_dir = Path(_cache_dir)
        self.local_cache_dir.mkdir(exist_ok=True)

        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        # If a custom root CA bundle is provided, use it for SSL verification
        _verify_param = root_ca_path if root_ca_path else verify_ssl

        self.s3_client = session.client(
            "s3",
            endpoint_url=s3_endpoint,
            use_ssl=use_ssl,
            verify=_verify_param,
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
        """Compress model directory to tar.gz with memory-efficient streaming.
        
        This method processes files one by one to avoid loading large models
        entirely into memory, preventing crashes with multi-GB models.
        """
        logger.info("Compressing %s -> %s", model_path, archive_path)
        
        with tarfile.open(archive_path, "w:gz") as tar:
            # Add files one by one to control memory usage
            for file_path in model_path.rglob("*"):
                if file_path.is_file():
                    # Calculate the archive name (relative path within the model)
                    arcname = model_path.name / file_path.relative_to(model_path)
                    
                    # Add file with streaming to avoid loading entire file into memory
                    tar.add(file_path, arcname=str(arcname))
                    
                    # Log progress for large operations
                    if file_path.stat().st_size > 100 * 1024 * 1024:  # > 100MB
                        logger.info("Added large file: %s (%.1f MB)", 
                                  file_path.name, file_path.stat().st_size / (1024*1024))

    def _extract_model(self, archive_path: Path, extract_dir: Path) -> None:
        """Extract model archive with memory-efficient streaming.
        
        This method extracts files one by one to avoid memory issues
        with large model archives.
        """
        logger.info("Extracting %s -> %s", archive_path, extract_dir)
        
        with tarfile.open(archive_path, "r:gz") as tar:
            # Extract files one by one for better memory control
            for member in tar.getmembers():
                if member.isfile():
                    # Log progress for large files
                    if member.size > 100 * 1024 * 1024:  # > 100MB
                        logger.info("Extracting large file: %s (%.1f MB)", 
                                  member.name, member.size / (1024*1024))
                    
                    tar.extract(member, extract_dir.parent)
                elif member.isdir():
                    # Create directories
                    tar.extract(member, extract_dir.parent)

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
        if LLM is None:
            logger.error("vLLM is not installed. Install it with: pip install vllm")
            return None
            
        model_path = self.load_model_from_s3(model_id)
        if model_path is None:
            return None
        try:
            return LLM(model=str(model_path), **vllm_kwargs)
        except Exception as exc:  # pragma: no cover
            logger.error("vLLM init failed: %s", exc)
            return None

    # ───────────────────────────── Cache utilities ────────────────────────────
    def list_cached_models(self, source: str = "local") -> list[str]:
        """Return a list of cached model IDs.

        Parameters
        ----------
        source : {"local", "s3"}
            Where to list the models from. "local" inspects the local cache
            directory, "s3" queries the configured bucket.
        """
        source = source.lower()
        if source == "local":
            return [p.name for p in self.local_cache_dir.iterdir() if p.is_dir()]
        if source == "s3":
            paginator = self.s3_client.get_paginator("list_objects_v2")
            models: list[str] = []
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.s3_prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith(".tar.gz"):
                        models.append(key[len(self.s3_prefix):-7])  # strip prefix + ext
            return models
        raise ValueError("source must be 'local' or 's3'")

    def delete_cached_model(self, model_id: str, *, local: bool = True, s3: bool = False) -> bool:
        """Delete cached model locally and/or from S3.

        Returns ``True`` if at least one deletion succeeded, ``False`` otherwise.
        """
        success = False
        if local:
            local_path = self._get_local_path(model_id)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)
                success = True
        if s3:
            key = self._get_s3_key(model_id)
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
                success = True
            except ClientError as exc:
                logger.error("Failed to delete %s from S3: %s", key, exc)
        return success
