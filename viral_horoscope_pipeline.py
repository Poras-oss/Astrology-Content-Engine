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
import hashlib
import hmac
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import requests
from pathlib import Path
from typing import Any

import requests


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
DEFAULT_META_GRAPH_VERSION = "v22.0"  # pinned to a stable, supported version


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


def get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise RuntimeError(f"Missing environment variable: {key}")
    return val


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

def build_prompt(theme: str | None = None) -> str:
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


def generate_signature(params: dict[str, str], api_secret: str) -> str:
    """
    Cloudinary signature: SHA-1 of alphabetically sorted param string + secret.
    Exclude `file`, `api_key`, and `resource_type` from the signed string.
    """
    excluded = {"file", "api_key", "resource_type"}
    sorted_pairs = sorted(
        f"{k}={v}" for k, v in params.items() if k not in excluded
    )
    to_sign = "&".join(sorted_pairs) + api_secret
    return hashlib.sha1(to_sign.encode("utf-8")).hexdigest()
 
 
def upload_video(file_path: str) -> str:
    """
    Upload a video to Cloudinary using the authenticated upload API.
    Returns the secure public URL (https://...).
    """
    cloud_name = get_env("CLOUDINARY_CLOUD_NAME")
    api_key    = get_env("CLOUDINARY_API_KEY")
    api_secret = get_env("CLOUDINARY_API_SECRET")
 
    timestamp  = str(int(time.time()))
    folder     = "horoscope_reels"
 
    # Parameters to sign (no `file`, `api_key`, `resource_type`)
    params_to_sign: dict[str, str] = {
        "folder":    folder,
        "timestamp": timestamp,
    }
 
    signature = generate_signature(params_to_sign, api_secret)
 
    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/video/upload"
 
    with open(file_path, "rb") as video_file:
        response = requests.post(
            upload_url,
            data={
                "api_key":   api_key,
                "timestamp": timestamp,
                "signature": signature,
                "folder":    folder,
            },
            files={"file": video_file},
            timeout=300,  # 5-minute timeout for large video uploads
        )
 
    if not response.ok:
        try:
            err = response.json()
        except Exception:
            err = response.text
        raise RuntimeError(f"Cloudinary upload failed {response.status_code}: {err}")
 
    data = response.json()
    secure_url = data.get("secure_url")
    if not secure_url:
        raise RuntimeError(f"Cloudinary returned no secure_url: {data}")
 
    return secure_url


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


def normalize_bundle(bundle: dict[str, Any], theme: str | None) -> dict[str, Any]:
    meta  = bundle.get("meta",  {})
    signs = bundle.get("signs", [])

    sign_lookup: dict[str, dict] = {
        item.get("sign", ""): item
        for item in signs
        if isinstance(item, dict)
    }

    normalized_signs = []
    for sign in ZODIAC_SIGNS:
        generated = sign_lookup.get(sign["name"], {})
        reel_lines = generated.get(
            "reel_lines",
            [
                generated.get("theme",          "A shift is happening."),
                generated.get("private_truth",  "You can feel it already."),
                generated.get("screenshot_line","This one is yours."),
            ],
        )
        normalized_signs.append({
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
        })

    return {
        "generated_at":  dt.datetime.now().isoformat(timespec="seconds"),
        "theme_request": theme or "",
        "meta": {
            "title":         meta.get("title",         "The Horoscope They Feel"),
            "hook":          meta.get("hook",           "These are not soft horoscopes."),
            "theme":         meta.get("theme",          theme or "psychology wrapped in cosmic timing"),
            "caption_hook":  meta.get("caption_hook",  "This one is going to feel a little too personal."),
            "caption_body":  meta.get("caption_body",  (
                "Your sign is not just a mood today. It is a mirror. Some signs are protecting too much. "
                "Some are craving honesty. Some are finally too tired to keep performing for breadcrumbs."
            )),
            "cta":            meta.get("cta",            "Save this, send it to your sign twin, and comment the line that dragged you."),
            "audio_direction":meta.get("audio_direction","moody, cinematic, intimate, slow-burn"),
            "cover_text":     meta.get("cover_text",     "THE HOROSCOPE THAT READS YOU"),
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
            "share_to_feed": True,        # boolean, not string
            "access_token":  self.access_token,
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
    def post_reel(self, video_url: str, caption: str) -> str:
        """
        Full three-step Reels publishing flow.

        Parameters
        ----------
        video_url : str
            Publicly accessible HTTPS URL to the rendered MP4 file.
        caption   : str
            Instagram caption text.

        Returns
        -------
        str  –  The published Instagram post ID.
        """
        container_id = self._create_reel_container(video_url, caption)
        self._wait_until_ready(container_id)
        post_id = self._publish_container(container_id)
        print(f"[Meta] Published! Post ID: {post_id}")
        return post_id


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def generate_content(theme: str | None, output_root: Path) -> Path:
    api_key    = get_groq_api_key()
    prompt     = build_prompt(theme)
    raw        = call_groq(prompt, SYSTEM_PROMPT, api_key)
    parsed     = parse_model_json(raw)
    bundle     = normalize_bundle(parsed, theme)
    timestamp  = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / timestamp
    return write_bundle_files(bundle, output_dir)


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

    render_bundle_path = remotion_dir / "src" / "data" / "render-bundle.json"
    render_bundle_path.parent.mkdir(parents=True, exist_ok=True)
    render_bundle_path.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    subprocess.run(
        [get_npm_command(), "run", "render", "--", str(output_file)],
        cwd=remotion_dir,
        check=True,
    )
    return output_file


def post_reel(bundle_path: Path, video_url: str) -> str:
    """
    Post a reel to Instagram.

    Parameters
    ----------
    bundle_path : Path
        Path to the horoscope_bundle.json (for the caption).
    video_url : str
        Publicly accessible HTTPS URL of the rendered MP4.
        Upload your local file to S3 / R2 / Cloudinary first, then pass the URL here.
    """
    bundle    = json.loads(bundle_path.read_text(encoding="utf-8"))
    caption   = build_caption(bundle)
    publisher = MetaReelPublisher(
        access_token  = get_meta_access_token(),
        ig_user_id    = get_instagram_account_id(),
        graph_version = get_meta_graph_version(),
    )
    return publisher.post_reel(video_url, caption)


def cleanup_generated_outputs(bundle_path: Path) -> None:
    output_dir = bundle_path.parent
    if output_dir.exists():
        shutil.rmtree(output_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python upload_to_cloudinary.py <path_to_video.mp4>", file=sys.stderr)
        sys.exit(1)
 
    file_path = sys.argv[1]
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
 
    # Print ONLY the URL to stdout so the workflow can capture it cleanly
    url = upload_video(file_path)
    print(url)
 
 
if __name__ == "__main__":
    main()