from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

PARKS_URL = "https://queue-times.com/parks.json"
PARK_QUEUE_URL = "https://queue-times.com/parks/{park_id}/queue_times.json"


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
        logger.debug("QueueTimes returned %d park groups", len(groups))
        for group in groups:
            if group.get("name") == "Walt Disney Attractions":
                parks = group.get("parks", [])
                logger.info("Found %d Disney parks", len(parks))
                return parks
        logger.warning("Walt Disney Attractions group not found in parks list")
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
                rides = data["rides"]
            else:
                areas = data.get("lands") or data.get("areas") or []
                rides = []
                for area in areas:
                    rides.extend(area.get("rides", []))
        elif isinstance(data, list):
            rides = []
            for area in data:
                rides.extend(area.get("rides", []))
        else:
            rides = []
        logger.debug("Park %s returned %d rides", park_id, len(rides))
        if not rides:
            logger.warning("No rides found for park %s", park_id)
        return rides

    async def close(self) -> None:
        await self.client.aclose()

