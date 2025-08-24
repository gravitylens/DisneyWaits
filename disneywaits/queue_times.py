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

        def _collect(node: Any) -> List[Dict[str, Any]]:
            rides: List[Dict[str, Any]] = []
            if isinstance(node, dict):
                if isinstance(node.get("rides"), list):
                    rides.extend(node["rides"])
                for key in ("lands", "areas"):
                    for child in node.get(key, []) or []:
                        rides.extend(_collect(child))
            elif isinstance(node, list):
                for child in node:
                    rides.extend(_collect(child))
            return rides

        rides = _collect(data)
        logger.debug(
            "Flattened rides for park %s: %s", park_id, [r.get("name") for r in rides]
        )
        if not rides:
            logger.warning("No rides found for park %s", park_id)
        else:
            logger.info("Park %s returned %d rides", park_id, len(rides))
        return rides

    async def close(self) -> None:
        await self.client.aclose()

