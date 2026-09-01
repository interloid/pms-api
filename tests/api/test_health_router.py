from fastapi import FastAPI
from tests.api.conftest import ApiClient

from app.api.v1.endpoints.health import router


def test_health_returns_application_status():
    app = FastAPI()
    app.include_router(router)

    response = ApiClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "message": "Application is running",
    }
