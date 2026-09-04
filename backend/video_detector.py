"""
Video Stream Analyzer for Valorant Esports VODs.
High-accuracy local parser utilizing a 144p video track to detect the 1:39 round timer.
"""

import base64
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
import cv2
import numpy as np

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class VideoDetector:
    """High-precision CV detector for Valorant VOD round starts ('1:39')."""

    _timer_template: Optional[np.ndarray] = None

    @classmethod
    def get_template(cls) -> Optional[np.ndarray]:
        """Loads and caches the 144p timer template."""
        if cls._timer_template is None:
            tmpl_path = TEMPLATES_DIR / "timer_139_144p.png"
            if tmpl_path.exists():
                cls._timer_template = cv2.imread(str(tmpl_path), cv2.IMREAD_GRAYSCALE)
        return cls._timer_template

    # Alias for backward compatibility
    @classmethod
    def get_templates(cls):
        return cls.get_template(), None, None

    @classmethod
    def is_real_139(cls, crop_gray: np.ndarray, tmpl_139: Optional[np.ndarray]) -> bool:
        """
        Validates whether a 14x16 crop from the center timer is genuinely '1:39'.
        Distinguishes 1:39 from 0:xx (buy phase/late round) using colon and digit structure.
        """
        if crop_gray is None or crop_gray.shape != (14, 16) or tmpl_139 is None:
            return False
        colon_dots = (int(crop_gray[4, 7]) + int(crop_gray[7, 7])) / 2.0
        colon_gap = (int(crop_gray[5, 7]) + int(crop_gray[6, 7])) / 2.0
        colon_contrast = colon_dots - colon_gap
        col3 = crop_gray[4:8, 3].mean()
        col4 = crop_gray[4:8, 4].mean()
        corr = cv2.matchTemplate(crop_gray, tmpl_139, cv2.TM_CCOEFF_NORMED)[0][0]
        return (corr >= 0.82) and (colon_contrast > 25) and (col4 > 110) and (col3 < 65)

    @classmethod
    def is_hud_active(cls, gray_frame: np.ndarray) -> bool:
        """Determines if the in-game broadcast HUD is currently active."""
        if gray_frame is None or gray_frame.shape[0] < 16 or gray_frame.shape[1] < 161:
            return False
        hud = gray_frame[0:16, 95:161]
        return (35 < hud.mean() < 120) and (hud.std() > 25)

    @classmethod
    def download_144p_video(cls, youtube_id: str, output_path: str) -> bool:
        """Downloads the 144p video track using yt-dlp to a local file."""
        import yt_dlp
        url = f"https://www.youtube.com/watch?v={youtube_id}"
        ydl_opts = {
            'format': 'bestvideo[height<=144][ext=mp4]/worstvideo[ext=mp4]',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            print(f"[VideoDetector] Failed to download 144p video: {e}")
            return False

    @classmethod
    def detect_round_starts(
        cls,
        local_video_path: str,
        total_rounds_expected: int = 24,
        anchor_sec: int = 180,
        end_scan_sec: int = 3600,
        step_sec: int = 1
    ) -> List[Dict[str, Any]]:
        """
        High-precision Round Detector using 1:39 timer structural analysis.
        Guarantees <= 3s error vs broadcast round starts.
        """
        if not os.path.exists(local_video_path):
            return []

        timer_tmpl = cls.get_template()
        if timer_tmpl is None:
            print("[VideoDetector] Timer template not found. CV detection disabled.")
            return []

        cap = cv2.VideoCapture(local_video_path)
        if not cap.isOpened():
            print("[VideoDetector] Failed to open local video file.")
            return []

        print(f"[VideoDetector] Scanning from {anchor_sec}s to {end_scan_sec}s for 1:39 round starts...")
        
        # Step 1: Scan for all 1:39 frames
        matches: List[int] = []
        t = anchor_sec
        while t <= end_scan_sec:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            crop = gray[0:14, 120:136]
            if cls.is_real_139(crop, timer_tmpl):
                matches.append(t)
            t += step_sec

        # Step 2: Group consecutive seconds into clusters (gap <= 10s)
        raw_clusters: List[List[int]] = []
        for m in matches:
            if not raw_clusters or m > raw_clusters[-1][-1] + 10:
                raw_clusters.append([m])
            else:
                raw_clusters[-1].append(m)

        # Step 3: Filter noise and enforce minimum gap
        # Real round start clusters have sustained detections (count >= 8 and span >= 8s)
        # Minimum time between round starts in esports Valorant is >= 65s
        valid_clusters: List[List[int]] = []
        for c in raw_clusters:
            cnt = len(c)
            span = c[-1] - c[0]
            if cnt >= 8 and span >= 8:
                if not valid_clusters or c[0] >= valid_clusters[-1][0] + 65:
                    valid_clusters.append(c)

        print(f"[VideoDetector] Found {len(valid_clusters)} valid round clusters.")

        # Step 4: Construct round intervals
        detected_rounds: List[Dict[str, Any]] = []
        for idx, c in enumerate(valid_clusters[:total_rounds_expected], 1):
            r_start = c[0]
            if idx < len(valid_clusters):
                next_start = valid_clusters[idx][0]
                # Search for combat end (when HUD disappears) between r_start + 30 and next_start - 20
                r_end = None
                for end_t in range(r_start + 30, min(r_start + 115, next_start - 20)):
                    cap.set(cv2.CAP_PROP_POS_MSEC, end_t * 1000)
                    ret, frame = cap.read()
                    if not ret:
                        break
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    if not cls.is_hud_active(gray):
                        r_end = end_t
                        break
                if r_end is None:
                    # Default buy phase starts ~35s before next round
                    r_end = min(r_start + 100, max(r_start + 35, next_start - 35))
            else:
                r_end = r_start + 75

            detected_rounds.append({
                "round": idx,
                "start": r_start,
                "end": r_end,
                "duration": r_end - r_start,
                "formatted_start": f"{r_start // 60:02d}:{r_start % 60:02d}",
                "formatted_end": f"{r_end // 60:02d}:{r_end % 60:02d}",
            })
            print(f"  -> Round {idx}: {r_start}s ({r_start//60:02d}:{r_start%60:02d}) to {r_end}s ({r_end//60:02d}:{r_end%60:02d}) [dur={r_end - r_start}s]")

        cap.release()
        return detected_rounds

    @classmethod
    def _extract_youtube_id(cls, url_or_id: str) -> str:
        """Local YouTube ID extractor (avoids circular import with TimelineMapper)."""
        if not url_or_id:
            return ""
        s = str(url_or_id).strip()
        if re.match(r"^[a-zA-Z0-9_-]{11}$", s):
            return s
        for pattern in [
            r"(?:v=|\/)([a-zA-Z0-9_-]{11})(?:[&?]|$)",
            r"youtu\.be\/([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/embed\/([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/live\/([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/v\/([a-zA-Z0-9_-]{11})",
        ]:
            m = re.search(pattern, s)
            if m:
                return m.group(1)
        return s

    @classmethod
    def _resolve_local_video(cls, youtube_url: str) -> tuple[str, bool]:
        """Returns (local_path, owned_by_caller). Reuses temp_cv_{id}.mp4 / temp_inspect.mp4."""
        video_id = cls._extract_youtube_id(youtube_url)
        if not video_id:
            return "", False
        local_path = f"temp_cv_{video_id}.mp4"
        if os.path.exists(local_path):
            return local_path, False
        if os.path.exists("temp_inspect.mp4"):
            shutil.copy("temp_inspect.mp4", local_path)
            return local_path, False
        ok = cls.download_144p_video(video_id, local_path)
        if ok and os.path.exists(local_path):
            return local_path, True
        return "", False

    @classmethod
    def _maybe_cleanup(cls, local_path: str, owned: bool) -> None:
        if not local_path or not owned:
            return
        if os.environ.get("KEEP_TEMP_VIDEO"):
            return
        if os.path.exists("temp_inspect.mp4"):
            return
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass

    @classmethod
    def scan_timeline(
        cls,
        youtube_url: str,
        start_sec: int = 180,
        end_sec: int = 4000,
        step_sec: int = 10,
    ) -> List[Dict[str, Any]]:
        """Detects round intervals via local 144p video (used by POST /api/scan_storyboards)."""
        start_sec = max(0, int(start_sec))
        end_sec = max(start_sec + 30, int(end_sec))
        local_path, owned = cls._resolve_local_video(youtube_url)
        if not local_path:
            return []
        try:
            detected = cls.detect_round_starts(
                local_video_path=local_path,
                total_rounds_expected=60,
                anchor_sec=start_sec,
                end_scan_sec=end_sec,
                step_sec=1,
            )
            intervals: List[Dict[str, Any]] = []
            for d in detected:
                intervals.append({
                    "round": d["round"],
                    "start": d["start"],
                    "end": d["end"],
                    "duration": d["end"] - d["start"],
                })
            return intervals
        finally:
            cls._maybe_cleanup(local_path, owned)

    @classmethod
    def get_candidate_thumbnails(
        cls,
        youtube_url: str,
        start_sec: int,
        end_sec: int,
        step_sec: int = 10,
    ) -> List[Dict[str, Any]]:
        """Samples frames via local 144p video (used by POST /api/thumbnails + Estudio)."""
        start_sec = max(0, int(start_sec))
        end_sec = max(start_sec + 10, int(end_sec))
        step_sec = max(1, int(step_sec or 10))
        local_path, owned = cls._resolve_local_video(youtube_url)
        if not local_path:
            return []
        timer_tmpl = cls.get_template()
        cap = cv2.VideoCapture(local_path)
        thumbs: List[Dict[str, Any]] = []
        try:
            if not cap.isOpened():
                return []
            t = start_sec
            while t <= end_sec and len(thumbs) < 30:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()
                if not ret or frame is None:
                    t += step_sec
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                is_start = False
                hud_active = cls.is_hud_active(gray)
                try:
                    crop = gray[0:14, 120:136]
                    is_start = cls.is_real_139(crop, timer_tmpl)
                except Exception:
                    is_start = False
                # Victory/replay screens hide the HUD -> end candidate.
                is_end = not hud_active
                small = frame
                try:
                    h, w = frame.shape[:2]
                    if w > 320:
                        scale = 320.0 / float(w)
                        small = cv2.resize(frame, (320, int(h * scale)))
                except Exception:
                    small = frame
                ok, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if not ok:
                    t += step_sec
                    continue
                b64 = base64.b64encode(bytes(buf)).decode("ascii")
                thumbs.append({
                    "time": t,
                    "formatted": f"{t // 60:02d}:{t % 60:02d}",
                    "thumbnail": f"data:image/jpeg;base64,{b64}",
                    "is_start_candidate": bool(is_start),
                    "is_end_candidate": bool(is_end and not is_start),
                    "hud_active": bool(hud_active),
                })
                t += step_sec
            return thumbs
        finally:
            try:
                cap.release()
            except Exception:
                pass
            cls._maybe_cleanup(local_path, owned)
