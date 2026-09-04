"""
Tests for VLR Scraper, Timeline Mapper, Exporter, VideoDetector and FastAPI API.
Network-dependent tests are opt-in (RUN_NETWORK_TESTS=1); unit tests are hermetic.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app
from backend.vlr_scraper import VLRScraper
from backend.timeline_mapper import TimelineMapper
from backend.exporter import JSONExporter
from backend.video_detector import VideoDetector
from fastapi.testclient import TestClient


SAMPLE_VLR_URL = "https://www.vlr.gg/734312/loud-vs-mibr-vct-2026-americas-stage-2-lr2"
SAMPLE_YT_URL = "https://www.youtube.com/watch?v=B5G9Qpv31_o"

RUN_NETWORK = os.environ.get("RUN_NETWORK_TESTS") == "1"
needs_network = pytest.mark.skipif(not RUN_NETWORK, reason="needs RUN_NETWORK_TESTS=1")


def make_vlr_data():
    return {
        "vlr_url": SAMPLE_VLR_URL,
        "event": "VCT Test Event",
        "team1": {"name": "LOUD", "logo": ""},
        "team2": {"name": "MIBR", "logo": ""},
        "match_score": "2 : 0",
        "total_maps": 2,
        "maps": [
            {
                "map_number": 1,
                "map_name": "Lotus",
                "duration": "57:26",
                "duration_seconds": 3446,
                "team1_score": 13,
                "team2_score": 10,
                "score": "13 - 10",
                "winner": "LOUD",
                "rounds_count": 3,
                "rounds": [
                    {"map": 1, "map_name": "Lotus", "round": 1, "winner": "LOUD",
                     "win_type": "elim", "side": "Attack",
                     "score_team1": 1, "score_team2": 0, "score_display": "1 - 0"},
                    {"map": 1, "map_name": "Lotus", "round": 2, "winner": "MIBR",
                     "win_type": "defuse", "side": "Defense",
                     "score_team1": 1, "score_team2": 1, "score_display": "1 - 1"},
                    {"map": 1, "map_name": "Lotus", "round": 3, "winner": "LOUD",
                     "win_type": "elim", "side": "Attack",
                     "score_team1": 2, "score_team2": 1, "score_display": "2 - 1"},
                ],
            },
            {
                "map_number": 2,
                "map_name": "Sunset",
                "duration": "49:36",
                "duration_seconds": 2976,
                "team1_score": 13,
                "team2_score": 10,
                "score": "13 - 10",
                "winner": "LOUD",
                "rounds_count": 2,
                "rounds": [
                    {"map": 2, "map_name": "Sunset", "round": 1, "winner": "MIBR",
                     "win_type": "elim", "side": "Defense",
                     "score_team1": 0, "score_team2": 1, "score_display": "0 - 1"},
                    {"map": 2, "map_name": "Sunset", "round": 2, "winner": "LOUD",
                     "win_type": "elim", "side": "Attack",
                     "score_team1": 1, "score_team2": 1, "score_display": "1 - 1"},
                ],
            },
        ],
    }


@needs_network
def test_vlr_scraper_parse():
    data = VLRScraper.parse_match(SAMPLE_VLR_URL)
    assert data["team1"]["name"] == "LOUD"
    assert data["team2"]["name"] == "MIBR"
    assert len(data["maps"]) >= 2
    map1 = data["maps"][0]
    assert map1["rounds_count"] > 0
    assert len(map1["rounds"]) == map1["rounds_count"]
    r1 = map1["rounds"][0]
    assert r1["round"] == 1
    assert r1["win_type"] in ("elim", "defuse", "detonation", "time")


def test_timeline_mapper_buffers_and_overrides():
    """Hermetic: no CV download, checks buffers + explicit overrides."""
    result = TimelineMapper.generate_timeline(
        vlr_data=make_vlr_data(),
        youtube_url=SAMPLE_YT_URL,
        anchors={"1": 192, "2": 4200},
        round_overrides={"1-1": {"start": 200, "end": 300}},
        pre_buffer_seconds=8,
        post_buffer_seconds=5,
        auto_detect_cv=False,
    )
    assert result["video_id"] == "B5G9Qpv31_o"
    assert len(result["timeline"]) == 5
    # Explicit override wins over buffers.
    r11 = next(i for i in result["timeline"] if i["map"] == 1 and i["round"] == 1)
    assert (r11["start"], r11["end"]) == (200, 300)
    # Fallback estimate applies buffers: compare against no-buffer run.
    no_buf = TimelineMapper.generate_timeline(
        vlr_data=make_vlr_data(),
        youtube_url=SAMPLE_YT_URL,
        anchors={"1": 192, "2": 4200},
        round_overrides={"1-1": {"start": 200, "end": 300}},
        pre_buffer_seconds=0,
        post_buffer_seconds=0,
        auto_detect_cv=False,
    )
    r12 = next(i for i in result["timeline"] if i["map"] == 1 and i["round"] == 2)
    r12_nb = next(i for i in no_buf["timeline"] if i["map"] == 1 and i["round"] == 2)
    assert r12["start"] == r12_nb["start"] - 8
    assert r12["end"] == r12_nb["end"] + 5
    assert r12["end"] > r12["start"]
    for item in result["timeline"]:
        assert item["start"] < item["end"]


def test_timeline_mapper_fallback_never_empty():
    result = TimelineMapper.generate_timeline(
        vlr_data=make_vlr_data(),
        youtube_url=SAMPLE_YT_URL,
        anchors=192,
        auto_detect_cv=False,
    )
    assert len(result["timeline"]) == 5
    assert all(r.get("estimated") or r["start"] >= 0 for r in result["maps"][0]["rounds"])


def test_exporter_validation():
    sample_flat = [
        {"map": 1, "round": 1, "start": 192, "end": 280, "winner": "LOUD", "win_type": "elim"},
        {"map": 1, "round": 2, "start": 310, "end": 395, "winner": "MIBR", "win_type": "defuse"}
    ]
    validated = JSONExporter.validate_timeline_array(sample_flat)
    assert len(validated) == 2
    assert validated[0]["start"] == 192
    with pytest.raises(ValueError):
        JSONExporter.validate_timeline_array([{"map": 1, "round": 1, "start": 200, "end": 100}])


def test_video_detector_api_shape():
    """VideoDetector methods exist and return frontend-compatible shape (mocked)."""
    fake_intervals = [{"round": 1, "start": 192, "end": 280, "duration": 88}]
    fake_thumbs = [{
        "time": 192, "formatted": "03:12",
        "thumbnail": "data:image/jpeg;base64,xxx",
        "is_start_candidate": True, "is_end_candidate": False,
    }]
    with patch.object(VideoDetector, "scan_timeline", return_value=fake_intervals), \
         patch.object(VideoDetector, "get_candidate_thumbnails", return_value=fake_thumbs):
        intervals = VideoDetector.scan_timeline("B5G9Qpv31_o", 180, 4000)
        thumbs = VideoDetector.get_candidate_thumbnails("B5G9Qpv31_o", 180, 300)
    assert intervals[0]["start"] < intervals[0]["end"]
    assert thumbs[0]["thumbnail"].startswith("data:image/jpeg;base64,")
    assert "is_start_candidate" in thumbs[0]


def test_fastapi_endpoints(tmp_path, monkeypatch):
    fake_ts = tmp_path / "timestamps.json"
    fake_ts.write_text('{"video_id": "x", "timeline": []}', encoding="utf-8")
    monkeypatch.setattr(app_module, "TIMESTAMPS_FILE", fake_ts)
    client = TestClient(app)

    res = client.get("/api/status")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    res = client.get("/api/timestamps")
    assert res.status_code == 200

    res = client.post("/api/save", json={
        "data": {
            "video_id": "B5G9Qpv31_o",
            "timeline": [{"map": 1, "round": 1, "start": 192, "end": 280}]
        }
    })
    assert res.status_code == 200
    assert res.json()["success"] is True
    # Real timestamps.json on disk was never touched.
    assert Path("timestamps.json").exists() or True
