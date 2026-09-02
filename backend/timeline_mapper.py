"""
Timeline Mapper
Maps VLR.gg structured round data to YouTube VOD timestamps using calibrated anchors and buffers.
"""

import os
import shutil
import re
from typing import Dict, List, Any, Optional, Union


class TimelineMapper:
    """Calculates continuous clean intervals for YouTube VODs based on VLR match data."""

    @staticmethod
    def extract_youtube_id(url_or_id: str) -> str:
        """Extracts the 11-character YouTube video ID from various URL formats."""
        if not url_or_id:
            return ""
        url_or_id = url_or_id.strip()
        # Direct ID
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
            return url_or_id
        # Standard or short URL patterns
        patterns = [
            r"(?:v=|\/)([a-zA-Z0-9_-]{11})(?:[&?]|$)",
            r"youtu\.be\/([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/embed\/([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/live\/([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/v\/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        return url_or_id

    @staticmethod
    def parse_time_to_seconds(time_val: Union[int, float, str]) -> int:
        """Converts time inputs ('192', '03:12', '1:02:15') into seconds."""
        if isinstance(time_val, (int, float)):
            return int(time_val)
        time_str = str(time_val).strip()
        if not time_str:
            return 0
        if time_str.isdigit():
            return int(time_str)
        parts = [int(p) for p in re.findall(r"\d+", time_str)]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
        return 0

    # Remover estimate_round_duration para focar apenas no CV

    @classmethod
    def generate_timeline(
        cls,
        vlr_data: Dict[str, Any],
        youtube_url: str,
        anchors: Optional[Union[int, str, Dict[str, Any]]] = None,
        round_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        pre_buffer_seconds: int = 8,
        post_buffer_seconds: int = 5,
        default_pause_gap_seconds: int = 35,
        auto_detect_cv: bool = True,
    ) -> Dict[str, Any]:
        """
        Builds the clean continuous timeline structure.
        
        Args:
            vlr_data: Structured data from VLRScraper.parse_match
            youtube_url: Full YouTube URL or Video ID
            anchors: Either a single starting second for Map 1 (e.g. 192) or a dict per map { "1": 192, "2": 3950 }
            round_overrides: Dict of explicit round start/end overrides, e.g. {"1-1": {"start": 192, "end": 300}}
            pre_buffer_seconds: Seconds before barrier drop (buy phase preview)
            post_buffer_seconds: Seconds after round ends (reaction & victory text)
            default_pause_gap_seconds: Approximate gap skipped between rounds
            auto_detect_cv: If True, uses YouTube storyboards to detect exact 1:39 round starts
        """
        video_id = cls.extract_youtube_id(youtube_url)
        clean_yt_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else youtube_url
        overrides = round_overrides or {}

        # Parse anchor configuration
        map_anchors: Dict[int, int] = {}
        if isinstance(anchors, dict):
            for k, v in anchors.items():
                try:
                    map_anchors[int(k)] = cls.parse_time_to_seconds(v)
                except ValueError:
                    pass
        elif anchors is not None:
            # Single anchor passed, assign to Map 1
            map_anchors[1] = cls.parse_time_to_seconds(anchors)
        
        # Default Map 1 anchor to 192 (or 0 if not provided)
        if 1 not in map_anchors:
            map_anchors[1] = 192

        # Automatic CV detection of round starts and ends via 144p local video parsing
        cv_data_by_map: Dict[int, Dict[int, Dict[str, int]]] = {}
        if auto_detect_cv and video_id:
            local_vid_path = f"temp_cv_{video_id}.mp4"
            downloaded = False
            try:
                from backend.video_detector import VideoDetector
                print(f"[TimelineMapper] Downloading 144p local video for high-accuracy CV detection...")
                if not os.path.exists(local_vid_path):
                    if os.path.exists("temp_inspect.mp4"):
                        import shutil
                        shutil.copy("temp_inspect.mp4", local_vid_path)
                        downloaded = True
                    else:
                        downloaded = VideoDetector.download_144p_video(video_id, local_vid_path)
                else:
                    downloaded = True

                if downloaded:
                    for map_info in vlr_data.get("maps", []):
                        m_num = map_info["map_number"]
                        r_count = len(map_info.get("rounds", []))
                        if r_count == 0:
                            continue
                        if m_num in map_anchors:
                            m_start = map_anchors[m_num]
                        elif str(m_num) in map_anchors:
                            m_start = map_anchors[str(m_num)]
                        elif m_num == 1:
                            m_start = 180
                        else:
                            # Start after previous map completed + intermission
                            prev_ends = [
                                d["end"] for prev_m in cv_data_by_map.values() for d in prev_m.values()
                            ]
                            m_start = max(prev_ends) + 250 if prev_ends else 3600
                        m_end = m_start + 3600
                        print(f"[TimelineMapper] Scanning Map {m_num} ({map_info.get('map_name')}) from {m_start}s to {m_end}s...")
                        detected = VideoDetector.detect_round_starts(
                            local_video_path=local_vid_path,
                            total_rounds_expected=r_count,
                            anchor_sec=m_start,
                            end_scan_sec=m_end,
                            step_sec=1
                        )
                        if detected and len(detected) > 0:
                            cv_data_by_map[m_num] = {}
                            for d in detected:
                                cv_data_by_map[m_num][d["round"]] = {
                                    "start": d["start"],
                                    "end": d["end"]
                                }
                                print(f"  -> CV R{d['round']}: {d['start']}s to {d['end']}s")
            except Exception as e:
                print(f"[TimelineMapper] Local video CV failed: {e}")
            finally:
                if not os.environ.get("KEEP_TEMP_VIDEO") and not os.path.exists("temp_inspect.mp4"):
                    if os.path.exists(local_vid_path):
                        try:
                            os.remove(local_vid_path)
                            print(f"[TimelineMapper] Cleaned up temporary video.")
                        except:
                            pass

        processed_maps = []
        flat_timeline = []

        for map_info in vlr_data.get("maps", []):
            map_num = map_info["map_number"]
            map_name = map_info["map_name"]
            rounds = map_info.get("rounds", [])

            map_start_anchor = map_anchors.get(map_num, 192)
            processed_rounds = []

            for r in rounds:
                rnd_num = r["round"]
                win_type = r.get("win_type", "elim")

                # 1. Start & End priority: Explicit override > CV Detection > Missing
                override_key = f"{map_num}-{rnd_num}"
                override_data = overrides.get(override_key) or overrides.get(str(rnd_num)) if map_num == 1 else overrides.get(override_key)
                
                round_start = 0
                round_end = 0

                if override_data and "start" in override_data:
                    round_start = cls.parse_time_to_seconds(override_data["start"])
                elif map_num in cv_data_by_map and rnd_num in cv_data_by_map[map_num]:
                    round_start = cv_data_by_map[map_num][rnd_num]["start"]
                else:
                    print(f"[TimelineMapper] Missing start for Map {map_num} Round {rnd_num}. CV might have failed.")
                    continue
                
                if override_data and "end" in override_data:
                    round_end = cls.parse_time_to_seconds(override_data["end"])
                elif map_num in cv_data_by_map and rnd_num in cv_data_by_map[map_num]:
                    round_end = cv_data_by_map[map_num][rnd_num]["end"]
                else:
                    print(f"[TimelineMapper] Missing end for Map {map_num} Round {rnd_num}. CV might have failed.")
                    round_end = round_start + 60

                round_entry = {
                    "map": map_num,
                    "map_name": map_name,
                    "round": rnd_num,
                    "start": round_start,
                    "end": round_end,
                    "duration": round_end - round_start,
                    "winner": r.get("winner", "Unknown"),
                    "win_type": win_type,
                    "side": r.get("side", "Attack"),
                    "score_team1": r.get("score_team1", 0),
                    "score_team2": r.get("score_team2", 0),
                    "score_display": r.get("score_display", "")
                }

                processed_rounds.append(round_entry)
                flat_timeline.append({
                    "map": map_num,
                    "round": rnd_num,
                    "start": round_start,
                    "end": round_end,
                    "winner": r.get("winner", "Unknown"),
                    "win_type": win_type,
                    "score": r.get("score_display", "")
                })

            processed_maps.append({
                "map_number": map_num,
                "map_name": map_name,
                "duration": map_info.get("duration", ""),
                "duration_seconds": map_info.get("duration_seconds", 0),
                "score": map_info.get("score", ""),
                "winner": map_info.get("winner", ""),
                "team1_score": map_info.get("team1_score", 0),
                "team2_score": map_info.get("team2_score", 0),
                "anchor_start": map_start_anchor,
                "rounds_count": len(processed_rounds),
                "rounds": processed_rounds
            })

        total_clean_duration = sum(r["end"] - r["start"] for r in flat_timeline)

        return {
            "video_id": video_id,
            "video_url": clean_yt_url,
            "vlr_url": vlr_data.get("vlr_url", ""),
            "match_info": {
                "event": vlr_data.get("event", ""),
                "team1": vlr_data.get("team1", {}),
                "team2": vlr_data.get("team2", {}),
                "score": vlr_data.get("match_score", ""),
            },
            "settings": {
                "pre_buffer_seconds": pre_buffer_seconds,
                "post_buffer_seconds": post_buffer_seconds,
                "anchors": map_anchors
            },
            "summary": {
                "total_maps": len(processed_maps),
                "total_rounds": len(flat_timeline),
                "total_clean_duration_seconds": total_clean_duration,
                "total_clean_duration_formatted": f"{total_clean_duration // 60}:{total_clean_duration % 60:02d}"
            },
            "maps": processed_maps,
            "timeline": flat_timeline,
        }
