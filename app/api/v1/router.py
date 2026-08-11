from fastapi import APIRouter

from app.api.v1.endpoints import auth_router, user_router, health, test

router = APIRouter()

router.include_router(
    health.router,
    tags=["Health"],
)

router.include_router(auth_router.router)
router.include_router(test.router)
router.include_router(user_router.router)
