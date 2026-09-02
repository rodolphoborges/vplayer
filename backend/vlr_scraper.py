"""
VLR.gg Match Scraper
Extracts match metadata, maps, scores, and round-by-round statistics from VLR.gg match pages.
"""

import re
import urllib.request
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup


class VLRScraper:
    """Scraper for VLR.gg match pages."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    @staticmethod
    def normalize_url(url_or_id: str) -> str:
        """Ensures the input is a valid full VLR.gg match URL."""
        url_or_id = str(url_or_id).strip()
        if url_or_id.isdigit():
            return f"https://www.vlr.gg/{url_or_id}"
        if not url_or_id.startswith("http"):
            if url_or_id.startswith("vlr.gg"):
                return f"https://{url_or_id}"
            return f"https://www.vlr.gg/{url_or_id}"
        return url_or_id

    @classmethod
    def fetch_html(cls, url: str) -> str:
        """Fetches raw HTML from a VLR.gg URL."""
        norm_url = cls.normalize_url(url)
        req = urllib.request.Request(norm_url, headers=cls.DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")

    @classmethod
    def parse_duration_to_seconds(cls, duration_str: str) -> int:
        """Converts duration strings like '57:26' or '1:02:15' into total seconds."""
        if not duration_str:
            return 0
        parts = [int(p) for p in re.findall(r"\d+", duration_str)]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 1:
            return parts[0]
        return 0

    @classmethod
    def parse_match(cls, url_or_html: str, is_html: bool = False) -> Dict[str, Any]:
        """
        Parses a VLR.gg match page into structured data.
        
        Args:
            url_or_html: Either the URL to fetch or raw HTML content.
            is_html: If True, treats url_or_html as raw HTML string.
        """
        html = url_or_html if is_html else cls.fetch_html(url_or_html)
        soup = BeautifulSoup(html, "html.parser")

        # 1. Event & Match Title
        event_el = soup.select_one(".match-header-super .match-header-event")
        event_series_el = soup.select_one(".match-header-super .match-header-event-series")
        event_name = " ".join(event_el.get_text().split()) if event_el else "VALORANT Tournament"
        event_series = " ".join(event_series_el.get_text().split()) if event_series_el else ""
        full_event = f"{event_name} - {event_series}".strip(" -")

        # 2. Teams
        team_links = soup.select(".match-header-link-name")
        team1_name = "Team 1"
        team2_name = "Team 2"
        if len(team_links) >= 1:
            t1_title = team_links[0].select_one(".wf-title-med")
            team1_name = t1_title.get_text(strip=True) if t1_title else team_links[0].get_text(strip=True)
        if len(team_links) >= 2:
            t2_title = team_links[1].select_one(".wf-title-med")
            team2_name = t2_title.get_text(strip=True) if t2_title else team_links[1].get_text(strip=True)

        # Team Logos
        team_logos = [img.get("src") for img in soup.select(".match-header-link img, .match-header-team img") if img.get("src")]
        team1_logo = ("https:" + team_logos[0]) if (len(team_logos) > 0 and team_logos[0].startswith("//")) else (team_logos[0] if team_logos else "")
        team2_logo = ("https:" + team_logos[1]) if (len(team_logos) > 1 and team_logos[1].startswith("//")) else (team_logos[1] if len(team_logos) > 1 else "")

        # 3. Overall Match Score
        score_el = soup.select_one(".match-header-vs-score")
        match_score_raw = " ".join(score_el.get_text().split()) if score_el else "0 : 0"
        score_match = re.search(r"(\d+)\s*[:\-]\s*(\d+)", match_score_raw)
        match_score = f"{score_match.group(1)} : {score_match.group(2)}" if score_match else match_score_raw

        # 4. Maps Navigation
        maps_nav = []
        for item in soup.select(".vm-stats-gamesnav-item"):
            game_id = item.get("data-game-id")
            if not game_id or game_id == "all":
                continue
            text = " ".join(item.get_text().split())
            # Format is typically "1 Lotus" or "2 Sunset" or "1 Ascent PICK"
            m = re.search(r"(\d+)\s*([A-Za-z]+)", text)
            map_num = int(m.group(1)) if m else len(maps_nav) + 1
            map_name = m.group(2) if m else text
            
            # Check if picked by someone
            is_pick = "PICK" in text.upper()
            
            maps_nav.append({
                "game_id": game_id,
                "map_number": map_num,
                "map_name": map_name,
                "is_pick": is_pick,
            })

        # 5. Extract Details For Each Map
        maps_data = []
        for g_nav in maps_nav:
            game_id = g_nav["game_id"]
            map_num = g_nav["map_number"]
            map_name = g_nav["map_name"]

            game_container = soup.select_one(f'.vm-stats-game[data-game-id="{game_id}"]')
            if not game_container:
                continue

            # Header info (scores & duration)
            duration_str = "0:00"
            t1_score = 0
            t2_score = 0
            header = game_container.select_one(".vm-stats-game-header")
            if header:
                dur_el = header.select_one(".map-duration")
                if dur_el:
                    duration_str = dur_el.get_text(strip=True)
                score_spans = header.select(".score")
                if len(score_spans) >= 2:
                    try:
                        t1_score = int(score_spans[0].get_text(strip=True))
                        t2_score = int(score_spans[1].get_text(strip=True))
                    except ValueError:
                        pass

            duration_seconds = cls.parse_duration_to_seconds(duration_str)

            # Round by round extraction
            rounds: List[Dict[str, Any]] = []
            rounds_container = game_container.select_one(".vlr-rounds")
            if rounds_container:
                cols = rounds_container.select(".vlr-rounds-row-col")
                running_t1 = 0
                running_t2 = 0

                for col in cols:
                    rnd_num_el = col.select_one(".rnd-num")
                    if not rnd_num_el:
                        continue
                    
                    try:
                        rnd_num = int(rnd_num_el.get_text(strip=True))
                    except ValueError:
                        continue

                    # Squares representing team 1 (top) and team 2 (bottom)
                    sqs = col.select(".rnd-sq")
                    winner = "Unknown"
                    win_type = "elim"
                    side = "Attack"

                    for s_idx, sq in enumerate(sqs):
                        classes = sq.get("class", [])
                        if "mod-win" in classes:
                            if s_idx == 0:
                                winner = team1_name
                                running_t1 += 1
                            else:
                                winner = team2_name
                                running_t2 += 1

                            if "mod-t" in classes:
                                side = "Attack"
                            elif "mod-ct" in classes:
                                side = "Defense"

                        img = sq.find("img")
                        if img and img.get("src"):
                            src = img.get("src")
                            if "elim" in src:
                                win_type = "elim"
                            elif "defuse" in src:
                                win_type = "defuse"
                            elif "boom" in src:
                                win_type = "detonation"
                            elif "time" in src:
                                win_type = "time"

                    # Skip placeholder columns for unplayed rounds
                    if winner == "Unknown":
                        continue

                    rounds.append({
                        "map": map_num,
                        "map_name": map_name,
                        "round": rnd_num,
                        "winner": winner,
                        "win_type": win_type,
                        "side": side,
                        "score_team1": running_t1,
                        "score_team2": running_t2,
                        "score_display": f"{running_t1} - {running_t2}"
                    })

            maps_data.append({
                "map_number": map_num,
                "map_name": map_name,
                "duration": duration_str,
                "duration_seconds": duration_seconds,
                "team1_score": t1_score,
                "team2_score": t2_score,
                "score": f"{t1_score} - {t2_score}",
                "winner": team1_name if t1_score > t2_score else (team2_name if t2_score > t1_score else "Tie"),
                "rounds_count": len(rounds),
                "rounds": rounds,
            })

        return {
            "vlr_url": cls.normalize_url(url_or_html) if not is_html else "",
            "event": full_event,
            "team1": {
                "name": team1_name,
                "logo": team1_logo,
            },
            "team2": {
                "name": team2_name,
                "logo": team2_logo,
            },
            "match_score": match_score,
            "total_maps": len(maps_data),
            "maps": maps_data,
        }
