"""s3modelcache package

Classic src/ layout:
    src/s3modelcache/
        __init__.py          (re-export public API)
        model_cache.py       (S3ModelCache implementation)
        logger.py            (HCPLogger + LoggedHCPCache)
        upload_large.py      (multipart helper)
"""
from .model_cache import S3ModelCache  # noqa: F401
from .logger import HCPLogger, LoggedHCPCache  # noqa: F401
from .upload_large import upload_large_model_to_hcp  # noqa: F401
#Backward-compat alias
upload_large_model = upload_large_model_to_hcp
