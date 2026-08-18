"""A slow CompleteMultipartUpload must raise StorageUnavailableError (-> 502),
not escape as an unhandled error (-> opaque 500).

botocore signals a read timeout with ReadTimeoutError, a BotoCoreError. That
is a *sibling* of ClientError, not a subclass, so handlers written around
ClientError never saw it -- and assembling a large multipart object routinely
outruns the default 60s read timeout while still succeeding at the provider.
"""
import asyncio, uuid
from unittest.mock import patch
from botocore.exceptions import ReadTimeoutError

from app.db.session import async_session_factory
from app.services import source_video_service as svc
from app.services import storage
from app.services.source_video_service import (
    StorageUnavailableError, complete_source_video_upload,
)
from db_models.models.project import Project
from db_models.models.source_video import SourceVideo
from db_models.models.user import User

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: print(f"  PASS  {n}"); passed += 1
    else: print(f"  FAIL  {n}" + (f" -- {d}" if d else "")); failed += 1

async def main():
    body = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4000
    async with async_session_factory() as db:
        user = User(email=f"t-{uuid.uuid4().hex[:8]}@e.com", password_hash="x", name="T")
        db.add(user); await db.flush()
        proj = Project(user_id=user.id, title="t", target_aspect_ratio="9:16")
        db.add(proj); await db.flush()

        key = storage.build_raw_video_key(proj.id, "big.mp4")
        upload_id = storage.create_multipart_upload(key, "video/mp4")
        sv = SourceVideo(project_id=proj.id, r2_key_raw=key, order_index=0,
                         size_bytes=len(body), original_filename="big.mp4",
                         content_type="video/mp4", upload_id=upload_id)
        db.add(sv); await db.commit(); await db.refresh(sv)

        storage.get_internal_r2_client().upload_part(
            Bucket=storage.settings.r2_bucket_name, Key=key,
            UploadId=upload_id, PartNumber=1, Body=body)

        # 1. Timeout during assembly.
        with patch.object(svc, "complete_multipart_upload",
                          side_effect=ReadTimeoutError(endpoint_url="https://s3.example")):
            try:
                await complete_source_video_upload(db, project_id=proj.id, source_video_id=sv.id)
                check("read timeout is mapped, not swallowed", False, "no exception raised")
            except StorageUnavailableError as exc:
                check("read timeout -> StorageUnavailableError (502)", True)
                check("message reassures the file is uploaded", "uploaded" in str(exc).lower(), str(exc))
            except Exception as exc:
                check("read timeout -> StorageUnavailableError (502)", False,
                      f"got {type(exc).__name__}: {exc}")

        # 2. Timeout while listing parts.
        with patch.object(svc, "list_parts",
                          side_effect=ReadTimeoutError(endpoint_url="https://s3.example")):
            try:
                await complete_source_video_upload(db, project_id=proj.id, source_video_id=sv.id)
                check("list_parts timeout is mapped", False, "no exception raised")
            except StorageUnavailableError:
                check("list_parts timeout -> StorageUnavailableError (502)", True)
            except Exception as exc:
                check("list_parts timeout -> StorageUnavailableError (502)", False,
                      f"got {type(exc).__name__}: {exc}")

        # 3. The real call still works once storage responds.
        job = await complete_source_video_upload(db, project_id=proj.id, source_video_id=sv.id)
        check("normal completion still succeeds", job is not None)
        await db.refresh(sv)
        check("row finalised (upload_pending cleared)", sv.upload_id is None)

asyncio.run(main())
print(f"\n{passed} passed, {failed} failed")
raise SystemExit(0 if failed == 0 else 1)
