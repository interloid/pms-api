from fastapi import FastAPI

from app.api.v1.endpoints.health import router
from tests.api.conftest import ApiClient


def test_health_returns_application_status():
    app = FastAPI()
    app.include_router(router)

    response = ApiClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "Application is running",
    }
