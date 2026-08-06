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


def _build_r2_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="auto",
    )


@lru_cache
def get_r2_client():
    # This client only ever generates presigned URLs (no direct transfers),
    # so it must use whatever endpoint the eventual requester (the browser)
    # can reach -- r2_public_endpoint_url when set, see config.py.
    endpoint_url = (
        settings.r2_public_endpoint_url
        or settings.r2_endpoint_url
        or f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    )
    return _build_r2_client(endpoint_url)


@lru_cache
def get_internal_r2_client():
    # For calls this process makes itself (not presigned URLs handed to the
    # browser), so it must use an endpoint *this server* can reach -- e.g.
    # the Docker-internal MinIO host in dev, never r2_public_endpoint_url.
    endpoint_url = settings.r2_endpoint_url or f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return _build_r2_client(endpoint_url)


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


def delete_object(key: str) -> None:
    # Presigned uploads mean a source_video row can exist with no matching
    # object yet (or ever, if the browser PUT never completed) -- deleting
    # a key that was never written is not an error, just a no-op.
    get_internal_r2_client().delete_object(Bucket=settings.r2_bucket_name, Key=key)
