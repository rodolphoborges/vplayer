"""
Generate timestamps.json via CLI.

Example:
    python generate_timestamps.py --vlr "https://www.vlr.gg/734312/loud-vs-mibr-vct-2026-americas-stage-2-lr2" --yt "https://www.youtube.com/watch?v=B5G9Qpv31_o" --anchor 192 --output timestamps.json
    python generate_timestamps.py --vlr 734312 --yt B5G9Qpv31_o --anchors "1=192,2=3926" --no-cv --format flat
"""

import argparse
import json
import sys
from pathlib import Path

from backend.vlr_scraper import VLRScraper
from backend.timeline_mapper import TimelineMapper
from backend.exporter import JSONExporter


def parse_anchors_arg(anchors_str: str | None) -> dict:
    result: dict = {}
    if not anchors_str:
        return result
    for part in anchors_str.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        result[k.strip()] = v.strip()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Valorant clean-player timestamps.json")
    parser.add_argument("--vlr", required=True, help="VLR.gg match URL or ID")
    parser.add_argument("--yt", required=True, help="YouTube VOD URL or 11-char Video ID")
    parser.add_argument("--anchor", default="192", help="Anchor for Map 1 in seconds or MM:SS (default: 192)")
    parser.add_argument("--anchors", default="", help='Per-map anchors, e.g. "1=192,2=3926" (overrides --anchor)')
    parser.add_argument("--pre-buffer", type=int, default=8, help="Buy-phase seconds before round start")
    parser.add_argument("--post-buffer", type=int, default=5, help="Celebration seconds after round end")
    parser.add_argument("--gap", type=int, default=35, help="Fallback gap between rounds when CV fails")
    parser.add_argument("--output", default="timestamps.json", help="Output JSON path")
    parser.add_argument("--format", choices=["full", "flat"], default="full", help="full payload or flat timeline array")
    parser.add_argument("--no-cv", action="store_true", help="Disable 144p CV detection (use anchor estimation)")
    args = parser.parse_args()

    per_map = parse_anchors_arg(args.anchors)
    anchors = per_map if per_map else args.anchor

    print(f"[CLI] Scraping {args.vlr} ...")
    vlr_data = VLRScraper.parse_match(args.vlr)
    print(f"[CLI] Found {vlr_data.get('total_maps', 0)} maps.")

    result = TimelineMapper.generate_timeline(
        vlr_data=vlr_data,
        youtube_url=args.yt,
        anchors=anchors,
        pre_buffer_seconds=args.pre_buffer,
        post_buffer_seconds=args.post_buffer,
        default_pause_gap_seconds=args.gap,
        auto_detect_cv=not args.no_cv,
    )

    output_path = Path(args.output)
    if args.format == "flat":
        JSONExporter.save_json(result.get("timeline", []), output_path)
    else:
        JSONExporter.save_json(result, output_path)

    summary = result.get("summary", {})
    print(f"[CLI] Saved {output_path} — {summary.get('total_rounds', 0)} rounds, "
          f"clean {summary.get('total_clean_duration_formatted', '')}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
