import asyncio
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.queue_times import QueueTimesClient

class DummyResp:
    def __init__(self, data):
        self._data = data
    def json(self):
        return self._data
    def raise_for_status(self):
        pass

async def _fetch_parks(monkeypatch, payload):
    client = QueueTimesClient()
    async def fake_get(url):
        return DummyResp(payload)
    monkeypatch.setattr(client.client, "get", fake_get)
    parks = await client.fetch_parks()
    await client.close()
    return parks

def test_fetch_parks_filters_wda(monkeypatch):
    payload = [
        {"name": "Other", "parks": [{"id": 1, "name": "Other Park"}]},
        {"name": "Walt Disney Attractions", "parks": [
            {"id": 10, "name": "Magic Kingdom"},
            {"id": 11, "name": "Epcot"},
        ]},
    ]
    parks = asyncio.run(_fetch_parks(monkeypatch, payload))
    assert parks == [
        {"id": 10, "name": "Magic Kingdom"},
        {"id": 11, "name": "Epcot"},
    ]

async def _fetch_waits(monkeypatch, payload):
    client = QueueTimesClient()
    async def fake_get(url):
        return DummyResp(payload)
    monkeypatch.setattr(client.client, "get", fake_get)
    waits = await client.fetch_wait_times(1)
    await client.close()
    return waits

def test_fetch_wait_times_flattens(monkeypatch):
    payload = {
        "lands": [
            {"rides": [{"id": 1}, {"id": 2}]},
            {"rides": [{"id": 3}]},
        ]
    }
    waits = asyncio.run(_fetch_waits(monkeypatch, payload))
    assert [r["id"] for r in waits] == [1, 2, 3]


def test_fetch_wait_times_flattens_nested(monkeypatch):
    payload = {
        "lands": [
            {
                "areas": [
                    {"rides": [{"id": 4}]},
                    {"areas": [{"rides": [{"id": 5}]}]},
                ]
            }
        ]
    }
    waits = asyncio.run(_fetch_waits(monkeypatch, payload))
    assert [r["id"] for r in waits] == [4, 5]
