"""
Tests for VLR Scraper, Timeline Mapper, Exporter, and FastAPI Web API.
"""

import pytest
from pathlib import Path
from backend.vlr_scraper import VLRScraper
from backend.timeline_mapper import TimelineMapper
from backend.exporter import JSONExporter
from fastapi.testclient import TestClient
from app import app


SAMPLE_VLR_URL = "https://www.vlr.gg/734312/loud-vs-mibr-vct-2026-americas-stage-2-lr2"
SAMPLE_YT_URL = "https://www.youtube.com/watch?v=B5G9Qpv31_o"


def test_vlr_scraper_parse():
    data = VLRScraper.parse_match(SAMPLE_VLR_URL)
    assert "team1" in data
    assert "team2" in data
    assert data["team1"]["name"] == "LOUD"
    assert data["team2"]["name"] == "MIBR"
    assert len(data["maps"]) >= 2
    
    # Map 1: Lotus
    map1 = data["maps"][0]
    assert map1["map_name"] == "Lotus"
    assert map1["rounds_count"] > 0
    assert len(map1["rounds"]) == map1["rounds_count"]

    # Check sample round properties
    r1 = map1["rounds"][0]
    assert r1["round"] == 1
    assert r1["winner"] in ("LOUD", "MIBR")
    assert r1["win_type"] in ("elim", "defuse", "detonation", "time")


def test_timeline_mapper_generate():
    vlr_data = VLRScraper.parse_match(SAMPLE_VLR_URL)
    result = TimelineMapper.generate_timeline(
        vlr_data=vlr_data,
        youtube_url=SAMPLE_YT_URL,
        anchors={"1": 192, "2": 4200},
        pre_buffer_seconds=8,
        post_buffer_seconds=5
    )

    assert result["video_id"] == "B5G9Qpv31_o"
    assert len(result["timeline"]) > 0
    
    # Check that all intervals are strictly ordered with start < end
    for item in result["timeline"]:
        assert item["start"] < item["end"]
        assert item["map"] in (1, 2)
        assert item["round"] >= 1


def test_exporter_validation():
    sample_flat = [
        {"map": 1, "round": 1, "start": 192, "end": 280, "winner": "LOUD", "win_type": "elim"},
        {"map": 1, "round": 2, "start": 310, "end": 395, "winner": "MIBR", "win_type": "defuse"}
    ]
    validated = JSONExporter.validate_timeline_array(sample_flat)
    assert len(validated) == 2
    assert validated[0]["start"] == 192

    # Negative test: invalid start >= end
    with pytest.raises(ValueError):
        JSONExporter.validate_timeline_array([{"map": 1, "round": 1, "start": 200, "end": 100}])


def test_fastapi_endpoints():
    client = TestClient(app)
    
    # Save original timestamps content
    ts_path = Path("timestamps.json")
    original_content = ts_path.read_text(encoding="utf-8") if ts_path.exists() else None

    try:
        # Status
        res = client.get("/api/status")
        assert res.status_code == 200
        assert res.json()["status"] == "online"

        # Timestamps
        res = client.get("/api/timestamps")
        assert res.status_code in (200, 404)

        # Save
        res = client.post("/api/save", json={
            "data": {
                "video_id": "B5G9Qpv31_o",
                "timeline": [{"map": 1, "round": 1, "start": 192, "end": 280}]
            }
        })
        assert res.status_code == 200
        assert res.json()["success"] is True
    finally:
        # Restore original timestamps content
        if original_content is not None:
            ts_path.write_text(original_content, encoding="utf-8")
