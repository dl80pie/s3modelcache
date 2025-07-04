import tempfile
import tarfile
import os
from pathlib import Path
from unittest import mock

import pytest

from s3modelcache import S3ModelCache


@pytest.fixture
def cache(tmp_path):
    """Return a S3ModelCache instance with a temporary local cache dir and mocked s3 client."""
    with mock.patch("boto3.Session.client") as mocked_client:
        mocked_client.return_value = mock.MagicMock()
        c = S3ModelCache(
        bucket_name="unit-test-bucket",
        s3_endpoint="https://dummy-endpoint",
        aws_access_key_id="key",
        aws_secret_access_key="secret",
        local_cache_dir=str(tmp_path),
        verify_ssl=False,
    )
        return c


def test_key_and_path_generation(cache):
    model_id = "huggingface/bert-base-uncased"
    expected_key = "models/huggingface_bert-base-uncased.tar.gz"
    expected_path = cache.local_cache_dir / "huggingface_bert-base-uncased"

    assert cache._get_s3_key(model_id) == expected_key
    assert cache._get_local_path(model_id) == expected_path


def test_compress_and_extract_roundtrip(cache):
    # Create dummy model directory with a file
    model_dir = cache._get_local_path("dummy/model")
    model_dir.mkdir(parents=True)
    file_path = model_dir / "weights.bin"
    file_path.write_bytes(b"\x00" * 128)

    archive_path = cache.local_cache_dir / "archive.tar.gz"

    # Compress
    cache._compress_model(model_dir, archive_path)
    assert archive_path.exists()

    # Extract to new dir
    extract_dir = cache.local_cache_dir / "extracted"
    extract_dir.mkdir()
    cache._extract_model(archive_path, extract_dir)

    extracted_file = extract_dir.parent / model_dir.name / "weights.bin"
    assert extracted_file.exists()
    assert extracted_file.read_bytes() == b"\x00" * 128


def test_upload_download_calls(cache):
    model_id = "test/model"
    model_dir = cache._get_local_path(model_id)
    model_dir.mkdir(parents=True)
    dummy_tar = cache.local_cache_dir / "dummy.tar.gz"
    with tarfile.open(dummy_tar, "w:gz") as tar:
        tar.add(model_dir, arcname=model_dir.name)

    # Replace internal helpers to avoid real compression
    with mock.patch.object(cache, "_compress_model", return_value=None), \
         mock.patch.object(cache, "_get_local_path", return_value=model_dir):

        # Call upload; should trigger s3_client.upload_file
        cache._upload_to_s3(dummy_tar, "some/key")
        cache.s3_client.upload_file.assert_called_once()

        # Call download; should trigger s3_client.download_file
        cache._download_from_s3("some/key", dummy_tar)
        cache.s3_client.download_file.assert_called_once()
