from __future__ import annotations

import httpx
from typing import Any, Dict, List

PARKS_URL = "https://queue-times.com/parks.json"
PARK_QUEUE_URL = "https://queue-times.com/parks/{park_id}/queue_times.json"


class QueueTimesClient:
    """HTTP client for the queue-times API."""

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(headers={"User-Agent": "DisneyWaits/1.0"})

    async def fetch_parks(self) -> List[Dict[str, Any]]:
        resp = await self.client.get(PARKS_URL)
        resp.raise_for_status()
        data = resp.json()
        return data.get("parks", data)

    async def fetch_wait_times(self, park_id: int | str) -> Dict[str, Any]:
        url = PARK_QUEUE_URL.format(park_id=park_id)
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self.client.aclose()

