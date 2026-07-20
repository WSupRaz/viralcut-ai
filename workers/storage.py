from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig

from workers.config import settings


@lru_cache
def get_r2_client():
    endpoint_url = settings.r2_endpoint_url or f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="auto",
    )


def download_to_path(key: str, local_path: str) -> None:
    get_r2_client().download_file(settings.r2_bucket_name, key, local_path)


def upload_from_path(local_path: str, key: str, content_type: str = "video/mp4") -> None:
    get_r2_client().upload_file(
        local_path, settings.r2_bucket_name, key, ExtraArgs={"ContentType": content_type}
    )
