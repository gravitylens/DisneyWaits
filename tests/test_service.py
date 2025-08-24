import os, sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.service import (
    DisneyWaitsService,
    ParkInfo,
    RideInfo,
    app,
    service as global_service,
)
from disneywaits.stats import RideStats
from fastapi.testclient import TestClient
from datetime import UTC, datetime


class DummyClient:
    async def fetch_parks(self):
        return [{"id": 1, "name": "Test Park"}]

    async def fetch_wait_times(self, park_id):
        return [
            {"id": 10, "name": "Ride A", "wait_time": 5, "is_open": True},
            {"id": 11, "name": "Ride B", "wait_time": 0, "is_open": False},
        ]


def test_service_update_and_query():
    service = DisneyWaitsService(DummyClient())
    import asyncio

    asyncio.run(service.update())
    waits_all = service.wait_times()
    assert len(waits_all) == 2
    waits_filtered = service.wait_times("1")
    assert waits_filtered == waits_all
    ride_a = next(r for r in waits_all if r["id"] == "10")
    ride_b = next(r for r in waits_all if r["id"] == "11")
    assert ride_a["current_wait"] == 5
    assert ride_b["current_wait"] is None
    assert service.wait_times("missing") == []


def test_wait_times_endpoint():
    global_service.parks = {
        "1": ParkInfo(
            id="1",
            name="Test",
            rides={"10": RideInfo(id="10", name="Ride", stats=RideStats())},
        )
    }
    global_service.parks["1"].rides["10"].stats.add_wait(5, datetime.now(UTC))
    client = TestClient(app)
    resp = client.get("/wait_times")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {
            "id": "10",
            "name": "Ride",
            "current_wait": 5,
            "mean": 5,
            "stdev": None,
            "is_unusually_low": False,
        }
    ]
    assert client.get("/wait_times", params={"park_id": "1"}).json() == data
    assert client.get("/wait_times", params={"park_id": "2"}).json() == []
    assert client.get("/parks/wait_times").json() == data
    assert client.get("/parks/wait_times", params={"park_id": "1"}).json() == data

