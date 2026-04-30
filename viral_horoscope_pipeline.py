#!/usr/bin/env python3
"""
Standalone horoscope content + reel pipeline.

What it does:
1. Generates all 12 zodiac sign readings in one Groq call
2. Saves a structured JSON bundle optimized for Instagram carousel/reel copy
3. Writes caption + voiceover text assets
4. Optionally calls a local Remotion project to render a 9:16 reel
5. Posts the rendered reel to Instagram via Meta Graph API (URL-based upload)

Usage:
    python viral_horoscope_pipeline.py --generate
    python viral_horoscope_pipeline.py --generate --theme "soft launch energy"
    python viral_horoscope_pipeline.py --generate --render
    python viral_horoscope_pipeline.py --render --input generated_reels\\20260425_230500\\horoscope_bundle.json
    python viral_horoscope_pipeline.py --generate --render --post --video-url https://your-cdn.com/reel.mp4
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import requests

try:
    import prompt_generator
except ImportError:
    prompt_generator = None


ZODIAC_SIGNS = [
    {"name": "Aries",       "element": "Fire",  "symbol": "Ram",          "palette": ["#2A0F14", "#7A1C2B", "#FF7A59"]},
    {"name": "Taurus",      "element": "Earth", "symbol": "Bull",         "palette": ["#0E221B", "#23573A", "#E8C16B"]},
    {"name": "Gemini",      "element": "Air",   "symbol": "Twins",        "palette": ["#111827", "#224E88", "#7ED7F7"]},
    {"name": "Cancer",      "element": "Water", "symbol": "Crab",         "palette": ["#0F1A2E", "#284B8A", "#B9D8FF"]},
    {"name": "Leo",         "element": "Fire",  "symbol": "Lion",         "palette": ["#2A1405", "#8A430F", "#FFC145"]},
    {"name": "Virgo",       "element": "Earth", "symbol": "Maiden",       "palette": ["#152018", "#45634C", "#DCE8B4"]},
    {"name": "Libra",       "element": "Air",   "symbol": "Scales",       "palette": ["#1D1424", "#6E4A8C", "#F5B8E8"]},
    {"name": "Scorpio",     "element": "Water", "symbol": "Scorpion",     "palette": ["#120A19", "#4C1D5F", "#FF6AA2"]},
    {"name": "Sagittarius", "element": "Fire",  "symbol": "Archer",       "palette": ["#1C1222", "#6441A5", "#FFB86B"]},
    {"name": "Capricorn",   "element": "Earth", "symbol": "Sea Goat",     "palette": ["#141414", "#434343", "#E6D3A3"]},
    {"name": "Aquarius",    "element": "Air",   "symbol": "Water Bearer", "palette": ["#0A1A22", "#0F6E7A", "#95F3FF"]},
    {"name": "Pisces",      "element": "Water", "symbol": "Fish",         "palette": ["#140F24", "#3D2C78", "#9BC8FF"]},
]

SIGN_INDEX = {sign["name"]: sign for sign in ZODIAC_SIGNS}
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_META_GRAPH_VERSION = "v19.0"  # pinned to a stable, supported version

REEL_PRESETS: dict[str, dict[str, Any]] = {
    "fixed_self_respect": {
        "label": "Fixed signs: self-respect test",
        "headline": "Fixed signs, this week is testing your self-respect",
        "target_signs": ["Taurus", "Leo", "Scorpio", "Aquarius"],
        "angle": (
            "Fixed signs are being tempted to over-prove loyalty, chase closure, "
            "or bend a boundary just to keep emotional control."
        ),
        "cover_text": "FIXED SIGNS: DON'T BEND",
        "hook": "Fixed signs, this week tests your self-respect.",
        "cta": "Save this if your sign got read, and send it to the fixed sign who keeps acting unbothered.",
    },
    "fire_do_not_chase": {
        "label": "Fire signs: do not chase",
        "headline": "Aries, Leo, Sagittarius: do not chase this person",
        "target_signs": ["Aries", "Leo", "Sagittarius"],
        "angle": (
            "Fire signs are confusing intensity with proof. The reel should feel like "
            "a stylish warning against chasing someone who only responds to distance."
        ),
        "cover_text": "FIRE SIGNS: DON'T CHASE",
        "hook": "Aries, Leo, Sagittarius: do not chase this person.",
        "cta": "Comment your fire sign and send this before someone texts first.",
    },
    "moved_on_but_didnt": {
        "label": "Moved on, but did not",
        "headline": "The signs pretending they moved on but didn't",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Choose the four signs most likely to act detached while still checking, "
            "comparing, remembering, or waiting for emotional confirmation."
        ),
        "cover_text": "THEY DIDN'T MOVE ON",
        "hook": "These signs are pretending they moved on.",
        "cta": "If your sign is here, comment nothing. That will say enough.",
    },
    "moon_scorpio_exposure": {
        "label": "Moon in Scorpio: exposed",
        "headline": "Moon in Scorpio: 4 signs about to get exposed emotionally",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Use Moon in Scorpio as the transit frame. Pick four signs whose hidden "
            "feelings, jealousy, loyalty tests, or private attachments are coming to the surface."
        ),
        "cover_text": "MOON IN SCORPIO EXPOSES",
        "hook": "Moon in Scorpio is exposing these four signs.",
        "cta": "Save this before the feeling gets louder, and send it to the sign that got exposed.",
    },
    "daily_transit": {
        "label": "Daily transit: emotional weather",
        "headline": "Today's astrology is making these signs act different",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Use today's astrology as the trigger. Connect one current-feeling transit, Moon mood, "
            "or planetary tension to a real-life emotional situation people recognize immediately."
        ),
        "cover_text": "TODAY'S ASTROLOGY SHIFT",
        "hook": "Today's astrology is hitting these signs first.",
        "cta": "Save this for later today and send it to the sign acting different.",
    },
    "love_attachment": {
        "label": "Love: attachment pattern",
        "headline": "These signs act detached when they care too much",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Make this about dating, silence, attachment, delayed replies, mixed signals, "
            "and the difference between emotional control and emotional honesty."
        ),
        "cover_text": "THEY CARE TOO MUCH",
        "hook": "These signs act detached when they care too much.",
        "cta": "Send this to the sign who says they are fine too quickly.",
    },
    "shadow_callout": {
        "label": "Shadow work: called out",
        "headline": "The lie each of these signs tells themselves",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Give each sign a sharp but compassionate shadow-work callout: the story they tell "
            "themselves to avoid vulnerability, accountability, grief, or desire."
        ),
        "cover_text": "YOUR SIGN'S LITTLE LIE",
        "hook": "These signs are lying to themselves a little.",
        "cta": "Comment your sign if it felt rude but accurate.",
    },
    "compatibility_drama": {
        "label": "Compatibility: chemistry trap",
        "headline": "Zodiac pairs that mistake chemistry for compatibility",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Frame each card as a sign or sign-pair dynamic where chemistry, ego, timing, "
            "or unfinished business gets confused with actual compatibility."
        ),
        "cover_text": "CHEMISTRY IS NOT COMPATIBILITY",
        "hook": "These signs keep confusing chemistry with compatibility.",
        "cta": "Send this to the person who calls chaos a connection.",
    },
    "money_power": {
        "label": "Money: reputation era",
        "headline": "These signs are entering their reputation era",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Make this about career, money, visibility, undercharging, discipline, envy, "
            "and the moment a sign stops hiding its ambition."
        ),
        "cover_text": "REPUTATION ERA STARTS",
        "hook": "These signs are done being humble about their talent.",
        "cta": "Save this if your sign is done playing small.",
    },
    "weekend_tension": {
        "label": "Weekend: social tension",
        "headline": "This weekend exposes who actually cares",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Make this feel timely for the next 48 hours: plans, parties, texts, delayed replies, "
            "social comparison, ex energy, and who makes effort when nobody asks twice."
        ),
        "cover_text": "THIS WEEKEND EXPOSES IT",
        "hook": "This weekend exposes who actually cares.",
        "cta": "Send this before the weekend starts acting obvious.",
    },
    "moon_sign_mood": {
        "label": "Moon signs: private mood",
        "headline": "Moon signs that are feeling everything privately",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Write for Moon signs, not Sun signs. Focus on private reactions, emotional safety, "
            "comfort habits, attachment needs, and what they will not say out loud."
        ),
        "cover_text": "YOUR MOON SIGN KNOWS",
        "hook": "These Moon signs are feeling everything privately.",
        "cta": "Send this to someone who knows their Moon sign too well.",
    },
    "placement_based": {
        "label": "Placements: birth chart detail",
        "headline": "If you have these placements, this message is yours",
        "target_signs": None,
        "target_count": 4,
        "angle": (
            "Use placement language: Venus, Mars, Moon, Rising, or Saturn placements. "
            "Each card should feel more specific than a Sun-sign horoscope."
        ),
        "cover_text": "CHECK YOUR PLACEMENTS",
        "hook": "If you have these placements, this is yours.",
        "cta": "Save this and check your chart before denying it.",
    },
}

DAILY_STYLE_ROTATION = [
    "daily_transit",
    "love_attachment",
    "shadow_callout",
    "compatibility_drama",
    "money_power",
    "weekend_tension",
    "moon_sign_mood",
    "placement_based",
]

REEL_STYLE_CHOICES = ["all_signs", "daily", "random_daily", "random_viral", "generator", *REEL_PRESETS.keys()]


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _get_env(keys: list[str], local_env: dict[str, str]) -> str:
    for key in keys:
        val = os.getenv(key) or local_env.get(key, "")
        if val:
            return val
    return ""


def get_groq_api_key() -> str:
    local_env = load_dotenv(Path(".env"))
    return _get_env(["GROQ_API_KEY", "groq_api"], local_env)


def get_meta_access_token() -> str:
    local_env = load_dotenv(Path(".env"))
    return _get_env(["META_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN"], local_env)


def get_instagram_account_id() -> str:
    local_env = load_dotenv(Path(".env"))
    return _get_env(["INSTAGRAM_USER_ID", "INSTAGRAM_ACCOUNT_ID", "IG_USER_ID"], local_env)


def get_meta_graph_version() -> str:
    local_env = load_dotenv(Path(".env"))
    return _get_env(["META_GRAPH_API_VERSION"], local_env) or DEFAULT_META_GRAPH_VERSION


def get_npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------

def call_groq(prompt: str, system_prompt: str, api_key: str, model: str = DEFAULT_MODEL) -> str:
    if not api_key:
        raise RuntimeError("Missing Groq API key. Set GROQ_API_KEY or groq_api in .env.")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.95,
            "max_tokens": 3500,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ],
        },
        timeout=90,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# JSON parsing / repair
# ---------------------------------------------------------------------------

def extract_json_payload(raw: str) -> str:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text.strip()


def repair_json_string(text: str) -> str:
    """Fix common LLM JSON issues: literal newlines/tabs inside strings, invalid escapes."""
    result: list[str] = []
    in_string = False
    i = 0
    VALID_ESCAPES = set('"\\/bfnrtu')

    while i < len(text):
        char = text[i]
        if not in_string:
            result.append(char)
            if char == '"':
                in_string = True
            i += 1
            continue

        if char == '\\':
            if i + 1 < len(text):
                next_char = text[i + 1]
                if next_char in VALID_ESCAPES:
                    result.append(char)
                    result.append(next_char)
                    i += 2
                else:
                    result.append('\\\\')
                    i += 1
            else:
                result.append('\\\\')
                i += 1
            continue

        if char == '"':
            result.append(char)
            in_string = False
            i += 1
            continue

        if   char == '\n': result.append('\\n')
        elif char == '\r': result.append('\\r')
        elif char == '\t': result.append('\\t')
        else:              result.append(char)
        i += 1

    return ''.join(result)


def parse_model_json(raw: str) -> dict:
    payload = extract_json_payload(raw)
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass
    try:
        repaired = repair_json_string(payload)
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        char_pos = e.pos
        snippet = payload[max(0, char_pos - 60) : char_pos + 60]
        raise RuntimeError(
            f"JSON repair failed at position {char_pos}.\n"
            f"Context: ...{snippet!r}...\n"
            f"Original error: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Prompt / system
# ---------------------------------------------------------------------------

def resolve_reel_style(style: str | None) -> str:
    requested = (style or "all_signs").strip().lower()
    aliases = {
        "all": "all_signs",
        "all-signs": "all_signs",
        "fixed": "fixed_self_respect",
        "fire": "fire_do_not_chase",
        "love": "love_attachment",
        "shadow": "shadow_callout",
        "money": "money_power",
        "career": "money_power",
        "weekend": "weekend_tension",
        "moon": "moon_sign_mood",
        "placements": "placement_based",
        "transit": "daily_transit",
        "moved_on": "moved_on_but_didnt",
        "moved-on": "moved_on_but_didnt",
        "moon_scorpio": "moon_scorpio_exposure",
        "scorpio_moon": "moon_scorpio_exposure",
    }
    requested = aliases.get(requested, requested)
    if requested == "daily":
        return DAILY_STYLE_ROTATION[dt.date.today().toordinal() % len(DAILY_STYLE_ROTATION)]
    if requested == "random_daily":
        return random.choice(DAILY_STYLE_ROTATION)
    if requested == "random_viral":
        return random.choice(list(REEL_PRESETS.keys()))
    if requested not in REEL_STYLE_CHOICES:
        raise ValueError(
            f"Unknown reel style {style!r}. Choose one of: {', '.join(REEL_STYLE_CHOICES)}"
        )
    return requested


def build_targeted_prompt(style_key: str, theme: str | None = None) -> str:
    today = dt.datetime.now().strftime("%B %d, %Y")
    preset = REEL_PRESETS[style_key]
    theme_line = theme or preset["angle"]
    target_signs = preset.get("target_signs")
    if target_signs:
        target_rule = (
            f"Use these target signs exactly, in this order: {', '.join(target_signs)}."
        )
        count_rule = f"Include exactly {len(target_signs)} signs."
    else:
        count = int(preset.get("target_count", 4))
        target_rule = (
            f"Choose exactly {count} zodiac signs that best fit the angle. "
            "Do not include all 12 signs."
        )
        count_rule = f"Include exactly {count} signs, each once."

    return f"""
Today is {today}.
Create one focused, high-retention Instagram Reel script in this exact viral style:
{preset["headline"]}

Core angle:
{theme_line}

Targeting:
- {target_rule}
- The first 2 seconds must make the viewer feel either named, exposed, warned, or curious.
- This is not a daily all-sign horoscope. It is a sharp identity reel for a smaller group.

Creative goal:
- Make the viewer think "I need to send this to them."
- Every sign should have a specific emotional receipt, not generic advice.
- Use mild tension, romantic/social psychology, ego, boundaries, attachment, and self-respect.
- Add astrology substance: name the transit, placement, modality, element, ruling planet, or Moon mood that explains why this sign is being activated.
- Each sign card should contain one astrology reason and one recognizable real-life behavior.
- Sound like a perceptive friend with taste, not a therapist, preacher, or fortune cookie.
- Avoid generic phrases like "major shift", "stay grounded", "new chapter", "trust the universe", "take bold action".
- Avoid diagnosing people or making absolute harmful claims.

Return valid JSON only with this exact shape:
{{
  "meta": {{
    "title": "short series title, 3-6 words",
    "hook": "{preset["hook"]}",
    "theme": "1 sentence theme summary",
    "description": "1 sentence explaining the current astrological weather causing this (e.g. Moon in Scorpio is clashing with Mars)",
    "caption_hook": "opening caption line, highly scroll-stopping",
    "caption_body": "70-140 word caption for Instagram, intimate and shareable",
    "cta": "{preset["cta"]}",
    "audio_direction": "brief direction for the reel mood",
    "cover_text": "{preset["cover_text"]}"
  }},
  "signs": [
    {{
      "sign": "Aries",
      "theme": "3-6 words",
      "private_truth": "1 emotionally sharp sentence",
      "tension": "1 sentence naming the internal conflict",
      "shift": "1 sentence telling them what changes now",
      "screenshot_line": "1 punchy line built to be screenshotted",
      "share_line": "1 line they would send to a friend",
      "reel_lines": ["line 1", "line 2", "line 3"],
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}

Rules:
- {count_rule}
- Keep each reel_lines item under 11 words.
- Line 1 must be a direct callout (The Vibe). Do NOT include the label 'The Vibe:' in the text.
- Line 2 must name the astrology trigger plus the behavior (The Reason). Do NOT include the label 'The Reason:' in the text.
- Line 3 must give the warning, reveal, or boundary (The Action). Do NOT include the label 'The Action:' in the text.
- Give each sign a different reason; no repeated templates.
- Escape any line breaks inside JSON strings as \n.
"""


def build_prompt(theme: str | None = None, style: str | None = "all_signs") -> str:
    style_key = resolve_reel_style(style)
    if style_key != "all_signs":
        return build_targeted_prompt(style_key, theme)

    today      = dt.datetime.now().strftime("%B %d, %Y")
    sign_list  = ", ".join(sign["name"] for sign in ZODIAC_SIGNS)
    theme_line = theme or "magnetic self-respect, private emotions, and screenshot-worthy realizations"
    return f"""
Today is {today}.
Create one highly shareable Instagram horoscope package for all 12 zodiac signs in a single response.

Creative goal:
- This should feel personal enough to screenshot, save, and DM to a friend.
- Blend astrology with psychology, attachment patterns, inner narratives, desire, ego, boundaries, self-worth, and emotional timing.
- Every sign should feel called out in a specific, intimate way.
- Avoid generic spiritual fluff.
- Avoid melodrama, fatalism, or diagnosing people.
- Avoid repetitive words like toxic, addicted, broken, destroyed, or killing you.
- Keep it emotionally intelligent, modern, and socially sharp.
- Write with tension, clarity, and emotional precision.
- Tone: intimate, observant, a little dangerous, deeply relatable.
- Theme focus: {theme_line}

Audience goal:
- Make people say "why is this literally me?"
- Make each sign feel seen in a private way.
- Keep language sharp and social-media ready.

Target signs:
{sign_list}

Return valid JSON only with this exact shape:
{{
  "meta": {{
    "title": "short series title, 3-6 words",
    "hook": "one striking hook line for the reel cover",
    "theme": "1 sentence theme summary",
    "description": "1 sentence explaining the current astrological weather causing this (e.g. Venus in Pisces is increasing emotional sensitivity)",
    "caption_hook": "opening caption line, highly scroll-stopping",
    "caption_body": "120-220 word caption for Instagram, personal and magnetic",
    "cta": "one sentence CTA to save/share/comment",
    "audio_direction": "brief direction for the reel mood",
    "cover_text": "big text for the opening frame, max 8 words"
  }},
  "signs": [
    {{
      "sign": "Aries",
      "theme": "4-8 words",
      "private_truth": "1 emotionally sharp sentence",
      "tension": "1 sentence naming the internal conflict",
      "shift": "1 sentence telling them what changes now",
      "screenshot_line": "1 punchy line built to be screenshotted",
      "share_line": "1 line they would send to a friend",
      "reel_lines": ["line 1", "line 2", "line 3"],
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}

Rules:
- Include all 12 signs exactly once.
- Each sign must feel distinct.
- Keep "screenshot_line" and "share_line" very strong.
- Vary the emotional angle across signs: romance, self-respect, boundaries, ambition, friendship, avoidance, confidence, grief, longing, softness.
- Do not turn every sign into a trauma monologue.
- Make it feel like a perceptive friend, not a therapist or preacher.
- Escape any line breaks inside JSON strings as \\n.
"""


SYSTEM_PROMPT = """
You are an elite astrology + psychology copywriter for viral Instagram content.

You write like someone who understands:
- emotional protection patterns
- romantic tension
- self-sabotage
- identity, ego, longing, avoidance, attachment
- the exact language people screenshot because it feels too true

Your output must be:
- direct
- intimate
- socially sticky
- emotionally precise
- modern and human
- non-repetitive across signs
- valid JSON only
"""


# ---------------------------------------------------------------------------
# Bundle normalisation
# ---------------------------------------------------------------------------

def ensure_three_lines(sign: dict[str, Any]) -> list[str]:
    raw_lines = sign.get("reel_lines", [])
    lines = [str(l).strip() for l in raw_lines if str(l).strip()] if isinstance(raw_lines, list) else []
    fallbacks = [
        sign.get("theme",          "A shift is happening."),
        sign.get("private_truth",  "You can feel it already."),
        sign.get("screenshot_line","This one is yours."),
    ]
    for fb in fallbacks:
        if len(lines) >= 3:
            break
        text = str(fb).strip()
        if text:
            lines.append(text)
    while len(lines) < 3:
        lines.append("This sign is moving differently now.")
    return lines[:3]


def normalize_sign(generated: dict[str, Any], sign: dict[str, Any]) -> dict[str, Any]:
    reel_lines = generated.get(
        "reel_lines",
        [
            generated.get("theme",          "A shift is happening."),
            generated.get("private_truth",  "You can feel it already."),
            generated.get("screenshot_line","This one is yours."),
        ],
    )
    return {
        "sign":    sign["name"],
        "element": sign["element"],
        "symbol":  sign["symbol"],
        "palette": sign["palette"],
        "theme":   generated.get("theme",          f"{sign['name']} is entering a sharper chapter"),
        "private_truth": generated.get("private_truth",  f"{sign['name']} is done pretending they do not care."),
        "tension": generated.get("tension",        "You want clarity, but part of you still performs distance to stay safe."),
        "shift":   generated.get("shift",          "The right move is not louder effort. It is cleaner self-respect."),
        "screenshot_line": generated.get("screenshot_line", "You are not hard to love. You are hard to manipulate now."),
        "share_line":      generated.get("share_line",      "Send this to the version of you that keeps shrinking to feel chosen."),
        "reel_lines": ensure_three_lines({
            "reel_lines":     reel_lines,
            "theme":          generated.get("theme",          "A shift is happening."),
            "private_truth":  generated.get("private_truth",  "You can feel it already."),
            "screenshot_line":generated.get("screenshot_line","This one is yours."),
        }),
        "keywords": generated.get("keywords", [sign["element"], "emotion", "timing"])[:3],
    }


def normalize_bundle(bundle: dict[str, Any], theme: str | None, style: str | None = "all_signs") -> dict[str, Any]:
    style_key = resolve_reel_style(style)
    meta  = bundle.get("meta",  {})
    signs = bundle.get("signs", [])

    sign_lookup: dict[str, dict] = {
        item.get("sign", ""): item
        for item in signs
        if isinstance(item, dict)
    }

    normalized_signs = []
    if style_key == "all_signs":
        target_signs = [sign["name"] for sign in ZODIAC_SIGNS]
    elif style_key == "generator":
        target_signs = [
            str(item.get("sign", "")).strip()
            for item in signs
            if isinstance(item, dict) and str(item.get("sign", "")).strip() in SIGN_INDEX
        ]
    else:
        preset = REEL_PRESETS[style_key]
        target_signs = preset.get("target_signs") or [
            str(item.get("sign", "")).strip()
            for item in signs
            if isinstance(item, dict) and str(item.get("sign", "")).strip() in SIGN_INDEX
        ]
        target_count = int(preset.get("target_count") or len(target_signs))
        target_signs = target_signs[:target_count]

    for sign_name in target_signs:
        sign = SIGN_INDEX.get(sign_name)
        if not sign:
            continue
        normalized_signs.append(normalize_sign(sign_lookup.get(sign_name, {}), sign))

    if not normalized_signs:
        for sign in ZODIAC_SIGNS[:4]:
            normalized_signs.append(normalize_sign({}, sign))

    preset_meta = REEL_PRESETS.get(style_key, {})

    return {
        "generated_at":  dt.datetime.now().isoformat(timespec="seconds"),
        "theme_request": theme or "",
        "reel_style": style_key,
        "targeting": {
            "label": preset_meta.get("label", "All signs"),
            "headline": preset_meta.get("headline", "All signs horoscope"),
            "target_signs": [sign["sign"] for sign in normalized_signs],
        },
        "meta": {
            "title":         meta.get("title",         "The Horoscope They Feel"),
            "hook":          meta.get("hook",           preset_meta.get("hook", "These are not soft horoscopes.")),
            "theme":         meta.get("theme",          theme or preset_meta.get("angle", "psychology wrapped in cosmic timing")),
            "description":   meta.get("description",    "Current planetary alignments are triggering deep emotional shifts."),
            "caption_hook":  meta.get("caption_hook",  "This one is going to feel a little too personal."),
            "caption_body":  meta.get("caption_body",  (
                "Your sign is not just a mood today. It is a mirror. Some signs are protecting too much. "
                "Some are craving honesty. Some are finally too tired to keep performing for breadcrumbs."
            )),
            "cta":            meta.get("cta",            preset_meta.get("cta", "Save this, send it to your sign twin, and comment the line that dragged you.")),
            "audio_direction":meta.get("audio_direction","moody, cinematic, intimate, slow-burn"),
            "cover_text":     meta.get("cover_text",     preset_meta.get("cover_text", "THE HOROSCOPE THAT READS YOU")),
        },
        "signs": normalized_signs,
    }


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def build_caption(bundle: dict[str, Any]) -> str:
    return (
        f"{bundle['meta']['caption_hook']}\n\n"
        f"{bundle['meta']['caption_body']}\n\n"
        f"{bundle['meta']['cta']}\n"
    )


def build_voiceover_script(bundle: dict[str, Any]) -> str:
    lines = [bundle["meta"]["hook"], ""]
    for sign in bundle["signs"]:
        reel_lines = ensure_three_lines(sign)
        lines.append(f"{sign['sign']}: {reel_lines[0]}")
        lines.append(reel_lines[1])
        lines.append(reel_lines[2])
        lines.append("")
    lines.append(bundle["meta"]["cta"])
    return "\n".join(lines).strip() + "\n"


def write_bundle_files(bundle: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path    = output_dir / "horoscope_bundle.json"
    caption_path   = output_dir / "instagram_caption.txt"
    voiceover_path = output_dir / "voiceover_script.txt"

    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    caption_path.write_text(build_caption(bundle), encoding="utf-8")
    voiceover_path.write_text(build_voiceover_script(bundle), encoding="utf-8")
    return bundle_path


# ---------------------------------------------------------------------------
# Meta Graph API  —  FIXED
#
# Root causes of the original 400 Bad Request:
#
#  1. The original code mixed TWO different upload protocols:
#     - It created a container with `upload_type=resumable` (which returns a
#       one-time upload URI) …
#     - … but then posted binary data to that URI using the WRONG headers
#       (Authorization: OAuth instead of Authorization: Bearer, and
#       Content-Type: video/mp4 instead of application/octet-stream).
#     Meta requires `Authorization: OAuth <token>` only for the resumable
#     binary chunk endpoint, so the mismatch caused an immediate 400.
#
#  2. The standard / simpler Reels flow does NOT need a binary upload at all.
#     You supply a publicly accessible `video_url` and Meta fetches it
#     server-side. This is the approach used below.
#
#  3. `share_to_feed` should be a boolean True, not the string "true".
#
#  4. The graph version was pinned to v24.0 which may not exist yet; v22.0
#     is used instead (latest stable at time of writing).
# ---------------------------------------------------------------------------

class MetaReelPublisher:
    """
    Posts an Instagram Reel using the standard URL-based Media Container flow.

    Prerequisites
    -------------
    - `access_token` : a valid long-lived User or Page access token with
      `instagram_basic`, `instagram_content_publish`, and
      `pages_read_engagement` permissions.
    - `ig_user_id`   : the numeric Instagram Business / Creator account ID.
    - The video file must be hosted at a publicly accessible HTTPS URL
      (e.g. an S3 pre-signed URL, Cloudflare R2, etc.) before calling
      `post_reel`.  Meta fetches it server-side; no binary upload is needed.

    Flow
    ----
    1. POST /{ig_user_id}/media  →  returns container `id`
    2. Poll  GET /{container_id}?fields=status_code  until FINISHED
    3. POST /{ig_user_id}/media_publish  →  returns published post `id`
    """

    # Minimum video spec for Reels (Meta requirements as of 2024-Q4)
    # - Format : MP4 / MOV
    # - Codec  : H.264 (video), AAC (audio)
    # - Aspect : 9:16
    # - Length : 3 – 90 seconds
    # - Size   : ≤ 1 GB

    def __init__(
        self,
        access_token: str,
        ig_user_id: str,
        graph_version: str | None = None,
    ) -> None:
        if not access_token:
            raise RuntimeError("Missing META_ACCESS_TOKEN / INSTAGRAM_ACCESS_TOKEN.")
        if not ig_user_id:
            raise RuntimeError("Missing INSTAGRAM_USER_ID / INSTAGRAM_ACCOUNT_ID / IG_USER_ID.")
        self.access_token  = access_token
        self.ig_user_id    = ig_user_id
        self.graph_version = graph_version or get_meta_graph_version()
        self.base_url      = f"https://graph.facebook.com/{self.graph_version}"

    # ------------------------------------------------------------------
    # Step 1 – create media container
    # ------------------------------------------------------------------
    def _create_reel_container(self, video_url: str, caption: str) -> str:
        """
        Creates an unpublished Reel container.

        Parameters
        ----------
        video_url : str
            Publicly accessible HTTPS URL pointing to the MP4/MOV file.
        caption : str
            Full Instagram caption (hashtags included).

        Returns
        -------
        str  –  The container `id` to poll and then publish.
        """
        payload = {
            "media_type":    "REELS",
            "video_url":     video_url,   # Meta fetches this server-side
            "caption":       caption,
            "share_to_feed": "true",        # boolean, not string
            "access_token":  self.access_token,
            "thumb_offset_ms": 3000,
        }

        response = requests.post(
            f"{self.base_url}/{self.ig_user_id}/media",
            data=payload,
            timeout=60,
        )

        # Surface the error body before raise_for_status so it is visible
        if not response.ok:
            try:
                err = response.json()
            except Exception:
                err = response.text
            raise RuntimeError(
                f"[Meta] Container creation failed {response.status_code}: {err}"
            )

        data = response.json()
        container_id = data.get("id")
        if not container_id:
            raise RuntimeError(f"[Meta] Unexpected container response: {data}")

        print(f"[Meta] Container created: {container_id}")
        return container_id

    def _create_resumable_container(self, caption: str) -> tuple[str, str]:
        """
        Creates an unpublished Reel container for local file upload.

        Returns
        -------
        tuple[str, str]  –  (container_id, upload_uri)
        """
        payload = {
            "media_type":    "REELS",
            "upload_type":   "resumable",
            "caption":       caption,
            "share_to_feed": "true",
            "access_token":  self.access_token,
        }

        response = requests.post(
            f"{self.base_url}/{self.ig_user_id}/media",
            data=payload,
            timeout=60,
        )

        if not response.ok:
            try:
                err = response.json()
            except Exception:
                err = response.text
            raise RuntimeError(
                f"[Meta] Resumable container creation failed {response.status_code}: {err}"
            )

        data = response.json()
        container_id = data.get("id")
        upload_uri   = data.get("uri")
        if not container_id or not upload_uri:
            raise RuntimeError(f"[Meta] Unexpected resumable container response: {data}")

        print(f"[Meta] Resumable container created: {container_id}")
        return container_id, upload_uri

    def _upload_video_data(self, upload_uri: str, video_path: str | Path) -> None:
        """
        Uploads the binary video data to the resumable upload URI.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        file_size = video_path.stat().st_size
        
        headers = {
            "Authorization": f"OAuth {self.access_token}",
            "offset": "0",
            "X-Entity-Length": str(file_size),
            "X-Entity-Name": video_path.name,
            "X-Entity-Type": "video/mp4",
            "file_size": str(file_size),
        }
        
        print(f"[Meta] Uploading {file_size} bytes from {video_path}...")
        with open(video_path, "rb") as f:
            video_data = f.read()

        response = requests.post(
            upload_uri,
            headers=headers,
            data=video_data,
            timeout=300, # Large timeout for video upload
        )
            
        if not response.ok:
            try:
                err = response.json()
            except Exception:
                err = response.text
            raise RuntimeError(
                f"[Meta] Video binary upload failed {response.status_code}: {err}"
            )
            
        print("[Meta] Video data uploaded successfully.")

    # ------------------------------------------------------------------
    # Step 2 – poll until processing finishes
    # ------------------------------------------------------------------
    def _wait_until_ready(
        self,
        container_id: str,
        timeout_seconds: int = 900,
        poll_seconds: int = 15,
    ) -> None:
        """
        Polls the container status until Meta reports FINISHED.

        Possible status_code values: IN_PROGRESS, FINISHED, ERROR, EXPIRED.
        """
        deadline     = time.time() + timeout_seconds
        last_payload: dict[str, Any] | None = None

        while time.time() < deadline:
            response = requests.get(
                f"{self.base_url}/{container_id}",
                params={
                    "fields":       "status_code,status",
                    "access_token": self.access_token,
                },
                timeout=60,
            )
            response.raise_for_status()
            last_payload = response.json()
            status_code  = str(last_payload.get("status_code", "")).upper()
            status       = str(last_payload.get("status",      "")).upper()

            print(f"[Meta] Container {container_id} status: {status_code}")

            if status_code == "FINISHED":
                return
            if status_code in {"ERROR", "EXPIRED"} or status in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"[Meta] Processing failed: {last_payload}")

            time.sleep(poll_seconds)

        raise TimeoutError(
            f"[Meta] Timed out waiting for container to finish: {last_payload}"
        )

    # ------------------------------------------------------------------
    # Step 3 – publish
    # ------------------------------------------------------------------
    def _publish_container(self, container_id: str) -> str:
        """
        Publishes a FINISHED container and returns the live post ID.
        """
        response = requests.post(
            f"{self.base_url}/{self.ig_user_id}/media_publish",
            data={
                "creation_id":  container_id,
                "access_token": self.access_token,
            },
            timeout=60,
        )

        if not response.ok:
            try:
                err = response.json()
            except Exception:
                err = response.text
            raise RuntimeError(
                f"[Meta] Publish failed {response.status_code}: {err}"
            )

        data    = response.json()
        post_id = data.get("id")
        if not post_id:
            raise RuntimeError(f"[Meta] Unexpected publish response: {data}")

        return str(post_id)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def post_reel(self, caption: str, video_url: str | None = None, video_path: str | Path | None = None) -> str:
        """
        Full three-step Reels publishing flow. Supports both URL and local file uploads.

        Parameters
        ----------
        caption    : str
            Instagram caption text.
        video_url  : str | None
            Publicly accessible HTTPS URL to the rendered MP4 file.
        video_path : str | Path | None
            Local path to the rendered MP4 file.

        Returns
        -------
        str  –  The published Instagram post ID.
        """
        if video_url:
            container_id = self._create_reel_container(video_url, caption)
        elif video_path:
            container_id, upload_uri = self._create_resumable_container(caption)
            self._upload_video_data(upload_uri, video_path)
        else:
            raise ValueError("Either video_url or video_path must be provided.")
            
        self._wait_until_ready(container_id)
        post_id = self._publish_container(container_id)
        print(f"[Meta] Published! Post ID: {post_id}")
        return post_id


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def generate_content(
    theme: str | None, 
    output_root: Path, 
    style: str | None = "all_signs",
    gen_config: dict | None = None
) -> Path:
    style_key = resolve_reel_style(style)
    api_key    = get_groq_api_key()
    
    if style_key == "generator" and prompt_generator:
        cfg = prompt_generator.PromptConfig(
            format=gen_config.get("format", "4-sign"),
            theme=gen_config.get("theme", "attachment"),
            tone=gen_config.get("tone", "perceptive-friend"),
            transit=gen_config.get("transit", "mercury-rx"),
            target_signs=gen_config.get("target_signs")
        )
        prompt = prompt_generator.generate_prompt(cfg)
    else:
        prompt = build_prompt(theme, style_key)
        
    raw        = call_groq(prompt, SYSTEM_PROMPT, api_key)
    parsed     = parse_model_json(raw)
    bundle     = normalize_bundle(parsed, theme, style_key)
    timestamp  = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / timestamp
    return write_bundle_files(bundle, output_dir)


class AudioBuilder:
    @staticmethod
    def build_audio(bundle: dict[str, Any], output_path: Path) -> Path:
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
                print(f"[Audio] Using local track from library: {chosen.name}")
                shutil.copy2(chosen, output_path)
                return output_path

        # Extract keywords
        audio_dir = bundle.get("meta", {}).get("audio_direction", "moody, cinematic")
        if isinstance(audio_dir, dict):
            keywords = audio_dir.get("bg_music_keywords", ["ambient"])
        else:
            # Split by comma or space and filter out common words
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
                    print(f"[Audio] Downloading Pixabay track: {track_url}")
                    urllib.request.urlretrieve(track_url, str(output_path))
                    return output_path
                else:
                    print(f"[Audio] Pixabay fetch failed or empty (Status: {resp.status_code}).")
            except Exception as e:
                print(f"[Audio] Pixabay fetch exception: {e}")

        # 3. yt-dlp fallback
        print(f"[Audio] Falling back to yt-dlp for keywords: {' '.join(keywords)}")
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
            
            # Ensure it's exactly the output_path (yt-dlp might append .mp3 to a name without it)
            temp_mp3 = output_path.with_suffix(".mp3")
            if temp_mp3.exists() and temp_mp3 != output_path:
                if output_path.exists():
                    os.remove(output_path)
                os.rename(temp_mp3, output_path)
                
            return output_path
        except Exception as e:
            print(f"[Audio] yt-dlp failed: {e}")

        # 4. Silent Fallback
        print("[Audio] Using fallback silent track.")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", "60", "-q:a", "9", "-acodec", "libmp3lame", str(output_path)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Audio] ffmpeg fallback failed: {e}")
            # Create a zero-byte file so the pipeline doesn't crash
            output_path.touch()

        return output_path


def render_reel(bundle_path: Path, output_file: Path | None = None) -> Path:
    remotion_dir = Path("remotion_reel")
    if not remotion_dir.exists():
        raise RuntimeError("Missing remotion_reel directory.")
    if not (remotion_dir / "node_modules").exists():
        raise RuntimeError(
            "Remotion dependencies not installed. Run: npm install --prefix ./remotion_reel"
        )

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if output_file is None:
        output_file = bundle_path.parent / "horoscope_reel.mp4"
    output_file = output_file.resolve()

    # Build Audio
    audio_path = bundle_path.parent / "bg_music.mp3"
    AudioBuilder.build_audio(bundle, audio_path)

    # Prepare Remotion
    render_bundle_path = remotion_dir / "src" / "data" / "render-bundle.json"
    render_bundle_path.parent.mkdir(parents=True, exist_ok=True)
    
    public_dir = remotion_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    
    if audio_path.exists():
        shutil.copy2(audio_path, public_dir / "bg_music.mp3")
        bundle["_internal_audio_path"] = "bg_music.mp3"

    render_bundle_path.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    subprocess.run(
        [get_npm_command(), "run", "render", "--", str(output_file)],
        cwd=remotion_dir,
        check=True,
    )
    return output_file


def post_reel(bundle_path: Path, video_url: str | None = None, video_path: Path | None = None) -> str:
    """
    Post a reel to Instagram.

    Parameters
    ----------
    bundle_path : Path
        Path to the horoscope_bundle.json (for the caption).
    video_url : str | None
        Publicly accessible HTTPS URL of the rendered MP4.
    video_path : Path | None
        Local path to the rendered MP4 file.
    """
    if not video_url and not video_path:
        raise ValueError("Either video_url or video_path must be provided.")
        
    bundle    = json.loads(bundle_path.read_text(encoding="utf-8"))
    caption   = build_caption(bundle)
    publisher = MetaReelPublisher(
        access_token  = get_meta_access_token(),
        ig_user_id    = get_instagram_account_id(),
        graph_version = get_meta_graph_version(),
    )
    return publisher.post_reel(caption=caption, video_url=video_url, video_path=video_path)


def cleanup_generated_outputs(bundle_path: Path) -> None:
    output_dir = bundle_path.parent
    if output_dir.exists():
        shutil.rmtree(output_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate all-sign horoscope content and optional Remotion reel."
    )
    parser.add_argument("--generate",     action="store_true", help="Generate a fresh horoscope content bundle.")
    parser.add_argument("--render",       action="store_true", help="Render a reel using Remotion.")
    parser.add_argument("--post",         action="store_true", help="Post the rendered reel to Instagram via Meta Graph API.")
    parser.add_argument("--cleanup",      action="store_true", help="Delete generated local outputs after a successful post.")
    parser.add_argument("--input",        type=str,            help="Path to an existing horoscope_bundle.json for rendering/posting.")
    parser.add_argument("--theme",        type=str,            help="Optional custom theme to push the content direction.")
    parser.add_argument(
        "--style",
        type=str,
        default="all_signs",
        help=(
            "Reel format to generate. Use fixed_self_respect, fire_do_not_chase, "
            "moved_on_but_didnt, moon_scorpio_exposure, daily, random_daily, random_viral, "
            "generator, or all_signs."
        ),
    )
    
    # Generator-specific arguments
    if prompt_generator:
        parser.add_argument("--gen-format",  default="4-sign",            choices=list(prompt_generator.FORMAT_META.keys()))
        parser.add_argument("--gen-theme",   default="attachment",         choices=list(prompt_generator.THEME_LINES.keys()))
        parser.add_argument("--gen-tone",    default="perceptive-friend",  choices=list(prompt_generator.TONE_INSTRUCTIONS.keys()))
        parser.add_argument("--gen-transit", default="mercury-rx",         choices=list(prompt_generator.TRANSIT_CONTEXT.keys()))

    parser.add_argument("--list-styles", action="store_true", help="Print available reel styles and exit.")
    parser.add_argument(
        "--video-url",
        type=str,
        help=(
            "Publicly accessible HTTPS URL of the MP4 to post. "
        ),
    )
    parser.add_argument(
        "--video-path",
        type=str,
        help="Local path to the MP4 file to post. If --render is used, this defaults to the newly rendered reel.",
    )
    parser.add_argument(
        "--target-signs",
        type=str,
        help="Comma-separated list of zodiac signs to target (overrides style defaults).",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="generated_reels",
        help="Directory where generated bundles are stored.",
    )
    args = parser.parse_args()

    if args.list_styles:
        print("Available reel styles:")
        print("  all_signs: Full 12-sign horoscope")
        print("  daily: Weekday rotation for automated posting")
        print("  random_daily: Random daily content pillar")
        print("  random_viral: Random focused identity reel")
        print("  generator: Dynamic prompt generator (use --gen-format, --gen-theme, etc.)")
        for key, preset in REEL_PRESETS.items():
            print(f"  {key}: {preset['headline']}")
        return

    output_root  = Path(args.output_root)
    bundle_path: Path | None  = None
    output_file: Path | None  = None

    if args.generate:
        gen_config = {}
        if args.target_signs:
            gen_config["target_signs"] = [s.strip() for s in args.target_signs.split(",")]
            
        if prompt_generator:
            gen_config.update({
                "format": getattr(args, "gen_format", "4-sign"),
                "theme": getattr(args, "gen_theme", "attachment"),
                "tone": getattr(args, "gen_tone", "perceptive-friend"),
                "transit": getattr(args, "gen_transit", "mercury-rx"),
            })
        bundle_path = generate_content(args.theme, output_root, args.style, gen_config=gen_config)
        print(f"Generated content bundle: {bundle_path}")

    if args.input:
        bundle_path = Path(args.input)

    if args.render:
        if bundle_path is None:
            raise RuntimeError("Provide --input or combine --generate --render.")
        output_file = render_reel(bundle_path)
        print(f"Rendered reel: {output_file}")

    if args.post:
        if bundle_path is None:
            raise RuntimeError("Provide --input or combine --generate --post.")
            
        vid_path = None
        if args.video_path:
            vid_path = Path(args.video_path)
        elif output_file:
            vid_path = output_file
            
        if not args.video_url and not vid_path:
            raise RuntimeError(
                "Must provide --video-url or --video-path to post. "
                "Or combine --render and --post to auto-post the rendered reel."
            )
            
        post_id = post_reel(bundle_path, video_url=args.video_url, video_path=vid_path)
        print(f"Published Instagram reel: {post_id}")
        if args.cleanup:
            cleanup_generated_outputs(bundle_path)
            print(f"Deleted local output directory: {bundle_path.parent}")

    if not args.generate and not args.render and not args.post:
        parser.print_help()


if __name__ == "__main__":
    main()
