"""
Auto-Stream Valorant Clean Player - Web Application & Local Server
Provides REST API endpoints for processing VODs, syncing with VLR.gg, and serving the continuous player SPA.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.vlr_scraper import VLRScraper
from backend.timeline_mapper import TimelineMapper
from backend.exporter import JSONExporter

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TIMESTAMPS_FILE = BASE_DIR / "timestamps.json"

app = FastAPI(
    title="Valorant Clean Player API",
    description="Backend API for syncing Valorant YouTube VODs with VLR.gg match data",
    version="1.0.0"
)

# Enable CORS for local cross-origin usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcessRequest(BaseModel):
    vlr_url: str = Field(..., description="VLR.gg match URL or ID")
    youtube_url: str = Field(..., description="YouTube VOD URL or Video ID")
    anchor_seconds: Optional[Union[int, str]] = Field(192, description="Start anchor for Map 1")
    anchors: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Per-map anchors dict")
    round_overrides: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Explicit round overrides dict")
    pre_buffer_seconds: int = Field(8, description="Pre-round buy phase buffer in seconds")
    post_buffer_seconds: int = Field(5, description="Post-round celebration buffer in seconds")
    auto_detect_cv: bool = Field(True, description="Enable automatic 1:39 storyboard CV detection")


class SaveRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="Full or modified timestamps payload")


@app.get("/api/status")
def get_status():
    """Health check and file status."""
    has_timestamps = TIMESTAMPS_FILE.exists()
    return {
        "status": "online",
        "has_timestamps_file": has_timestamps,
        "timestamps_file_path": str(TIMESTAMPS_FILE)
    }


@app.get("/api/timestamps")
def get_timestamps():
    """Retrieves current timestamps.json or default configuration."""
    if not TIMESTAMPS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="No timestamps.json found. Please process a match first or generate via CLI."
        )
    try:
        data = JSONExporter.load_json(TIMESTAMPS_FILE)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading timestamps file: {str(e)}")


@app.post("/api/process")
def process_vod_match(req: ProcessRequest):
    """
    Parses VLR.gg match data, synchronizes with YouTube VOD timeline,
    generates clean continuous intervals, and saves to timestamps.json.
    """
    try:
        # 1. Scrape VLR.gg
        vlr_data = VLRScraper.parse_match(req.vlr_url)
        
        # 2. Setup Anchors
        anchors = req.anchors or {}
        if not anchors and req.anchor_seconds is not None:
            anchors = {"1": req.anchor_seconds}
        
        # 3. Generate Timeline
        timeline_result = TimelineMapper.generate_timeline(
            vlr_data=vlr_data,
            youtube_url=req.youtube_url,
            anchors=anchors,
            round_overrides=req.round_overrides,
            pre_buffer_seconds=req.pre_buffer_seconds,
            post_buffer_seconds=req.post_buffer_seconds,
            auto_detect_cv=req.auto_detect_cv
        )

        # 4. Save to timestamps.json
        JSONExporter.save_json(timeline_result, TIMESTAMPS_FILE)

        return JSONResponse(content={
            "success": True,
            "message": "Timestamps generated and saved successfully.",
            "data": timeline_result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process match: {str(e)}")


@app.post("/api/save")
def save_custom_timestamps(req: SaveRequest):
    """Saves user-modified timestamps (from calibration/producer mode) to timestamps.json."""
    try:
        JSONExporter.save_json(req.data, TIMESTAMPS_FILE)
        return {"success": True, "message": "Updated timestamps saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save timestamps: {str(e)}")


class ScanRequest(BaseModel):
    youtube_url: str = Field(..., description="YouTube VOD URL or Video ID")
    start_seconds: int = Field(180, description="Start scanning second")
    end_seconds: int = Field(4000, description="End scanning second")


@app.post("/api/scan_storyboards")
def scan_storyboards(req: ScanRequest):
    """Runs automated CV/template matching on YouTube storyboards to detect round intervals."""
    try:
        from backend.video_detector import VideoDetector
        intervals = VideoDetector.scan_timeline(
            youtube_url=req.youtube_url,
            start_sec=req.start_seconds,
            end_sec=req.end_seconds,
            step_sec=10
        )
        return {"success": True, "detected_intervals_count": len(intervals), "intervals": intervals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scanning failed: {str(e)}")


class ThumbnailRequest(BaseModel):
    youtube_url: str = Field(..., description="YouTube VOD URL or Video ID")
    start_seconds: int = Field(..., description="Start window seconds")
    end_seconds: int = Field(..., description="End window seconds")
    step_seconds: int = Field(10, description="Step interval in seconds")


@app.post("/api/thumbnails")
def get_candidate_thumbnails(req: ThumbnailRequest):
    """Generates visual thumbnail cards for candidate round start and end points."""
    try:
        from backend.video_detector import VideoDetector
        thumbs = VideoDetector.get_candidate_thumbnails(
            youtube_url=req.youtube_url,
            start_sec=req.start_seconds,
            end_sec=req.end_seconds,
            step_sec=req.step_seconds
        )
        return {"success": True, "count": len(thumbs), "thumbnails": thumbs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnails: {str(e)}")


# Mount static assets directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serves the main SPA index.html."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Valorant Clean Player</h1><p>Index file not found in static/</p>")
    return FileResponse(str(index_path))


def run_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run("app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    run_server()
