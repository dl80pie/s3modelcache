"""Multipart upload helper for very large model archives.

Function `upload_large_model_to_hcp` mirrors the helper originally found in
*UploadLargeModel.py* but is adapted for the new package layout.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig

from .model_cache import S3ModelCache

logger = logging.getLogger(__name__)

__all__ = ["upload_large_model_to_hcp"]


def upload_large_model_to_hcp(
    cache: S3ModelCache,
    model_id: str,
    *,
    chunk_size: int = 100 * 1024 * 1024,  # 100 MB
) -> bool:
    """Upload *model_id* to S3 using multipart transfer.

    Parameters
    ----------
    cache:
        An initialised `S3ModelCache` instance (with credentials).
    model_id:
        HF model identifier.
    chunk_size:
        Part/chunk size in bytes (default 100 MB).
    """
    model_path = cache._get_local_path(model_id)
    s3_key = cache._get_s3_key(model_id)

    archive_path = cache.local_cache_dir / f"{model_path.name}.tar.gz"
    if not archive_path.exists():
        cache._compress_model(model_path, archive_path)

    cfg = TransferConfig(
        multipart_threshold=chunk_size,
        multipart_chunksize=chunk_size,
        max_concurrency=10,
        use_threads=True,
    )

    # Reuse credentials from cache's client
    creds = cache.s3_client._request_signer._credentials  # type: ignore[attr-defined]
    s3_client = boto3.client(
        "s3",
        endpoint_url=cache.s3_endpoint,
        aws_access_key_id=creds.access_key,
        aws_secret_access_key=creds.secret_key,
        config=boto3.session.Config(signature_version="s3v4"),
    )

    try:
        logger.info("Starting multipart upload of %s -> %s", archive_path, s3_key)
        s3_client.upload_file(str(archive_path), cache.bucket_name, s3_key, Config=cfg)
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("Multipart upload failed: %s", exc)
        return False
    finally:
        if archive_path.exists():
            archive_path.unlink()
