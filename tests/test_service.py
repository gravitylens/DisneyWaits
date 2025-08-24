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
    assert ride_a["is_open"] is True
    assert ride_a["recently_opened"] is False
    assert ride_b["current_wait"] is None
    assert ride_b["is_open"] is False
    assert ride_b["recently_opened"] is False
    assert service.wait_times("missing") == []


def test_wait_times_filters():
    service = DisneyWaitsService(DummyClient())
    import asyncio

    asyncio.run(service.update())
    now = datetime.now(UTC)
    ride_a_stats = service.parks["1"].rides["10"].stats
    for _ in range(4):
        ride_a_stats.add_wait(10, now)
    ride_a_stats.add_wait(5, now)

    waits_open = service.wait_times(is_open=True)
    assert [w["id"] for w in waits_open] == ["10"]
    waits_closed = service.wait_times(is_open=False)
    assert [w["id"] for w in waits_closed] == ["11"]
    waits_low = service.wait_times(is_unusually_low=True)
    assert [w["id"] for w in waits_low] == ["10"]
    waits_not_low = service.wait_times(is_unusually_low=False)
    assert [w["id"] for w in waits_not_low] == ["11"]


def test_wait_times_accepts_int_park_id():
    service = DisneyWaitsService(DummyClient())
    import asyncio

    asyncio.run(service.update())
    assert service.wait_times(1) == service.wait_times("1")
    assert service.wait_times(1, is_open=True)[0]["id"] == "10"


class FlippingClient:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch_parks(self):
        return [{"id": 1, "name": "Test Park"}]

    async def fetch_wait_times(self, park_id):
        self.calls += 1
        if self.calls == 1:
            return [{"id": 10, "name": "Ride", "wait_time": 0, "is_open": False}]
        else:
            return [{"id": 10, "name": "Ride", "wait_time": 5, "is_open": True}]


def test_recently_opened_service():
    service = DisneyWaitsService(FlippingClient())
    import asyncio

    asyncio.run(service.update())  # ride closed
    asyncio.run(service.update())  # ride opens
    waits = service.wait_times()
    assert waits[0]["recently_opened"] is True
    asyncio.run(service.update())  # subsequent poll
    assert service.wait_times()[0]["recently_opened"] is False


def test_wait_times_endpoint():
    global_service.parks = {
        "1": ParkInfo(
            id="1",
            name="Test",
            rides={
                "10": RideInfo(id="10", name="Ride", stats=RideStats()),
                "11": RideInfo(id="11", name="Other", stats=RideStats()),
            },
        )
    }
    now = datetime.now(UTC)
    stats_a = global_service.parks["1"].rides["10"].stats
    stats_a.add_wait(10, now)
    stats_a.add_wait(10, now)
    stats_a.add_wait(5, now)
    stats_b = global_service.parks["1"].rides["11"].stats
    stats_b.mark_closed()
    client = TestClient(app)
    resp = client.get("/wait_times")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ride = next(r for r in data if r["id"] == "10")
    assert ride["current_wait"] == 5
    assert ride["is_open"] is True
    assert ride["recently_opened"] is False
    assert ride["is_unusually_low"] is True
    assert ride["mean"] == pytest.approx(8.333333333333334)
    assert ride["stdev"] == pytest.approx(2.886751345948129)
    other = next(r for r in data if r["id"] == "11")
    assert other["current_wait"] is None
    assert other["is_open"] is False
    assert other["recently_opened"] is False
    assert other["is_unusually_low"] is False
    assert other["mean"] is None
    assert other["stdev"] is None
    assert client.get("/wait_times", params={"park_id": "1"}).json() == data
    assert client.get("/wait_times", params={"park_id": "2"}).json() == []
    assert client.get("/parks/wait_times").json() == data
    assert client.get("/parks/wait_times", params={"park_id": "1"}).json() == data
    assert client.get("/wait_times", params={"is_open": "true"}).json() == [ride]
    assert client.get("/wait_times", params={"is_open": "false"}).json() == [other]
    assert client.get("/wait_times", params={"is_unusually_low": "true"}).json() == [ride]
    assert client.get(
        "/wait_times",
        params={"is_unusually_low": "false"},
    ).json() == [other]

