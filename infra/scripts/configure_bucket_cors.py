"""Set the bucket CORS rule required for browser-direct uploads.

The browser PUTs multipart parts straight to object storage via presigned
URLs (cross-origin, from your app's origin to the bucket's S3 endpoint).
Without a CORS rule allowing that origin, every part PUT is aborted by the
browser before it starts -- the upload spins at 0% and finally reports
"Upload paused due to network issues". The API's own CORS is a separate,
already-configured concern; this is the *bucket's* rule.

Usage (same env vars as the rest of the stack; on Render, copy the R2_*
values from the `api` service's Environment tab):

  R2_ENDPOINT_URL=https://<your-s3-endpoint> \\
  R2_ACCESS_KEY_ID=<keyID> R2_SECRET_ACCESS_KEY=<applicationKey> \\
  R2_BUCKET_NAME=<bucket> \\
  python infra/scripts/configure_bucket_cors.py --origin https://<your-app-domain>

`--origin` may be given multiple times for extra origins (e.g. localhost for
dev). If omitted, defaults to `*` (works everywhere, but wider than needed).

For Backblaze B2, the endpoint is your account's S3-compatible endpoint,
e.g. https://s3.us-east-005.backblazeb2.com (NOT the console URL). The same
S3 PutBucketCors API is used by MinIO, R2, and AWS S3, so this script works
against all of them.
"""

import argparse
import os
import sys

import boto3
from botocore.client import Config as BotoConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin",
        action="append",
        default=[],
        help="allowed origin (repeatable). Defaults to * if none given.",
    )
    args = parser.parse_args()

    origins = args.origin or ["*"]

    endpoint = os.environ.get("R2_ENDPOINT_URL") or os.environ.get("B2_ENDPOINT_URL")
    if not endpoint:
        print("error: set R2_ENDPOINT_URL (or B2_ENDPOINT_URL)", file=sys.stderr)
        sys.exit(1)
    access_key = os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("B2_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("B2_APPLICATION_KEY")
    bucket = os.environ.get("R2_BUCKET_NAME") or os.environ.get("B2_BUCKET_NAME")
    if not (access_key and secret_key and bucket):
        print(
            "error: set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME "
            "(or the B2_* equivalents)",
            file=sys.stderr,
        )
        sys.exit(1)

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=BotoConfig(signature_version="s3v4"),
    )

    rule = {
        "AllowedOrigins": origins,
        # GET/HEAD for the eventual download URLs (exports), PUT for part
        # uploads, POST for complete; DELETE so the app can remove objects.
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3600,
    }

    try:
        client.put_bucket_cors(Bucket=bucket, CORSConfiguration={"CORSRules": [rule]})
    except Exception as exc:  # noqa: BLE001 -- surface the provider's message
        print(f"error: could not set CORS rule: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"CORS rule set on '{bucket}' for origins: {', '.join(origins)}")
    print("Verify: curl -i -X OPTIONS <presigned-part-url> -H 'Origin: <origin>'")
    print("         -H 'Access-Control-Request-Method: PUT'  # expect 2xx + access-control-allow-origin")


if __name__ == "__main__":
    main()
