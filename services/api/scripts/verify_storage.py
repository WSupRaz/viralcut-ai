"""Check that the configured object-storage credentials actually work.

Uses the application's own client (app.services.storage.get_internal_r2_client)
rather than a hand-rolled boto3 session, so a pass here means the app itself
can reach the bucket -- same endpoint, addressing style, signature version and
timeouts. A standalone script with slightly different config can pass while
the app still fails, which would be a misleading all-clear.

Reads configuration from the environment only; nothing is written to disk and
no secret is printed. Key IDs are shown fingerprinted (first/last 4 chars) so
you can confirm *which* credential is loaded without exposing it.

    python scripts/verify_storage.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from botocore.exceptions import BotoCoreError, ClientError  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.storage import get_internal_r2_client  # noqa: E402


def fingerprint(value: str | None) -> str:
    """Enough to identify a credential, not enough to use one."""
    if not value:
        return "<unset>"
    if len(value) <= 8:
        return f"<set, {len(value)} chars>"
    return f"{value[:4]}...{value[-4:]} ({len(value)} chars)"


def main() -> int:
    endpoint = (
        settings.r2_endpoint_url
        or f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    )
    bucket = settings.r2_bucket_name

    print("Configuration")
    print(f"  endpoint : {endpoint}")
    print(f"  bucket   : {bucket}")
    print(f"  key id   : {fingerprint(settings.r2_access_key_id)}")
    print(f"  secret   : {fingerprint(settings.r2_secret_access_key)}")
    print()

    client = get_internal_r2_client()
    failures = 0

    print("Checks")
    try:
        client.head_bucket(Bucket=bucket)
        print("  head_bucket      OK   -- credentials valid, bucket reachable")
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code", "")
        print(f"  head_bucket      FAIL -- HTTP {status} {code}")
        if status == 403:
            print("                        403 = credentials rejected or not scoped to this bucket")
        elif status == 404:
            print("                        404 = bucket does not exist at this endpoint")
        failures += 1
    except BotoCoreError as exc:
        print(f"  head_bucket      FAIL -- {type(exc).__name__} (endpoint unreachable / timeout)")
        failures += 1

    try:
        resp = client.list_objects_v2(Bucket=bucket, MaxKeys=5)
        print(
            f"  list_objects_v2  OK   -- {resp.get('KeyCount', 0)} object(s) visible "
            "(max 5 requested)"
        )
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code", "")
        print(f"  list_objects_v2  FAIL -- HTTP {status} {code}")
        failures += 1
    except BotoCoreError as exc:
        print(f"  list_objects_v2  FAIL -- {type(exc).__name__}")
        failures += 1

    print()
    print("STORAGE OK" if failures == 0 else f"STORAGE FAILING ({failures} check(s) failed)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
