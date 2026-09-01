from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth_router,
    email_router,
    health,
    oauth_router,
    product_router,
)

router = APIRouter()

router.include_router(
    health.router,
    tags=["Health"],
)

router.include_router(auth_router.router)
router.include_router(email_router.router)
router.include_router(oauth_router.router)
router.include_router(product_router.router)
