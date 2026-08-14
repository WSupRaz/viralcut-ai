"""Install the bucket lifecycle rule that auto-expires abandoned multipart
uploads -- the provider-side safety net behind the hourly Celery sweep
(workers/tasks/cleanup.py) and the on-start sweep in the API. If a browser
dies mid-upload and the app itself is unreachable, the provider still aborts
the orphaned session (and frees its parts) after N days.

Works against any S3-compatible provider that supports the
AbortIncompleteMultipartUpload lifecycle action:
  * Cloudflare R2  -- supported; note R2 also expires multipart uploads by
                      DEFAULT after 7 days, so this only tightens the window
  * Backblaze B2   -- supported via its S3-compatible endpoint
  * MinIO (local)  -- supported too; harmless to run against dev. (Note:
                      some MinIO builds reject the S3 lifecycle XML outright
                      -- a known MinIO quirk; dev cleanup is still covered by
                      the in-app sweeps, so the script failing there is fine)

Usage (from anywhere; boto3 required -- the api/worker images have it):

  R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \\
  R2_BUCKET_NAME=... [R2_ENDPOINT_URL=https://<s3-endpoint>] \\
    python infra/scripts/configure_bucket_lifecycle.py [--days N]

Defaults: --days 1, which matches ABANDONED_UPLOAD_TTL_HOURS=24 in the app.
For local dev MinIO the env comes from the repo .env.
"""
import argparse
import os
import sys

import boto3
from botocore.client import Config as BotoConfig

RULE_ID = "abandoned-multipart-expiry"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1,
                        help="days after initiation before an incomplete multipart upload is aborted (default 1, matching the app's 24h TTL)")
    args = parser.parse_args()

    bucket = os.environ.get("R2_BUCKET_NAME")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    account_id = os.environ.get("R2_ACCOUNT_ID", "")
    endpoint = os.environ.get("R2_ENDPOINT_URL") or (
        f"https://{account_id}.r2.cloudflarestorage.com" if account_id else None
    )
    if not (bucket and access_key and secret_key and endpoint):
        print("error: set R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and", file=sys.stderr)
        print("       R2_ENDPOINT_URL (or R2_ACCOUNT_ID for real R2).", file=sys.stderr)
        sys.exit(2)

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="auto",
    )

    lifecycle = {
        "Rules": [
            {
                "ID": RULE_ID,
                "Status": "Enabled",
                # No Filter: the rule applies to the whole bucket (S3 allows
                # omitting Filter; an empty <Prefix> trips some validators).
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": args.days},
            }
        ]
    }

    try:
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket, LifecycleConfiguration=lifecycle
        )
        print(f"ok: lifecycle rule '{RULE_ID}' set on s3://{bucket} "
              f"(abort incomplete multipart after {args.days} day(s))")
    except Exception as exc:  # provider-specific errors bubble up with detail
        print(f"error: failed to set lifecycle rule: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
