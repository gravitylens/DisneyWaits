import os, sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.service import app


def test_index_page_served():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert '<select id="park-select">' in text
    assert '<table id="rides-table">' in text
