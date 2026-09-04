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

    @classmethod
    def _estimate_fallback_starts(
        cls,
        map_info: Dict[str, Any],
        anchor: int,
        gap: int = 35,
    ) -> List[int]:
        """Estimates round starts from VLR duration when CV detection fails."""
        rounds = map_info.get("rounds", [])
        if not rounds:
            return []
        duration = int(map_info.get("duration_seconds", 0) or 0)
        n = len(rounds)
        if duration > 0 and n > 0:
            # Distribute official duration across rounds + inter-round gaps.
            avg_round = max(60, (duration - gap * (n - 1)) // n)
            cadence = avg_round + max(0, gap)
        else:
            cadence = 90 + max(0, gap)
        return [int(anchor) + i * int(cadence) for i in range(n)]

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
            auto_detect_cv: If True, uses local 144p video to detect exact 1:39 round starts
        """
        video_id = cls.extract_youtube_id(youtube_url)
        clean_yt_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else youtube_url
        overrides = round_overrides or {}

        # Parse anchor configuration (keys always int, values in seconds).
        map_anchors: Dict[int, int] = {}
        if isinstance(anchors, dict):
            for k, v in anchors.items():
                try:
                    map_anchors[int(str(k).strip())] = cls.parse_time_to_seconds(v)
                except (ValueError, TypeError, AttributeError):
                    continue
        elif anchors is not None:
            # Single anchor passed, assign to Map 1
            map_anchors[1] = cls.parse_time_to_seconds(anchors)

        # Default Map 1 anchor to 192 if not provided
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
                        m_num = int(map_info["map_number"])
                        r_count = len(map_info.get("rounds", []))
                        if r_count == 0:
                            continue
                        if m_num in map_anchors:
                            m_start = map_anchors[m_num]
                        elif m_num == 1:
                            m_start = 180
                        else:
                            # Start after previous map completed + intermission
                            prev_ends = [
                                d["end"] for prev_m in cv_data_by_map.values() for d in prev_m.values()
                            ]
                            m_start = max(prev_ends) + 180 if prev_ends else 3600
                        duration_hint = int(map_info.get("duration_seconds", 0) or 0)
                        m_end = m_start + (duration_hint + 600 if duration_hint > 0 else 3600)
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
            map_num = int(map_info["map_number"])
            map_name = map_info.get("map_name", f"Map {map_num}")
            rounds = map_info.get("rounds", [])

            map_start_anchor = map_anchors.get(map_num, 192)
            # Fallback estimation when CV missed this map: avg round + gap cadence.
            fallback_starts = cls._estimate_fallback_starts(
                map_info=map_info,
                anchor=map_start_anchor,
                gap=default_pause_gap_seconds,
            )
            processed_rounds = []

            for idx, r in enumerate(rounds):
                rnd_num = int(r["round"])
                win_type = r.get("win_type", "elim")

                # 1. Start & End priority: Explicit override > CV Detection > Fallback estimate.
                override_key = f"{map_num}-{rnd_num}"
                override_data = overrides.get(override_key)
                if map_num == 1 and not override_data:
                    override_data = overrides.get(str(rnd_num))

                estimated = False
                if override_data and "start" in override_data:
                    round_start = cls.parse_time_to_seconds(override_data["start"])
                elif map_num in cv_data_by_map and rnd_num in cv_data_by_map[map_num]:
                    round_start = int(cv_data_by_map[map_num][rnd_num]["start"])
                else:
                    round_start = fallback_starts[idx] if idx < len(fallback_starts) else map_start_anchor + idx * 125
                    estimated = True

                if override_data and "end" in override_data:
                    round_end = cls.parse_time_to_seconds(override_data["end"])
                elif map_num in cv_data_by_map and rnd_num in cv_data_by_map[map_num]:
                    round_end = int(cv_data_by_map[map_num][rnd_num]["end"])
                else:
                    round_end = round_start + 85
                    estimated = True

                # 2. Apply buy-phase (pre) and celebration (post) buffers, unless explicitly overridden.
                if not (override_data and "start" in override_data):
                    round_start = max(0, round_start - int(pre_buffer_seconds or 0))
                if not (override_data and "end" in override_data):
                    round_end = round_end + int(post_buffer_seconds or 0)
                if round_end <= round_start:
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
                    "score_display": r.get("score_display", ""),
                    "estimated": estimated and not bool(override_data),
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
