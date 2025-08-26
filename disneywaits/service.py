from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Set, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
from pathlib import Path

from .queue_times import QueueTimesClient
from .stats import RideStats, WaitEntry


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
    def __init__(self, client: QueueTimesClient, data_path: Path | None = None) -> None:
        self.client = client
        self.parks: Dict[int | str, ParkInfo] = {}
        self.data_path = data_path or Path(__file__).with_name("data.json")
        self._subscribers: List[Tuple[asyncio.Queue, Set[str]]] = []

    # ------------------ Persistence helpers ------------------
    def save(self) -> None:
        """Write current park data to disk."""
        data: Dict[str, Any] = {}
        for park_id, park in self.parks.items():
            park_data: Dict[str, Any] = {"id": park.id, "name": park.name, "rides": {}}
            for ride_id, ride in park.rides.items():
                stats = ride.stats
                ride_data = {
                    "id": ride.id,
                    "name": ride.name,
                    "stats": {
                        "history": [
                            {"timestamp": entry.timestamp.isoformat(), "wait": entry.wait}
                            for entry in stats.history
                        ],
                        "current_wait": stats.current_wait,
                        "is_open": stats.is_open,
                        "recently_opened": stats.recently_opened,
                    },
                }
                park_data["rides"][ride_id] = ride_data
            data[park_id] = park_data

        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_path.write_text(json.dumps(data))

    def load(self) -> None:
        """Load park data from disk if available."""
        if not self.data_path.exists():
            return
        raw = json.loads(self.data_path.read_text())
        parks: Dict[int | str, ParkInfo] = {}
        for park_id, pdata in raw.items():
            park = ParkInfo(id=pdata["id"], name=pdata["name"])
            for ride_id, rdata in pdata.get("rides", {}).items():
                sdata = rdata.get("stats", {})
                stats = RideStats()
                stats.history = deque(
                    WaitEntry(datetime.fromisoformat(e["timestamp"]), e["wait"])
                    for e in sdata.get("history", [])
                )
                stats.current_wait = sdata.get("current_wait")
                stats.is_open = sdata.get("is_open", True)
                stats.recently_opened = sdata.get("recently_opened", False)
                ride = RideInfo(id=rdata["id"], name=rdata["name"], stats=stats)
                park.rides[ride_id] = ride
            parks[park_id] = park
        self.parks = parks

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
                if ride_info.stats.recently_opened:
                    self._notify(ride_id, "opened", ride_info)
                if ride_info.stats.is_unusually_low():
                    self._notify(ride_id, "unusually_low", ride_info)
            else:
                ride_info.stats.mark_closed()
                logger.debug("Skipping ride %s (open=%s wait=%s)", name, is_open, wait)

    def wait_times(
        self,
        park_id: int | str | None = None,
        **filters: Any,
    ) -> List[dict]:
        rides: List[RideInfo] = []
        if park_id is None:
            for park in self.parks.values():
                rides.extend(park.rides.values())
        else:
            park = self.parks.get(str(park_id))
            if not park:
                return []
            rides = list(park.rides.values())

        results = []
        for ride in rides:
            stats = ride.stats
            entry = {
                "id": ride.id,
                "name": ride.name,
                "current_wait": stats.current_wait,
                "mean": stats.mean(),
                "stdev": stats.stdev(),
                "is_open": stats.is_open,
                "recently_opened": stats.recently_opened,
                "is_unusually_low": stats.is_unusually_low(),
            }

            matched = True
            for key, value in filters.items():
                if value is None:
                    continue
                if entry.get(key) != value:
                    matched = False
                    break
            if matched:
                results.append(entry)
        return results

    def subscribe(self, ride_ids: Set[str]) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append((queue, ride_ids))
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers = [s for s in self._subscribers if s[0] is not queue]

    def _notify(self, ride_id: str, event: str, ride: RideInfo) -> None:
        data = {
            "ride_id": ride_id,
            "ride_name": ride.name,
            "event": event,
            "wait": ride.stats.current_wait,
        }
        for queue, ids in list(self._subscribers):
            if not ids or ride_id in ids:
                queue.put_nowait(data)

client = QueueTimesClient()
service = DisneyWaitsService(client)
app = FastAPI()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@app.on_event("startup")
async def startup() -> None:
    service.load()
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
    service.save()
    await client.close()


@app.get("/parks")
async def parks(id: str | None = None, name: str | None = None) -> Dict[str, str]:
    data = {str(p.id): p.name for p in service.parks.values()}
    if id is not None:
        data = {pid: pname for pid, pname in data.items() if pid == id}
    if name is not None:
        data = {pid: pname for pid, pname in data.items() if pname == name}
    return data


@app.get("/wait_times")
@app.get("/parks/wait_times")
async def wait_times_endpoint(
    park_id: str | None = None,
    id: str | None = None,
    name: str | None = None,
    current_wait: int | None = None,
    mean: float | None = None,
    stdev: float | None = None,
    is_open: bool | None = None,
    recently_opened: bool | None = None,
    is_unusually_low: bool | None = None,
) -> List[dict]:
    return service.wait_times(
        park_id,
        id=id,
        name=name,
        current_wait=current_wait,
        mean=mean,
        stdev=stdev,
        is_open=is_open,
        recently_opened=recently_opened,
        is_unusually_low=is_unusually_low,
    )


@app.get("/events")
async def events(request: Request, ride_ids: str | None = None) -> EventSourceResponse:
    ids = set(ride_ids.split(",")) if ride_ids else set()
    queue = service.subscribe(ids)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = await queue.get()
                yield {"event": data["event"], "data": json.dumps(data)}
        finally:
            service.unsubscribe(queue)

    return EventSourceResponse(event_generator())


@app.get("/", response_class=HTMLResponse)
async def web_index() -> str:
    index_path = Path(__file__).with_name("index.html")
    return index_path.read_text()

