from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth_router,
    health,
    product_router,
)

router = APIRouter()

router.include_router(
    health.router,
    tags=["Health"],
)

router.include_router(auth_router.router)
router.include_router(product_router.router)
# router.include_router(product_image_router.router)
# router.include_router(test.router)
# router.include_router(user_router.router)
