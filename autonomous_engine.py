#!/usr/bin/env python3
"""
Autonomous Viral Astrology Content Engine
Runs daily to generate short-form video scripts and render reels.
"""

import os
import json
import time
import datetime as dt
import urllib.request
import subprocess
import random
import re
import shutil
from pathlib import Path

import requests
import feedparser
import swisseph as swe
from dotenv import load_dotenv

# Load env variables (Meta tokens, Groq key, etc.)
load_dotenv()

# Import helpers from the existing pipeline
import viral_horoscope_pipeline as vhp

# --- 1. Cosmic Scanner ---
class CosmicScanner:
    @staticmethod
    def get_today_context():
        now = dt.datetime.now(dt.timezone.utc)
        # Convert to Julian Day
        year, month, day, h, m, s = now.year, now.month, now.day, now.hour, now.minute, now.second + now.microsecond / 1000000.0
        jd = swe.julday(year, month, day, h + m/60.0 + s/3600.0)
        
        # Calculate planets
        planets = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, 
            "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER, 
            "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
        }
        
        zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
                        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        
        positions = {}
        retrogrades = []
        for name, planet_id in planets.items():
            res, _ = swe.calc_ut(jd, planet_id)
            sign_idx = int(res[0] / 30)
            sign = zodiac_signs[sign_idx]
            is_retrograde = res[3] < 0
            
            positions[name] = {"sign": sign, "degree": round(res[0] % 30, 2), "retrograde": is_retrograde}
            if is_retrograde and name not in ["Sun", "Moon"]:
                retrogrades.append(name)
        
        # Check moon phase
        sun_long = positions["Sun"]["degree"] + (zodiac_signs.index(positions["Sun"]["sign"]) * 30)
        moon_long = positions["Moon"]["degree"] + (zodiac_signs.index(positions["Moon"]["sign"]) * 30)
        
        phase_angle = (moon_long - sun_long) % 360
        if phase_angle < 15 or phase_angle > 345:
            moon_phase = "New Moon"
        elif 165 < phase_angle < 195:
            moon_phase = "Full Moon"
        else:
            moon_phase = "Waxing/Waning"

        return {
            "date": now.isoformat(),
            "moon_phase": moon_phase,
            "moon_sign": positions["Moon"]["sign"],
            "retrogrades": retrogrades,
            "positions": positions
        }

# --- 2. Trend Spotter ---
class TrendSpotter:
    @staticmethod
    def get_trend_signals():
        signals = {"trending_signs": [], "hot_topics": []}
        
        # 1. Google Trends RSS
        rss_url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:5]:
                signals["hot_topics"].append(entry.title)
        except Exception as e:
            print(f"Error fetching Google Trends: {e}")
            
        # 2. Reddit r/astrology top today
        reddit_url = "https://www.reddit.com/r/astrology/top.json?t=day&limit=15"
        try:
            headers = {"User-Agent": "AstrologyContentEngine/1.0"}
            resp = requests.get(reddit_url, headers=headers, timeout=10)
            if resp.ok:
                data = resp.json()
                for child in data.get("data", {}).get("children", []):
                    title = child["data"]["title"].lower()
                    for sign in ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"]:
                        if sign in title and sign not in signals["trending_signs"]:
                            signals["trending_signs"].append(sign)
        except Exception as e:
            print(f"Error fetching Reddit: {e}")
            
        return signals

# --- 3. Virality Scorer ---
class ViralityScorer:
    @staticmethod
    def score_context(cosmic_context, trend_signals):
        score = 5 # base
        primary_angle = "Regular transit"
        
        # Mercury Rx
        if "Mercury" in cosmic_context["retrogrades"]:
            score += 40
            primary_angle = "Mercury Retrograde"
            
        # Full / New Moon
        if cosmic_context["moon_phase"] in ["Full Moon", "New Moon"]:
            score += 25
            primary_angle = f"{cosmic_context['moon_phase']} in {cosmic_context['moon_sign']}"
            
        # Trending sign
        if trend_signals["trending_signs"]:
            score += 20
            primary_angle = f"Focus on {', '.join(trend_signals['trending_signs'])}"
            
        for topic in trend_signals["hot_topics"]:
            score += 5
            
        return {
            "score": min(score, 100),
            "angle": primary_angle
        }

# --- 4. Script Factory ---
class ScriptFactory:
    PROMPT_TEMPLATE = """
You are an autonomous viral astrology content engine. Your job is to 
produce one short-form video per day (60-90 seconds) that maximizes 
shares, comments, and saves on Instagram Reels and TikTok.

INPUTS YOU RECEIVE EACH RUN:
- cosmic_context: {cosmic_context}
- trend_signals: {trend_signals}
- virality_score: {virality_score}
- content_format: {content_format}

YOUR OUTPUT must be a JSON object with these exact keys:
{{
  "hook": "First 2 seconds of video — must be a bold claim or provocative question. Max 12 words.",
  "description": "1 sentence explaining the current astrological weather causing this (e.g. Moon in Scorpio is clashing with Mars)",
  "body": "The core narrative intro (approx 15-20 seconds). Rules: Speak directly to the viewer (you/your). Reference the actual planetary event. Include one controversial claim.",
  "groups": [
    {{
      "group_name": "Name of the group (e.g. Fire Signs, Mutable Signs, Scorpio Placements)",
      "signs_included": ["Array of specific signs in this group"],
      "message": "The script text for this group (Keep sentences under 12 words each). Structure: [Callout]. [Astrology Reason]. [Action]. Do NOT include labels like '[Callout]' in the text.",
      "visual_cue": "A punchy 3-5 word summary of the message to flash on screen"
    }}
  ],
  "CTA": "Last 5 seconds.",
  "caption": "Instagram caption — 3 sentences max. End with a question.",
  "hashtags": ["Array of 15 hashtags"],
  "audio_direction": {{
    "voice_tone": "one of [urgent, mystical, conspiratorial, warm, dramatic]",
    "bg_music_keywords": ["2-3 keywords to search for background track"],
    "pacing": "one of [fast, medium, slow]"
  }},
  "virality_hooks": {{
    "controversy_level": 1-10,
    "identity_trigger": "which specific sign or placement is the primary target",
    "share_mechanic": "why someone would share this"
  }}
}}

VIRALITY RULES (never break these):
1. Never be neutral. Every post takes a position.
2. Always name specific signs — generic astrology content dies.
3. The hook must create either curiosity, identity recognition, or mild fear.
4. If Mercury is retrograde, mention it regardless of the content format.
5. If moon is full or new, open with it.
6. Controversy level must be >= 6 for any post to achieve virality threshold.

OUTPUT ONLY the JSON. No preamble, no explanation.
"""
    @staticmethod
    def generate_script(cosmic_context, trend_signals, top_angle):
        api_key = vhp.get_groq_api_key()
        
        prompt = ScriptFactory.PROMPT_TEMPLATE.format(
            cosmic_context=json.dumps(cosmic_context),
            trend_signals=json.dumps(trend_signals),
            virality_score=json.dumps(top_angle),
            content_format="hot_take"
        )
        
        raw_output = vhp.call_groq(prompt, "You are a JSON-only API. Output valid JSON.", api_key)
        return vhp.parse_model_json(raw_output)

# --- 5. Audio Builder ---
class AudioBuilder:
    @staticmethod
    def build_audio(script_json, output_path):
        """
        Fetches or selects background music for the reel.
        1. Checks for a local 'music_library' folder.
        2. Tries Pixabay API.
        3. Falls back to yt-dlp.
        4. Last resort: silent track.
        """
        # 1. Local Library
        library_dir = Path("music_library")
        if library_dir.exists():
            tracks = list(library_dir.glob("*.mp3"))
            if tracks:
                chosen = random.choice(tracks)
                print(f"      -> Using local track from library: {chosen.name}")
                shutil.copy2(chosen, output_path)
                return output_path

        # Extract keywords
        audio_dir = script_json.get("audio_direction", {})
        if isinstance(audio_dir, dict):
            keywords = audio_dir.get("bg_music_keywords", ["ambient"])
        else:
            keywords = [k.strip() for k in re.split(r"[, ]+", str(audio_dir)) if len(k) > 2]

        if not keywords:
            keywords = ["astrology", "ambient"]

        query = "+".join(keywords[:3])

        # 2. Pixabay (attempting with User-Agent)
        pixabay_key = os.getenv("PIXABAY_API_KEY")
        if pixabay_key:
            url = f"https://pixabay.com/api/audio/?key={pixabay_key}&q={query}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.ok and resp.json().get("hits"):
                    track_url = resp.json()["hits"][0]["audio"]
                    print(f"      -> Downloading Pixabay track: {track_url}")
                    urllib.request.urlretrieve(track_url, str(output_path))
                    return output_path
                else:
                    print(f"      -> Pixabay fetch failed or empty (Status: {resp.status_code}).")
            except Exception as e:
                print(f"      -> Pixabay fetch exception: {e}")

        # 3. yt-dlp fallback
        print(f"      -> Falling back to yt-dlp for keywords: {' '.join(keywords)}")
        yt_query = f"ytsearch1:royalty free {' '.join(keywords[:3])} background music loop 60s"
        try:
            # Download and convert to mp3
            subprocess.run([
                "python", "-m", "yt_dlp",
                yt_query,
                "-x", "--audio-format", "mp3",
                "--max-downloads", "1",
                "-o", str(output_path.with_suffix('')) + ".%(ext)s"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Ensure it's exactly the output_path
            temp_mp3 = output_path.with_suffix(".mp3")
            if temp_mp3.exists() and temp_mp3 != output_path:
                if output_path.exists():
                    os.remove(output_path)
                os.rename(temp_mp3, output_path)

            return output_path
        except Exception as e:
            print(f"      -> yt-dlp failed: {e}")

        # 4. Silent Fallback
        print("      -> Using fallback silent track.")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", "60", "-q:a", "9", "-acodec", "libmp3lame", str(output_path)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"      -> ffmpeg fallback failed: {e}")
            output_path.touch()

        return output_path
# --- 6. Pipeline Integration ---
def run_pipeline(dry_run=False):
    print("=======================================")
    print(" AUTONOMOUS VIRAL CONTENT ENGINE")
    print("=======================================")
    
    print("[1/6] Scanning Cosmic Context...")
    cosmic_context = CosmicScanner.get_today_context()
    
    print("[2/6] Fetching Trend Signals...")
    trend_signals = TrendSpotter.get_trend_signals()
    
    print("[3/6] Scoring Virality...")
    top_angle = ViralityScorer.score_context(cosmic_context, trend_signals)
    print(f"      -> Top Angle: {top_angle['angle']} (Score: {top_angle['score']})")
    
    print("[4/6] Generating Script via Groq...")
    script_json = ScriptFactory.generate_script(cosmic_context, trend_signals, top_angle)
    
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("generated_reels") / f"auto_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    script_path = out_dir / "script.json"
    script_path.write_text(json.dumps(script_json, indent=2), encoding="utf-8")
    print(f"      -> Script saved to {script_path}")
    
    print("[5/6] Building Audio (Music Only)...")
    audio_path = out_dir / "bg_music.mp3"
    AudioBuilder.build_audio(script_json, audio_path)
    
    # Check if Remotion is ready to render
    print("[6/6] Rendering Reel via Remotion...")
    remotion_dir = Path("remotion_reel")
    if not remotion_dir.exists():
        print("      -> ERROR: remotion_reel directory not found. Skipping render.")
        return
        
    render_bundle_path = remotion_dir / "src" / "data" / "render-bundle.json"
    render_bundle_path.parent.mkdir(parents=True, exist_ok=True)
    
    public_dir = remotion_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(audio_path, public_dir / "bg_music.mp3")
    
    script_json["_internal_audio_path"] = "bg_music.mp3"
    render_bundle_path.write_text(json.dumps(script_json, indent=2), encoding="utf-8")
    
    output_video = out_dir / "reel.mp4"
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    try:
        subprocess.run([npm_cmd, "run", "render", "--", str(output_video.resolve())], cwd=remotion_dir, check=True)
        print(f"      -> Video rendered to {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"      -> Render failed: {e}")
        return

    if dry_run:
        print("\n[!] Dry run complete. Did not publish to Meta.")
        return
        
    print("[7/7] Publishing to Instagram...")
    try:
        publisher = vhp.MetaReelPublisher(
            access_token=vhp.get_meta_access_token(),
            ig_user_id=vhp.get_instagram_account_id(),
            graph_version=vhp.get_meta_graph_version()
        )
        
        caption = f"{script_json['caption']}\n\n{' '.join(script_json['hashtags'])}"
        post_id = publisher.post_reel(caption=caption, video_path=output_video)
        print(f"      -> Pipeline complete! IG Post ID: {post_id}")
    except Exception as e:
        print(f"      -> Publishing failed: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Astrology Content Engine")
    parser.add_argument("--dry-run", action="store_true", help="Generate and render without posting to Instagram")
    args = parser.parse_args()
    
    run_pipeline(dry_run=args.dry_run)
