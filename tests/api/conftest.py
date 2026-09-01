import asyncio
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response


class ApiClient:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        async def send() -> Response:
            request_kwargs = dict(kwargs)
            cookies = request_kwargs.pop("cookies", None)
            transport = ASGITransport(app=self.app, raise_app_exceptions=True)
            async with AsyncClient(
                transport=transport,
                base_url="http://testclient",
                cookies=cookies,
            ) as client:
                return await client.request(method, url, **request_kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        return self.request("DELETE", url, **kwargs)
