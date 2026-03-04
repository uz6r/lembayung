import logging
from datetime import date
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on transient errors (5xx, timeouts). NOT on 428."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class RateLimitHit(Exception):
    """
    Exception raised when the target server issues a Proof-of-Work (Altcha)
    challenge or rate-limit response (428/429). Used to circuit-break cycles
    and respect server-side load-management signals.
    """

    pass


class UnauthorizedError(Exception):
    """
    Exception raised when the widget API returns a 401 Unauthorized error.
    Typically means the target ID / slug or API key is invalid or rotated.
    """

    pass


class ProviderAdapter:
    """
    Adapter for the Provider Widget API. This class is designed for technical
    protocol analysis and demonstrates how to handle asynchronous sessions with
    persistence and responsible retry-logic.

    POLITENESS POLICY:
    - Reuses connections via a persistent client to avoid repeated handshakes.
    - Implements Circuit-Breaking (stops on 428/429).
    - Includes randomized jitter on all automated requests.
    """

    def __init__(
        self, base_url: str, api_key: str, target_slug: str, origin: str, referer: str
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.target_slug = target_slug
        self.origin = origin
        self.referer = referer

        # Spoof realistic browser headers to prevent basic blocking
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "origin": self.origin,
            "referer": self.referer,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "venue-api-key": self.api_key,
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        }

        # Persistent client for connection reuse and HTTP/2
        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=15.0,
            http2=False,
        )

    async def close(self):
        """Cleanly close the persistent HTTP client."""
        await self._client.aclose()

    async def get_calendar(self, party_size: int, start_date: date) -> dict[str, Any]:
        """
        Fetches the calendar availability overview.
        Endpoint: GET /v2/slots/calendar
        """
        url = f"{self.base_url}/v2/slots/calendar"
        params: dict[str, str | int] = {
            "party_size": party_size,
            "date": start_date.strftime("%Y-%m-%d"),
        }

        logger.debug(f"Fetching calendar from {url} with params {params}")
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30, jitter=3),
        reraise=True,
    )
    async def get_slots(
        self, party_size: int, target_date: date
    ) -> list[dict[str, Any]]:
        """
        Fetches the specific time slots for a given date.
        Endpoint: GET /v2/slots

        Retries on transient 5xx/timeout errors.
        Raises RateLimitHit on 428 for circuit-breaking.
        """
        url = f"{self.base_url}/v2/slots"
        params: dict[str, str | int] = {
            "party_size": party_size,
            "date": target_date.strftime("%Y-%m-%d"),
        }

        logger.debug(f"Fetching slots from {url} with params {params}")
        response = await self._client.get(url, params=params)

        # Circuit-break on 428 (Altcha/PoW challenge)
        if response.status_code == 428:
            raise RateLimitHit(
                f"428 Precondition Required for {target_date} pax {party_size}. "
                "Server requires Altcha/PoW — circuit-breaking this cycle."
            )

        if response.status_code == 401:
            raise UnauthorizedError(
                f"401 Unauthorized for {target_date} pax {party_size}. "
                f"Invalid API Key or Target Slug: {response.text}"
            )

        response.raise_for_status()

        data = response.json()
        # Returns different structures; check for 'slots' or 'data' keys
        res = (
            data.get("slots", data.get("data", data))
            if isinstance(data, dict)
            else data
        )
        if isinstance(res, list):
            return res
        return []
