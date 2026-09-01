import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:

    response = await client.get("/api/v1/health")

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["status"] == "ok"
    assert response_data["message"] == "Application is running"
