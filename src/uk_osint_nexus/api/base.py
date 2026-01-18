"""Base API client with common functionality."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from pydantic import BaseModel


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 2.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_call = time.monotonic()


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class BaseAPIClient(ABC):
    """Abstract base class for API clients."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        rate_limit: float = 2.0,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.rate_limiter = RateLimiter(rate_limit)
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_name(self) -> str:
        """Human-readable name for this data source."""
        return self.__class__.__name__.replace("Client", "")

    def _get_headers(self) -> dict[str, str]:
        """Get default headers for requests."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "UK-OSINT-Nexus/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Basic {self.api_key}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with rate limiting."""
        await self.rate_limiter.acquire()

        client = await self._get_client()
        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                response=e.response,
            )
        except httpx.RequestError as e:
            raise APIError(f"Request failed: {str(e)}")

    async def get(self, endpoint: str, params: Optional[dict] = None) -> dict[str, Any]:
        """Make a GET request."""
        return await self._request("GET", endpoint, params=params)

    async def post(
        self, endpoint: str, json_data: Optional[dict] = None, params: Optional[dict] = None
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", endpoint, params=params, json_data=json_data)

    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[BaseModel]:
        """Search this data source. Must be implemented by subclasses."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
