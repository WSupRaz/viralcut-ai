import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from db_models.models.source_video import SourceVideo

from workers.celery_app import celery_app
from workers.config import settings
from workers.db import get_session_factory
from workers.storage import abort_multipart_upload, delete_object


@celery_app.task(name="workers.tasks.cleanup.sweep_abandoned_uploads", max_retries=2)
def sweep_abandoned_uploads() -> dict:
    """Periodic sweep (celery beat): abort + delete source-video upload
    sessions that were started but never completed -- a browser that died
    mid-upload (tab closed hard, laptop lost, refresh mid-flight) would
    otherwise leak the multipart upload and its partial object forever.

    Mirrors the API-side sweep that runs when a new upload starts
    (source_video_service._cleanup_abandoned_uploads); this catches projects
    nobody touches again. Rows whose upload_id is set and created_at is older
    than abandoned_upload_ttl_hours are aborted, deleted, and removed."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.abandoned_upload_ttl_hours)
    session_factory = get_session_factory()

    cleaned = 0
    with session_factory() as session:
        rows = (
            session.execute(
                select(SourceVideo).where(
                    SourceVideo.upload_id.is_not(None),
                    SourceVideo.created_at < cutoff,
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            abort_multipart_upload(row.r2_key_raw, row.upload_id)
            delete_object(row.r2_key_raw)
            session.delete(row)
            cleaned += 1
        session.commit()

    return {"cleaned": cleaned, "cutoff": cutoff.isoformat()}
