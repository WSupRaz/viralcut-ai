import uuid
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import settings

PRESIGNED_URL_EXPIRY_SECONDS = 3600

ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-m4v": "m4v",
}


@lru_cache
def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def build_raw_video_key(project_id: uuid.UUID, filename: str) -> str:
    return f"raw/{project_id}/{uuid.uuid4()}-{filename}"


def generate_presigned_upload_url(key: str, content_type: str) -> str:
    client = get_r2_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
    )


def generate_presigned_get_url(key: str) -> str:
    client = get_r2_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
    )
