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

async def _fetch(monkeypatch, payload):
    client = QueueTimesClient()
    async def fake_get(url):
        return DummyResp(payload)
    monkeypatch.setattr(client.client, "get", fake_get)
    parks = await client.fetch_parks()
    await client.close()
    return parks

def test_fetch_parks_list(monkeypatch):
    parks = asyncio.run(_fetch(monkeypatch, [{"id": 1, "name": "Park"}]))
    assert parks == [{"id": 1, "name": "Park"}]

def test_fetch_parks_dict(monkeypatch):
    parks = asyncio.run(_fetch(monkeypatch, {"parks": [{"id": 2, "name": "Park2"}]}))
    assert parks == [{"id": 2, "name": "Park2"}]
