import asyncio

from httpx import ASGITransport, AsyncClient


class ApiClient:
    def __init__(self, app):
        self.app = app

    def request(self, method, url, **kwargs):
        async def send():
            transport = ASGITransport(app=self.app)
            cookies = kwargs.pop("cookies", None)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
                cookies=cookies,
            ) as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)
