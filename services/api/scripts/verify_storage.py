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
    probe_key = "_healthcheck/verify_storage_probe"

    def report(label: str, exc: Exception) -> None:
        if isinstance(exc, ClientError):
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = exc.response.get("Error", {}).get("Code", "")
            msg = exc.response.get("Error", {}).get("Message", "")
            print(f"  {label:<16} FAIL -- HTTP {status} {code} {msg}".rstrip())
        else:
            print(f"  {label:<16} FAIL -- {type(exc).__name__} (unreachable / timeout)")

    # Exercise the operations the app actually performs, in order. head_bucket
    # alone is not enough: a key with write but no read passes it and still
    # breaks every upload at the verification step, which is exactly the
    # failure this script exists to catch.
    print("Checks")
    try:
        client.head_bucket(Bucket=bucket)
        print("  head_bucket      OK   -- credentials valid, bucket reachable")
    except (ClientError, BotoCoreError) as exc:
        report("head_bucket", exc)
        if isinstance(exc, ClientError) and exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 403:
            print("                        403 = credentials rejected or not scoped to this bucket")
        failures += 1

    wrote = False
    try:
        client.put_object(Bucket=bucket, Key=probe_key, Body=b"viralcut-probe", ContentType="text/plain")
        wrote = True
        print("  put_object       OK   -- key can WRITE")
    except (ClientError, BotoCoreError) as exc:
        report("put_object", exc)
        print("                        write capability missing -- uploads cannot be assembled")
        failures += 1

    if wrote:
        try:
            client.head_object(Bucket=bucket, Key=probe_key)
            print("  head_object      OK   -- key can READ metadata")
        except (ClientError, BotoCoreError) as exc:
            report("head_object", exc)
            print("                        READ capability missing. Uploads assemble and then fail")
            print("                        verification; the worker also cannot fetch the video.")
            print("                        Fix: give the application key readFiles on this bucket.")
            failures += 1

        try:
            client.get_object(Bucket=bucket, Key=probe_key, Range="bytes=0-7")
            print("  get_object       OK   -- key can READ contents (ranged)")
        except (ClientError, BotoCoreError) as exc:
            report("get_object", exc)
            failures += 1

        try:
            client.delete_object(Bucket=bucket, Key=probe_key)
            print("  delete_object    OK   -- probe cleaned up")
        except (ClientError, BotoCoreError) as exc:
            report("delete_object", exc)
            print(f"                        leftover probe object: {probe_key}")
            failures += 1

    print()
    print("STORAGE OK" if failures == 0 else f"STORAGE FAILING ({failures} check(s) failed)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
