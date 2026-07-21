from fastapi import APIRouter

from app.api.v1 import auth, edit_plans, exports, jobs, projects, source_videos

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(source_videos.router)
api_router.include_router(jobs.router)
api_router.include_router(edit_plans.router)
api_router.include_router(exports.router)
