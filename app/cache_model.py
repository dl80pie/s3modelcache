import os
import sys

from s3modelcache import S3ModelCache


def main() -> int:
    model_id = os.getenv("MODEL_ID")
    if not model_id:
        print("ERROR: env MODEL_ID not set", file=sys.stderr)
        return 1

    bucket = os.getenv("S3_BUCKET")
    endpoint = os.getenv("S3_ENDPOINT")
    access_key = os.getenv("S3_ACCESS_KEY_ID")
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY")
    region = os.getenv("S3_REGION", "us-east-1")
    s3_prefix = os.getenv("S3_PREFIX", "models/")
    verify_ssl = os.getenv("S3_VERIFY_SSL", "true").lower() == "true"
    root_ca_path = os.getenv("S3_ROOT_CA_PATH") or None
    store_as_archive = os.getenv("S3_STORE_AS_ARCHIVE", "true").lower() == "true"

    if not bucket or not endpoint or not access_key or not secret_key:
        print(
            "ERROR: S3_* env vars not fully set (S3_BUCKET, S3_ENDPOINT, "
            "S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY)",
            file=sys.stderr,
        )
        return 1

    cache = S3ModelCache(
        bucket_name=bucket,
        s3_endpoint=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        s3_prefix=s3_prefix,
        verify_ssl=verify_ssl,
        root_ca_path=root_ca_path,
        store_as_archive=store_as_archive,
    )

    print(f"Caching model '{model_id}' to S3 bucket '{bucket}' ...")
    success = cache.cache_model_to_s3(model_id)
    if not success:
        print("ERROR: caching model to S3 failed", file=sys.stderr)
        return 1

    print("Model successfully cached to S3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
