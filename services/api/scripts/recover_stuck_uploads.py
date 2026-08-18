"""Heal or purge SourceVideo rows left with an open multipart session.

A row is "stuck" when upload_id IS NOT NULL: the multipart session was never
closed, so upload_pending stays true forever. Two very different causes, and
they need opposite treatment:

  * the object IS fully assembled in storage -- a real, completed upload whose
    acknowledgement was lost. Finalise it (clear upload_id, enqueue the proxy
    job) so the user gets the clip they already uploaded. Deleting these would
    throw away a file that transferred successfully.
  * the object is missing or the wrong size -- the upload genuinely died.
    Abort the multipart session, delete any partial object, drop the row.

Reuses the application's own _finalize_assembled_upload, so a row healed here
is indistinguishable from one healed by the normal upload path.

Dry run by default -- prints what it would do and changes nothing. Pass --apply
to actually write.

    python scripts/recover_stuck_uploads.py --project <uuid>
    python scripts/recover_stuck_uploads.py --project <uuid> --apply
    python scripts/recover_stuck_uploads.py --all-projects
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from botocore.exceptions import BotoCoreError, ClientError  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.session import async_session_factory  # noqa: E402
from app.services.source_video_service import _finalize_assembled_upload  # noqa: E402
from app.services.storage import (  # noqa: E402
    abort_multipart_upload,
    delete_object,
    object_size,
)
from db_models.models.source_video import SourceVideo  # noqa: E402


def human(n: int | None) -> str:
    if n is None:
        return "?"
    if n >= 1024**3:
        return f"{n / 1024**3:.2f} GB"
    if n >= 1024**2:
        return f"{n / 1024**2:.1f} MB"
    return f"{n} B"


def classify(row: SourceVideo) -> tuple[str, str]:
    """(action, reason) for one stuck row, without changing anything."""
    try:
        stored = object_size(row.r2_key_raw)
    except (ClientError, BotoCoreError) as exc:
        return "skip", f"storage unreachable ({type(exc).__name__}) -- rerun later"

    if stored is None:
        return "delete", "no object in storage (upload never assembled)"
    if stored != row.size_bytes:
        return "delete", f"object is {human(stored)}, expected {human(row.size_bytes)}"
    return "finalize", f"object fully present ({human(stored)}) -- completed but unacknowledged"


async def main() -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="project id to scope to")
    group.add_argument("--all-projects", action="store_true", help="every project")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    args = ap.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    scope = "all projects" if args.all_projects else f"project {args.project}"
    print(f"[{mode}] stuck-upload recovery -- {scope}\n")

    async with async_session_factory() as db:
        query = select(SourceVideo).where(SourceVideo.upload_id.is_not(None))
        if not args.all_projects:
            query = query.where(SourceVideo.project_id == uuid.UUID(args.project))
        rows = list((await db.execute(query.order_by(SourceVideo.created_at))).scalars().all())

        if not rows:
            print("No stuck rows found. Nothing to do.")
            return 0

        print(f"{len(rows)} stuck row(s):\n")
        planned: list[tuple[SourceVideo, str, str]] = []
        for row in rows:
            action, reason = classify(row)
            planned.append((row, action, reason))
            print(f"  {row.id}  {row.original_filename or '<no name>'}")
            print(
                f"    created {row.created_at:%Y-%m-%d %H:%M:%S} UTC, "
                f"declared {human(row.size_bytes)}"
            )
            print(f"    -> {action.upper()}: {reason}\n")

        counts = {
            a: sum(1 for _, act, _ in planned if act == a)
            for a in ("finalize", "delete", "skip")
        }
        print(
            f"Plan: {counts['finalize']} to finalize, {counts['delete']} to delete, "
            f"{counts['skip']} skipped"
        )

        if not args.apply:
            print("\nDry run -- nothing was changed. Re-run with --apply to execute.")
            return 0

        print("\nApplying...\n")
        finalized = deleted = skipped = failed = 0
        for row, action, _ in planned:
            try:
                if action == "finalize":
                    await _finalize_assembled_upload(db, source_video=row)
                    finalized += 1
                    print(f"  finalized {row.id} ({row.original_filename})")
                elif action == "delete":
                    try:
                        abort_multipart_upload(row.r2_key_raw, row.upload_id)
                        delete_object(row.r2_key_raw)
                    except (ClientError, BotoCoreError):
                        pass  # best effort; removing the row is what matters
                    await db.delete(row)
                    await db.commit()
                    deleted += 1
                    print(f"  deleted   {row.id} ({row.original_filename})")
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001 -- one bad row must not stop the sweep
                failed += 1
                print(f"  FAILED    {row.id}: {type(exc).__name__}: {exc}")
                await db.rollback()

        # Read the remaining count back from the database rather than trusting
        # the counters above.
        remaining_q = select(SourceVideo).where(SourceVideo.upload_id.is_not(None))
        if not args.all_projects:
            remaining_q = remaining_q.where(SourceVideo.project_id == uuid.UUID(args.project))
        remaining = len(list((await db.execute(remaining_q)).scalars().all()))

        print(
            f"\nDone: {finalized} finalized, {deleted} deleted, "
            f"{skipped} skipped, {failed} failed"
        )
        print(f"Stuck rows remaining in scope: {remaining}")
        return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
