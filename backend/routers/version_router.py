from fastapi import APIRouter, Response

from core.config import settings
from models.version_schemas import VersionOut

router = APIRouter(tags=["Version"])


@router.get("/version", response_model=VersionOut)
async def get_version(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return VersionOut(version=settings.PROJECT_VERSION, commit=settings.GIT_SHA)
