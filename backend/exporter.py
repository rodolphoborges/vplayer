"""
Exporter & JSON Manager
Handles serialization, validation, and saving of timestamps.json data.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Union, Optional


class JSONExporter:
    """Handles serialization and validation of timeline intervals."""

    @staticmethod
    def validate_timeline_array(data: Any) -> List[Dict[str, Any]]:
        """Validates that a flat timeline array meets required format."""
        if not isinstance(data, list):
            raise ValueError("Timeline must be a list of round objects.")
        
        validated = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"Item at index {idx} is not an object.")
            if "map" not in item or "round" not in item or "start" not in item or "end" not in item:
                raise ValueError(f"Item at index {idx} is missing required fields ('map', 'round', 'start', 'end').")
            
            start = int(item["start"])
            end = int(item["end"])
            if start >= end:
                raise ValueError(f"Round {item['round']} on map {item['map']} has start ({start}) >= end ({end}).")

            validated.append({
                "map": int(item["map"]),
                "round": int(item["round"]),
                "start": start,
                "end": end,
                "winner": str(item.get("winner", "")),
                "win_type": str(item.get("win_type", "elim")),
                "score": str(item.get("score", ""))
            })
        
        # Sort chronologically by map and round
        validated.sort(key=lambda x: (x["map"], x["round"]))
        return validated

    @classmethod
    def save_json(
        cls,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        filepath: Union[str, Path] = "timestamps.json",
        indent: int = 2
    ) -> Path:
        """Saves data to a JSON file."""
        target_path = Path(filepath)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        
        return target_path
    
    export_to_file = save_json

    @classmethod
    def load_json(cls, filepath: Union[str, Path] = "timestamps.json") -> Dict[str, Any]:
        """Loads and normalizes a JSON timestamps file."""
        target_path = Path(filepath)
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # If it's a raw array, wrap it into standard structure
        if isinstance(data, list):
            validated = cls.validate_timeline_array(data)
            return {
                "video_id": "",
                "video_url": "",
                "vlr_url": "",
                "match_info": {"event": "Custom Match", "score": ""},
                "timeline": validated,
                "maps": []
            }
        
        return data
