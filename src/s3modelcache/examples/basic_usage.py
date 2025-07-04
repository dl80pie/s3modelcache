"""Minimal example demonstrating how to use *s3modelcache*.

Prerequisite:
    1. Export the required S3 credentials / endpoint variables OR create a .env file.
    2. Install the package in editable mode:  `pip install -e .[test]`

This script will
    • download the model from Hugging Face (if not present in the bucket)
    • upload it to the configured S3 bucket
    • retrieve the local path (and optionally load it with vLLM)
"""
from __future__ import annotations

import os
from pathlib import Path

from s3modelcache import S3ModelCache, upload_large_model_to_hcp

# ---------------------------------------------------------------------------
# 1. Read configuration from environment (see README for details)
# ---------------------------------------------------------------------------
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
MODEL_ID = os.getenv("HF_MODEL", "microsoft/phi-2")  # smaller default model

if not all((S3_ENDPOINT, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET)):
    raise SystemExit("Please set S3_ENDPOINT, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET env vars")

# ---------------------------------------------------------------------------
# 2. Initialise the cache
# ---------------------------------------------------------------------------
cache = S3ModelCache(
    bucket_name=S3_BUCKET,
    s3_endpoint=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    local_cache_dir="./model_cache",  # will be created if absent
    verify_ssl=False,  # set True in production if you have valid certs
)

# ---------------------------------------------------------------------------
# 3. Cache / upload model (skipped if already present)
# ---------------------------------------------------------------------------
print(f"Caching {MODEL_ID} to {S3_BUCKET} …")
success = cache.cache_model_to_s3(MODEL_ID)
print("Upload done" if success else "Upload failed")

# ---------------------------------------------------------------------------
# 4. Multipart upload example for very large models (>5 GB)
# ---------------------------------------------------------------------------
# upload_large_model_to_hcp(cache, MODEL_ID, chunk_size=500*1024*1024)

# ---------------------------------------------------------------------------
# 5. Load with vLLM (optional)
# ---------------------------------------------------------------------------
# llm = cache.load_with_vllm(MODEL_ID, gpu_memory_utilization=0.9)
# print("LLM ready ->", llm)

# ---------------------------------------------------------------------------
print("Local path:", Path(cache._get_local_path(MODEL_ID)).resolve())