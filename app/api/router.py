from fastapi import APIRouter

from app.api.v1.router import router as v1_router
from app.core import config

router = APIRouter()

router.include_router(
    v1_router,
    prefix=config.API_V1_PREFIX,
)
