from __future__ import annotations

import asyncio
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
        parks_data = await self.client.fetch_parks()
        for park in parks_data:
            park_id = park.get("id") or park.get("slug")
            park_name = park.get("name")
            park_info = self.parks.setdefault(park_id, ParkInfo(id=park_id, name=park_name))
            await self._update_park(park_info)

    async def _update_park(self, park: ParkInfo) -> None:
        data = await self.client.fetch_wait_times(park.id)
        lands = data.get("lands", [])
        timestamp = datetime.now(UTC)
        for land in lands:
            for ride in land.get("rides", []):
                ride_id = ride.get("id")
                name = ride.get("name")
                wait = ride.get("wait_time")
                is_open = ride.get("is_open", True) and ride.get("status", "") not in {"Closed", "Refurbishment"}
                ride_info = park.rides.setdefault(ride_id, RideInfo(id=ride_id, name=name))
                if is_open and wait is not None:
                    ride_info.stats.mark_open()
                    ride_info.stats.add_wait(wait, timestamp)
                else:
                    ride_info.stats.mark_closed()

    def park_wait_times(self, park_id: int | str) -> List[dict]:
        park = self.parks.get(park_id)
        if not park:
            return []
        results = []
        for ride in park.rides.values():
            stats = ride.stats
            results.append(
                {
                    "id": ride.id,
                    "name": ride.name,
                    "current_wait": stats.current_wait,
                    "mean": stats.mean(),
                    "stdev": stats.stdev(),
                    "is_unusually_low": stats.is_unusually_low(),
                }
            )
        return results


client = QueueTimesClient()
service = DisneyWaitsService(client)
app = FastAPI()


@app.on_event("startup")
async def startup() -> None:
    async def poller() -> None:
        while True:
            try:
                await service.update()
            except Exception:  # pragma: no cover - logging omitted for brevity
                pass
            await asyncio.sleep(300)

    asyncio.create_task(poller())


@app.on_event("shutdown")
async def shutdown() -> None:
    await client.close()


@app.get("/parks")
async def parks() -> Dict[str, str]:
    return {str(p.id): p.name for p in service.parks.values()}


@app.get("/parks/{park_id}/wait_times")
async def wait_times(park_id: str) -> List[dict]:
    return service.park_wait_times(park_id)

