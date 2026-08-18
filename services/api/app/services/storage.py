import re
import uuid
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings

PRESIGNED_URL_EXPIRY_SECONDS = 3600

ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-m4v": "m4v",
}

# Min part size for S3 multipart is 5 MiB (except the last part); 8 MiB keeps
# the part count comfortably under every provider's 10,000-part ceiling even
# at the 5 GiB single-upload max (8 MiB -> 640 parts at 5 GiB).
MULTIPART_PART_SIZE_BYTES = 8 * 1024 * 1024

# Bytes of the head of the object we fetch to sniff the container format.
_MAGIC_SNIFF_BYTES = 64

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _build_r2_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            # botocore's default read timeout is 60s, which is fine for every
            # call here except one: CompleteMultipartUpload makes the provider
            # assemble the finished object from all its parts server-side, and
            # for a several-hundred-megabyte file with dozens of parts that
            # regularly runs past a minute. Timing out there raises
            # ReadTimeoutError -- a BotoCoreError, not a ClientError -- which
            # surfaced as an unhandled 500 while the assembly was still
            # succeeding in the background.
            connect_timeout=15,
            read_timeout=300,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
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


def sanitize_filename(filename: str) -> str:
    """Reduce a client-supplied filename to a safe basename for use inside an
    object key: strip any directory components (path traversal), collapse
    weird characters to '_', and never let the result be empty or '.'/..'."""
    base = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    base = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    if not base:
        base = "video"
    return base[:150]


def build_raw_video_key(project_id: uuid.UUID, filename: str) -> str:
    return f"raw/{project_id}/{uuid.uuid4()}-{sanitize_filename(filename)}"


def compute_multipart_part_count(size_bytes: int) -> int:
    """Part count for the fixed 8 MiB chunk size, clamped so we never exceed
    the 10,000-part ceiling providers enforce (would only matter far above
    the 5 GiB upload cap; keeps the math honest regardless)."""
    return max(1, -(-size_bytes // MULTIPART_PART_SIZE_BYTES))


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


def create_multipart_upload(key: str, content_type: str) -> str:
    """Server-side CreateMultipartUpload; returns the upload_id. The browser
    PUTs each part to a presigned part URL; the server completes/aborts."""
    client = get_internal_r2_client()
    response = client.create_multipart_upload(
        Bucket=settings.r2_bucket_name, Key=key, ContentType=content_type
    )
    return response["UploadId"]


def generate_presigned_part_upload_url(key: str, upload_id: str, part_number: int) -> str:
    client = get_r2_client()
    return client.generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
    )


def list_parts(key: str, upload_id: str) -> list[dict]:
    """All uploaded parts for a multipart upload as {part_number, size, etag}.
    Order is not guaranteed by the API; callers sort/validate themselves."""
    client = get_internal_r2_client()
    parts = []
    paginator = client.get_paginator("list_parts")
    for page in paginator.paginate(
        Bucket=settings.r2_bucket_name, Key=key, UploadId=upload_id
    ):
        for part in page.get("Parts", []):
            parts.append(
                {
                    "part_number": part["PartNumber"],
                    "size": part["Size"],
                    "etag": part["ETag"],
                }
            )
    return parts


def complete_multipart_upload(key: str, upload_id: str, parts: list[dict]) -> None:
    """Complete a multipart upload. `parts` must be the exact part list from
    list_parts (part_number + etag) -- do not trust client-supplied ETags."""
    client = get_internal_r2_client()
    client.complete_multipart_upload(
        Bucket=settings.r2_bucket_name,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={
            "Parts": [{"PartNumber": p["part_number"], "ETag": p["etag"]} for p in parts]
        },
    )


def abort_multipart_upload(key: str, upload_id: str) -> None:
    """Best-effort abort; aborts are idempotent and a missing upload is a no-op."""
    client = get_internal_r2_client()
    try:
        client.abort_multipart_upload(
            Bucket=settings.r2_bucket_name, Key=key, UploadId=upload_id
        )
    except ClientError:
        pass


def object_size(key: str) -> int | None:
    """HEAD an object; returns its size, or None if it doesn't exist."""
    client = get_internal_r2_client()
    try:
        response = client.head_object(Bucket=settings.r2_bucket_name, Key=key)
    except ClientError as exc:
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
            return None
        raise
    return int(response["ContentLength"])


def head_is_video_container(key: str) -> bool:
    """Cheap sanity check that the stored object actually starts like an
    ISO-BMFF container (mp4/mov/m4v are all box-based): scan the first 64
    bytes for an 'ftyp' box. Catches obviously-wrong uploads (e.g. an HTML
    error page, a zip) before we spend an ffmpeg pass on them. ffprobe in
    the worker remains the real gate."""
    client = get_internal_r2_client()
    try:
        response = client.get_object(
            Bucket=settings.r2_bucket_name, Key=key, Range=f"bytes=0-{_MAGIC_SNIFF_BYTES - 1}"
        )
        head = response["Body"].read(_MAGIC_SNIFF_BYTES)
    except ClientError:
        return False
    return b"ftyp" in head


def delete_object(key: str) -> None:
    # Presigned uploads mean a source_video row can exist with no matching
    # object yet (or ever, if the browser PUT never completed) -- deleting
    # a key that was never written is not an error, just a no-op.
    get_internal_r2_client().delete_object(Bucket=settings.r2_bucket_name, Key=key)
