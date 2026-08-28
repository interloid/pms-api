from redis.asyncio import Redis


class OAuthStateRepository:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def create(
        self,
        state: str,
        provider: str,
        ttl: int,
    ) -> None:

        key = f"oauth:state:{state}"

        await self.redis.set(key, provider, ex=ttl)

    async def consume(
        self,
        state: str,
    ) -> str | None:

        key = f"oauth:state:{state}"

        provider = await self.redis.getdel(key)

        if provider is None:
            return None

        if isinstance(provider, bytes):
            return provider.decode()

        return provider
