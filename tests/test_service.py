import os, sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.service import DisneyWaitsService


class DummyClient:
    async def fetch_parks(self):
        return [{"id": 1, "name": "Test Park"}]

    async def fetch_wait_times(self, park_id):
        return {
            "lands": [
                {
                    "rides": [
                        {"id": 10, "name": "Ride A", "wait_time": 5, "is_open": True},
                        {"id": 11, "name": "Ride B", "wait_time": 0, "is_open": False},
                    ]
                }
            ]
        }


def test_service_update_and_query():
    service = DisneyWaitsService(DummyClient())
    import asyncio

    asyncio.run(service.update())
    waits = service.park_wait_times(1)
    assert len(waits) == 2
    ride_a = next(r for r in waits if r["id"] == 10)
    ride_b = next(r for r in waits if r["id"] == 11)
    assert ride_a["current_wait"] == 5
    assert ride_b["current_wait"] is None
