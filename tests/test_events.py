import os, sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.service import DisneyWaitsService

class OpeningClient:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch_parks(self):
        return [{"id": 1, "name": "Park"}]

    async def fetch_wait_times(self, park_id):
        self.calls += 1
        if self.calls == 1:
            return [{"id": 10, "name": "Ride", "wait_time": 0, "is_open": False}]
        else:
            return [{"id": 10, "name": "Ride", "wait_time": 5, "is_open": True}]

class LowWaitClient:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch_parks(self):
        return [{"id": 1, "name": "Park"}]

    async def fetch_wait_times(self, park_id):
        self.calls += 1
        if self.calls < 4:
            return [{"id": 10, "name": "Ride", "wait_time": 10, "is_open": True}]
        else:
            return [{"id": 10, "name": "Ride", "wait_time": 5, "is_open": True}]

def test_service_notifies_on_open():
    service = DisneyWaitsService(OpeningClient())
    queue = service.subscribe({"10"})
    asyncio.run(service.update())  # ride closed
    asyncio.run(service.update())  # ride opens
    event = asyncio.run(queue.get())
    assert event["event"] == "opened"
    assert event["ride_id"] == "10"

def test_service_notifies_on_low_wait():
    service = DisneyWaitsService(LowWaitClient())
    queue = service.subscribe({"10"})
    for _ in range(3):
        asyncio.run(service.update())  # build history
    asyncio.run(service.update())  # drop to low wait
    event = asyncio.run(queue.get())
    assert event["event"] == "unusually_low"
    assert event["ride_id"] == "10"
