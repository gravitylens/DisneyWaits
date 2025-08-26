import os, sys, asyncio
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.service import DisneyWaitsService


class DummyClient:
    async def fetch_parks(self):
        return [{"id": 1, "name": "Test Park"}]

    async def fetch_wait_times(self, park_id):
        return [
            {"id": 10, "name": "Ride A", "wait_time": 5, "is_open": True},
            {"id": 11, "name": "Ride B", "wait_time": 0, "is_open": False},
        ]


def test_persistence(tmp_path: Path):
    data_path = tmp_path / "data.json"
    service = DisneyWaitsService(DummyClient(), data_path=data_path)
    asyncio.run(service.update())
    service.save()

    new_service = DisneyWaitsService(DummyClient(), data_path=data_path)
    new_service.load()
    waits = new_service.wait_times()
    assert len(waits) == 2
    ride_a = next(r for r in waits if r["id"] == "10")
    assert ride_a["current_wait"] == 5
