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
        """Return parks under the "Walt Disney Attractions" group."""
        resp = await self.client.get(PARKS_URL)
        resp.raise_for_status()
        data = resp.json()
        groups: List[Dict[str, Any]]
        if isinstance(data, dict):
            groups = data.get("parks", [])  # type: ignore[assignment]
        else:
            groups = data
        for group in groups:
            if group.get("name") == "Walt Disney Attractions":
                return group.get("parks", [])
        return []

    async def fetch_wait_times(self, park_id: int | str) -> List[Dict[str, Any]]:
        """Fetch and flatten all ride wait times for a park."""
        url = PARK_QUEUE_URL.format(park_id=park_id)
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        # Some endpoints return rides directly, others group by areas/lands.
        if isinstance(data, dict):
            if isinstance(data.get("rides"), list):
                return data["rides"]
            areas = data.get("lands") or data.get("areas") or []
        elif isinstance(data, list):
            areas = data
        else:
            areas = []
        rides: List[Dict[str, Any]] = []
        for area in areas:
            rides.extend(area.get("rides", []))
        return rides

    async def close(self) -> None:
        await self.client.aclose()

