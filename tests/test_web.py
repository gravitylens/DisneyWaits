import os, sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.service import app
from pathlib import Path


def test_index_page_served():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert '<select id="park-select">' in text
    assert '<table id="rides-table">' in text


def test_index_filters_zero_mean():
    path = Path(__file__).resolve().parent.parent / "disneywaits" / "index.html"
    text = path.read_text()
    assert "ride.mean !== 0" in text


def test_index_marks_low_waits_bold():
    path = Path(__file__).resolve().parent.parent / "disneywaits" / "index.html"
    text = path.read_text()
    assert ".low {" in text
    assert "font-weight: bold" in text
    assert "row.classList.add('low')" in text
