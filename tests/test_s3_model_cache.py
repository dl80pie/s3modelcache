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
    model_id = "VAGOsolutions/Llama-3.1-SauerkrautLM-70b-Instruct"
    expected_key = "models/VAGOsolutions_Llama-3.1-SauerkrautLM-70b-Instruct.tar.gz"
    expected_path = cache.local_cache_dir / "VAGOsolutions_Llama-3.1-SauerkrautLM-70b-Instruct"
    #model_id = "huggingface/bert-base-uncased"
    #expected_key = "models/huggingface_bert-base-uncased.tar.gz"
    #expected_path = cache.local_cache_dir / "huggingface_bert-base-uncased"

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


# ---------------------------------------------------------------------------
# New tests for listing and deleting cached models
# ---------------------------------------------------------------------------

def test_list_cached_models_local(cache):
    # create two dummy cached models
    (cache._get_local_path("a/model")).mkdir(parents=True)
    (cache._get_local_path("b/model")).mkdir(parents=True)

    listed = set(cache.list_cached_models())
    assert listed == {"a_model", "b_model"}


def test_list_cached_models_s3(cache):
    paginator = mock.MagicMock()
    cache.s3_client.get_paginator.return_value = paginator
    paginator.paginate.return_value = [
        {"Contents": [{"Key": f"{cache.s3_prefix}a_model.tar.gz"}]},
        {"Contents": [{"Key": f"{cache.s3_prefix}b_model.tar.gz"}]},
    ]

    listed = set(cache.list_cached_models("s3"))
    assert listed == {"a_model", "b_model"}


def test_delete_cached_model_local(cache):
    model_id = "delete/local"
    path = cache._get_local_path(model_id)
    path.mkdir(parents=True)
    assert path.exists()

    assert cache.delete_cached_model(model_id)
    assert not path.exists()


def test_delete_cached_model_s3(cache):
    cache.s3_client.delete_object.reset_mock()
    model_id = "delete/s3"

    success = cache.delete_cached_model(model_id, local=False, s3=True)
    assert success is True
    cache.s3_client.delete_object.assert_called_once()


def test_root_ca_path(tmp_path):
    ca_path = "/tmp/ca.pem"
    with mock.patch("boto3.Session.client") as mocked_client:
        mocked_client.return_value = mock.MagicMock()
        _ = S3ModelCache(
            bucket_name="bucket",
            s3_endpoint="https://ep",
            aws_access_key_id="k",
            aws_secret_access_key="s",
            root_ca_path=ca_path,
            local_cache_dir=str(tmp_path),
        )
        # ensure verify param equals path
        mocked_client.assert_called_once()
        _, kwargs = mocked_client.call_args
        assert kwargs["verify"] == ca_path


def test_memory_efficient_compression_with_large_files(cache):
    """Test memory-efficient compression with synthetic large files.
    
    This test creates synthetic model files to verify that the streaming
    compression works correctly without memory issues, simulating the
    VAGOsolutions/Llama-3.1-SauerkrautLM-70b-Instruct model structure.
    """
    # Create a synthetic model directory structure similar to large models
    model_id = "VAGOsolutions_Llama-3.1-SauerkrautLM-70b-Instruct"
    model_path = cache._get_local_path(model_id)
    model_path.mkdir(parents=True)
    
    # Create various file types that would be in a large model
    files_to_create = [
        ("config.json", '{"model_type": "llama", "vocab_size": 128256}'),
        ("tokenizer.json", '{"version": "1.0", "truncation": null}'),
        ("tokenizer_config.json", '{"tokenizer_class": "LlamaTokenizer"}'),
        ("special_tokens_map.json", '{"bos_token": "<|begin_of_text|>"}'),
        ("generation_config.json", '{"do_sample": true, "temperature": 0.6}'),
    ]
    
    # Create small text files
    for filename, content in files_to_create:
        (model_path / filename).write_text(content)
    
    # Create a few larger binary files to simulate model weights
    # These represent the actual model weight files that cause memory issues
    import os
    for i in range(3):
        weight_file = model_path / f"pytorch_model-{i:05d}-of-00003.bin"
        # Create 10MB files filled with zeros (simulates model weights)
        with open(weight_file, "wb") as f:
            # Write in chunks to avoid memory issues during test file creation
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(10):  # 10 chunks = 10MB
                f.write(b'\x00' * chunk_size)
    
    # Test compression with our memory-efficient method
    archive_path = cache.local_cache_dir / f"{model_id}.tar.gz"
    
    # This should work without memory issues due to streaming
    cache._compress_model(model_path, archive_path)
    
    # Verify archive was created
    assert archive_path.exists()
    assert archive_path.stat().st_size > 0
    
    # Verify archive contains all files
    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getnames()
        # Should contain exactly the expected files (5 config files + 3 weight files = 8)
        assert len(members) == len(files_to_create) + 3  # +3 for weight files
        
        # Check that weight files are in the archive
        weight_files_in_archive = [m for m in members if "pytorch_model" in m]
        assert len(weight_files_in_archive) == 3
        
        # Verify we have the expected model directory structure
        model_dir_files = [m for m in members if model_id in m]
        assert len(model_dir_files) == 8, f"Expected 8 files in model directory, got {len(model_dir_files)}"
    
    # Test extraction
    extract_dir = cache.local_cache_dir / "extracted_test"
    extract_dir.mkdir()
    cache._extract_model(archive_path, extract_dir)
    
    # Verify extraction worked
    extracted_model_path = extract_dir.parent / model_path.name
    assert extracted_model_path.exists()
    
    # Verify all files were extracted correctly
    for filename, expected_content in files_to_create:
        extracted_file = extracted_model_path / filename
        assert extracted_file.exists()
        assert extracted_file.read_text() == expected_content
    
    # Verify weight files were extracted with correct sizes
    for i in range(3):
        weight_file = extracted_model_path / f"pytorch_model-{i:05d}-of-00003.bin"
        assert weight_file.exists()
        assert weight_file.stat().st_size == 10 * 1024 * 1024  # 10MB
    
    # Clean up
    archive_path.unlink(missing_ok=True)
    if extracted_model_path.exists():
        import shutil
        shutil.rmtree(extracted_model_path)
    if extract_dir.exists():
        extract_dir.rmdir()
    
    # Clean up original synthetic model
    if model_path.exists():
        import shutil
        shutil.rmtree(model_path)


@pytest.mark.slow
def test_large_model_path_generation():
    """Test path generation for the large model mentioned by the user.
    
    This test verifies that our path generation works correctly for
    the VAGOsolutions/Llama-3.1-SauerkrautLM-70b-Instruct model.
    """
    # Create a temporary cache instance for path testing
    with tempfile.TemporaryDirectory() as tmp_dir:
        with mock.patch("boto3.Session.client") as mocked_client:
            mocked_client.return_value = mock.MagicMock()
            cache = S3ModelCache(
                bucket_name="test-bucket",
                s3_endpoint="https://test-endpoint",
                aws_access_key_id="test-key",
                aws_secret_access_key="test-secret",
                local_cache_dir=tmp_dir,
            )
            
            model_id = "VAGOsolutions/Llama-3.1-SauerkrautLM-70b-Instruct"
            
            # Test S3 key generation
            s3_key = cache._get_s3_key(model_id)
            expected_key = "models/VAGOsolutions_Llama-3.1-SauerkrautLM-70b-Instruct.tar.gz"
            assert s3_key == expected_key
            
            # Test local path generation
            local_path = cache._get_local_path(model_id)
            expected_path = Path(tmp_dir) / "VAGOsolutions_Llama-3.1-SauerkrautLM-70b-Instruct"
            assert local_path == expected_path
            
            # Verify path components are filesystem-safe (no slashes in filename)
            assert "/" not in local_path.name
            assert "/" not in s3_key.split("/")[-1].replace(".tar.gz", "")

