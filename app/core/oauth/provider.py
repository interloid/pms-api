from abc import ABC, abstractmethod
from typing import Any


class OAuthProvider(ABC):
    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        pass

    @abstractmethod
    async def exchange_code(self, code: str) -> dict[str, Any]:
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        pass
