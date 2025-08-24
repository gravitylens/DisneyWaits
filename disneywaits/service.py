from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List

from fastapi import FastAPI

from .queue_times import QueueTimesClient
from .stats import RideStats


@dataclass
class RideInfo:
    id: int | str
    name: str
    stats: RideStats = field(default_factory=RideStats)


@dataclass
class ParkInfo:
    id: int | str
    name: str
    rides: Dict[int | str, RideInfo] = field(default_factory=dict)


class DisneyWaitsService:
    def __init__(self, client: QueueTimesClient) -> None:
        self.client = client
        self.parks: Dict[int | str, ParkInfo] = {}

    async def update(self) -> None:
        logger.info("Refreshing park data")
        parks_data = await self.client.fetch_parks()
        logger.info("Received %d parks from QueueTimes", len(parks_data))
        if not parks_data:
            logger.warning("No parks returned from QueueTimes")
        for park in parks_data:
            park_id = str(park.get("id") or park.get("slug"))
            park_name = park.get("name")
            park_info = self.parks.setdefault(park_id, ParkInfo(id=park_id, name=park_name))
            await self._update_park(park_info)

    async def _update_park(self, park: ParkInfo) -> None:
        rides = await self.client.fetch_wait_times(park.id)
        logger.info("Updating %s (%s) with %d rides", park.name, park.id, len(rides))
        if not rides:
            logger.warning("No rides found for park %s", park.id)
        timestamp = datetime.now(UTC)
        for ride in rides:
            ride_id = str(ride.get("id"))
            name = ride.get("name")
            wait = ride.get("wait_time")
            is_open = ride.get("is_open", True) and ride.get("status", "") not in {"Closed", "Refurbishment"}
            ride_info = park.rides.setdefault(ride_id, RideInfo(id=ride_id, name=name))
            if is_open and wait is not None:
                ride_info.stats.mark_open()
                ride_info.stats.add_wait(wait, timestamp)
                logger.debug("Recorded wait %s for ride %s", wait, name)
            else:
                ride_info.stats.mark_closed()
                logger.debug("Skipping ride %s (open=%s wait=%s)", name, is_open, wait)

    def wait_times(self, park_id: int | str | None = None) -> List[dict]:
        rides: List[RideInfo] = []
        if park_id is None:
            for park in self.parks.values():
                rides.extend(park.rides.values())
        else:
            park = self.parks.get(park_id)
            if not park:
                return []
            rides = list(park.rides.values())

        results = []
        for ride in rides:
            stats = ride.stats
            results.append(
                {
                    "id": ride.id,
                    "name": ride.name,
                    "current_wait": stats.current_wait,
                    "mean": stats.mean(),
                    "stdev": stats.stdev(),
                    "is_open": stats.is_open,
                    "is_unusually_low": stats.is_unusually_low(),
                }
            )
        return results

client = QueueTimesClient()
service = DisneyWaitsService(client)
app = FastAPI()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@app.on_event("startup")
async def startup() -> None:
    try:
        await service.update()
    except Exception:  # pragma: no cover - log and continue
        logger.exception("Failed initial update")

    async def poller() -> None:
        while True:
            try:
                await service.update()
            except Exception:  # pragma: no cover - log and continue
                logger.exception("Failed to update wait times")
            await asyncio.sleep(300)

    asyncio.create_task(poller())


@app.on_event("shutdown")
async def shutdown() -> None:
    await client.close()


@app.get("/parks")
async def parks() -> Dict[str, str]:
    return {str(p.id): p.name for p in service.parks.values()}


@app.get("/wait_times")
@app.get("/parks/wait_times")
async def wait_times_endpoint(park_id: str | None = None) -> List[dict]:
    return service.wait_times(park_id)

