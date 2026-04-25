#!/usr/bin/env python3
"""
Standalone horoscope content + reel pipeline.

What it does:
1. Generates all 12 zodiac sign readings in one Groq call
2. Saves a structured JSON bundle optimized for Instagram carousel/reel copy
3. Writes caption + voiceover text assets
4. Optionally calls a local Remotion project to render a 9:16 reel

Usage:
    python viral_horoscope_pipeline.py --generate
    python viral_horoscope_pipeline.py --generate --theme "soft launch energy"
    python viral_horoscope_pipeline.py --generate --render
    python viral_horoscope_pipeline.py --render --input generated_reels\\20260425_230500\\horoscope_bundle.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests


ZODIAC_SIGNS = [
    {"name": "Aries", "element": "Fire", "symbol": "Ram", "palette": ["#2A0F14", "#7A1C2B", "#FF7A59"]},
    {"name": "Taurus", "element": "Earth", "symbol": "Bull", "palette": ["#0E221B", "#23573A", "#E8C16B"]},
    {"name": "Gemini", "element": "Air", "symbol": "Twins", "palette": ["#111827", "#224E88", "#7ED7F7"]},
    {"name": "Cancer", "element": "Water", "symbol": "Crab", "palette": ["#0F1A2E", "#284B8A", "#B9D8FF"]},
    {"name": "Leo", "element": "Fire", "symbol": "Lion", "palette": ["#2A1405", "#8A430F", "#FFC145"]},
    {"name": "Virgo", "element": "Earth", "symbol": "Maiden", "palette": ["#152018", "#45634C", "#DCE8B4"]},
    {"name": "Libra", "element": "Air", "symbol": "Scales", "palette": ["#1D1424", "#6E4A8C", "#F5B8E8"]},
    {"name": "Scorpio", "element": "Water", "symbol": "Scorpion", "palette": ["#120A19", "#4C1D5F", "#FF6AA2"]},
    {"name": "Sagittarius", "element": "Fire", "symbol": "Archer", "palette": ["#1C1222", "#6441A5", "#FFB86B"]},
    {"name": "Capricorn", "element": "Earth", "symbol": "Sea Goat", "palette": ["#141414", "#434343", "#E6D3A3"]},
    {"name": "Aquarius", "element": "Air", "symbol": "Water Bearer", "palette": ["#0A1A22", "#0F6E7A", "#95F3FF"]},
    {"name": "Pisces", "element": "Water", "symbol": "Fish", "palette": ["#140F24", "#3D2C78", "#9BC8FF"]},
]

SIGN_INDEX = {sign["name"]: sign for sign in ZODIAC_SIGNS}
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_META_GRAPH_VERSION = "v24.0"


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


def get_groq_api_key() -> str:
    local_env = load_dotenv(Path(".env"))
    return (
        os.getenv("GROQ_API_KEY")
        or os.getenv("groq_api")
        or local_env.get("GROQ_API_KEY")
        or local_env.get("groq_api")
        or ""
    )


def get_meta_access_token() -> str:
    local_env = load_dotenv(Path(".env"))
    return (
        os.getenv("META_ACCESS_TOKEN")
        or os.getenv("INSTAGRAM_ACCESS_TOKEN")
        or local_env.get("META_ACCESS_TOKEN")
        or local_env.get("INSTAGRAM_ACCESS_TOKEN")
        or ""
    )


def get_instagram_account_id() -> str:
    local_env = load_dotenv(Path(".env"))
    return (
        os.getenv("INSTAGRAM_USER_ID")
        or os.getenv("INSTAGRAM_ACCOUNT_ID")
        or os.getenv("IG_USER_ID")
        or local_env.get("INSTAGRAM_USER_ID")
        or local_env.get("INSTAGRAM_ACCOUNT_ID")
        or local_env.get("IG_USER_ID")
        or ""
    )


def get_meta_graph_version() -> str:
    local_env = load_dotenv(Path(".env"))
    return (
        os.getenv("META_GRAPH_API_VERSION")
        or local_env.get("META_GRAPH_API_VERSION")
        or DEFAULT_META_GRAPH_VERSION
    )


def get_npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


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
                {"role": "user", "content": prompt},
            ],
        },
        timeout=90,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def extract_json_payload(raw: str) -> str:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text.strip()




def repair_json_string(text: str) -> str:
    r"""
    Fix common LLM JSON output issues:
    1. Literal newlines/tabs inside strings → escaped versions
    2. Invalid escape sequences like \e, \p, \' → escaped backslash or removed
    """
    result = []
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

        # Inside a string
        if char == '\\':
            if i + 1 < len(text):
                next_char = text[i + 1]
                if next_char in VALID_ESCAPES:
                    # Valid escape — keep as-is
                    result.append(char)
                    result.append(next_char)
                    i += 2
                else:
                    # Invalid escape — escape the backslash
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

        # Literal control characters inside strings
        if char == '\n':
            result.append('\\n')
        elif char == '\r':
            result.append('\\r')
        elif char == '\t':
            result.append('\\t')
        else:
            result.append(char)
        i += 1

    return ''.join(result)


def escape_control_chars_in_strings(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False

    for char in text:
        if in_string:
            if escape:
                result.append(char)
                escape = False
                continue
            if char == "\\":
                result.append(char)
                escape = True
                continue
            if char == '"':
                result.append(char)
                in_string = False
                continue
            if char == "\n":
                result.append("\\n")
                continue
            if char == "\r":
                result.append("\\r")
                continue
            if char == "\t":
                result.append("\\t")
                continue
            result.append(char)
            continue

        result.append(char)
        if char == '"':
            in_string = True

    return "".join(result)

def parse_model_json(raw: str) -> dict:
    payload = extract_json_payload(raw)
    
    # Attempt 1: parse as-is
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass

    # Attempt 2: repair and retry
    try:
        repaired = repair_json_string(payload)
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        # Attempt 3: strip to the bad character and show context for debugging
        char_pos = e.pos
        snippet = payload[max(0, char_pos - 60):char_pos + 60]
        raise RuntimeError(
            f"JSON repair failed at position {char_pos}.\n"
            f"Context: ...{snippet!r}...\n"
            f"Original error: {e}"
        ) from e


def build_prompt(theme: str | None = None) -> str:
    today = dt.datetime.now().strftime("%B %d, %Y")
    sign_list = ", ".join(sign["name"] for sign in ZODIAC_SIGNS)
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


def normalize_bundle(bundle: dict[str, Any], theme: str | None) -> dict[str, Any]:
    meta = bundle.get("meta", {})
    signs = bundle.get("signs", [])

    normalized_signs = []
    seen: set[str] = set()
    sign_lookup = {item.get("sign", ""): item for item in signs if isinstance(item, dict)}

    for sign in ZODIAC_SIGNS:
        generated = sign_lookup.get(sign["name"], {})
        seen.add(sign["name"])
        reel_lines = generated.get(
            "reel_lines",
            [
                generated.get("theme", "A shift is happening."),
                generated.get("private_truth", "You can feel it already."),
                generated.get("screenshot_line", "This one is yours."),
            ],
        )
        normalized_signs.append(
            {
                "sign": sign["name"],
                "element": sign["element"],
                "symbol": sign["symbol"],
                "palette": sign["palette"],
                "theme": generated.get("theme", f"{sign['name']} is entering a sharper chapter"),
                "private_truth": generated.get(
                    "private_truth",
                    f"{sign['name']} is done pretending they do not care.",
                ),
                "tension": generated.get(
                    "tension",
                    "You want clarity, but part of you still performs distance to stay safe.",
                ),
                "shift": generated.get(
                    "shift",
                    "The right move is not louder effort. It is cleaner self-respect.",
                ),
                "screenshot_line": generated.get(
                    "screenshot_line",
                    "You are not hard to love. You are hard to manipulate now.",
                ),
                "share_line": generated.get(
                    "share_line",
                    "Send this to the version of you that keeps shrinking to feel chosen.",
                ),
                "reel_lines": ensure_three_lines(
                    {
                        "reel_lines": reel_lines,
                        "theme": generated.get("theme", "A shift is happening."),
                        "private_truth": generated.get("private_truth", "You can feel it already."),
                        "screenshot_line": generated.get("screenshot_line", "This one is yours."),
                    }
                ),
                "keywords": generated.get("keywords", [sign["element"], "emotion", "timing"])[:3],
            }
        )

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "theme_request": theme or "",
        "meta": {
            "title": meta.get("title", "The Horoscope They Feel"),
            "hook": meta.get("hook", "These are not soft horoscopes."),
            "theme": meta.get("theme", theme or "psychology wrapped in cosmic timing"),
            "caption_hook": meta.get("caption_hook", "This one is going to feel a little too personal."),
            "caption_body": meta.get(
                "caption_body",
                "Your sign is not just a mood today. It is a mirror. Some signs are protecting too much. "
                "Some are craving honesty. Some are finally too tired to keep performing for breadcrumbs.",
            ),
            "cta": meta.get("cta", "Save this, send it to your sign twin, and comment the line that dragged you."),
            "audio_direction": meta.get("audio_direction", "moody, cinematic, intimate, slow-burn"),
            "cover_text": meta.get("cover_text", "THE HOROSCOPE THAT READS YOU"),
        },
        "signs": normalized_signs,
    }


def ensure_three_lines(sign: dict[str, Any]) -> list[str]:
    raw_lines = sign.get("reel_lines", [])
    lines = [str(line).strip() for line in raw_lines if str(line).strip()] if isinstance(raw_lines, list) else []

    fallbacks = [
        sign.get("theme", "A shift is happening."),
        sign.get("private_truth", "You can feel it already."),
        sign.get("screenshot_line", "This one is yours."),
    ]

    for fallback in fallbacks:
        text = str(fallback).strip()
        if len(lines) >= 3:
            break
        if text:
            lines.append(text)

    while len(lines) < 3:
        lines.append("This sign is moving differently now.")

    return lines[:3]


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
    bundle_path = output_dir / "horoscope_bundle.json"
    caption_path = output_dir / "instagram_caption.txt"
    voiceover_path = output_dir / "voiceover_script.txt"

    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    caption_text = build_caption(bundle)
    caption_path.write_text(caption_text, encoding="utf-8")
    voiceover_path.write_text(build_voiceover_script(bundle), encoding="utf-8")
    return bundle_path


def build_caption(bundle: dict[str, Any]) -> str:
    return (
        f"{bundle['meta']['caption_hook']}\n\n"
        f"{bundle['meta']['caption_body']}\n\n"
        f"{bundle['meta']['cta']}\n"
    )


class MetaReelPublisher:
    def __init__(self, access_token: str, ig_user_id: str, graph_version: str | None = None):
        if not access_token:
            raise RuntimeError("Missing META_ACCESS_TOKEN / INSTAGRAM_ACCESS_TOKEN.")
        if not ig_user_id:
            raise RuntimeError("Missing INSTAGRAM_USER_ID / INSTAGRAM_ACCOUNT_ID / IG_USER_ID.")
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.graph_version = graph_version or get_meta_graph_version()
        self.base_url = f"https://graph.facebook.com/{self.graph_version}"

    def _create_reel_container(self, caption: str) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/{self.ig_user_id}/media",
            data={
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": caption,
                "share_to_feed": "true",
                "access_token": self.access_token,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        if "id" not in payload or "uri" not in payload:
            raise RuntimeError(f"Unexpected container response: {payload}")
        return payload

    def _upload_video_binary(self, upload_uri: str, video_path: Path) -> None:
        file_size = video_path.stat().st_size
        with video_path.open("rb") as handle:
            response = requests.post(
                upload_uri,
                headers={
                    "Authorization": f"OAuth {self.access_token}",
                    "offset": "0",
                    "file_size": str(file_size),
                    "Content-Type": "video/mp4",
                },
                data=handle.read(),
                timeout=600,
            )
        response.raise_for_status()
        payload = response.json()
        if payload.get("success") is not True:
            raise RuntimeError(f"Meta upload did not report success: {payload}")

    def _wait_until_ready(self, container_id: str, timeout_seconds: int = 900, poll_seconds: int = 15) -> None:
        deadline = time.time() + timeout_seconds
        last_payload: dict[str, Any] | None = None

        while time.time() < deadline:
            response = requests.get(
                f"{self.base_url}/{container_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.access_token,
                },
                timeout=60,
            )
            response.raise_for_status()
            last_payload = response.json()
            status_code = str(last_payload.get("status_code", "")).upper()
            status = str(last_payload.get("status", "")).upper()

            if status_code == "FINISHED":
                return
            if status_code in {"ERROR", "EXPIRED"} or status in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Meta processing failed: {last_payload}")

            time.sleep(poll_seconds)

        raise TimeoutError(f"Timed out waiting for Meta to finish processing: {last_payload}")

    def _publish_container(self, container_id: str) -> str:
        response = requests.post(
            f"{self.base_url}/{self.ig_user_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        post_id = payload.get("id")
        if not post_id:
            raise RuntimeError(f"Unexpected publish response: {payload}")
        return str(post_id)

    def post_reel(self, video_path: Path, caption: str) -> str:
        container = self._create_reel_container(caption)
        self._upload_video_binary(container["uri"], video_path)
        self._wait_until_ready(container["id"])
        return self._publish_container(container["id"])


def generate_content(theme: str | None, output_root: Path) -> Path:
    api_key = get_groq_api_key()
    prompt = build_prompt(theme)
    raw = call_groq(prompt, SYSTEM_PROMPT, api_key)
    parsed = parse_model_json(raw)
    bundle = normalize_bundle(parsed, theme)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / timestamp
    bundle_path = write_bundle_files(bundle, output_dir)
    return bundle_path


def render_reel(bundle_path: Path, output_file: Path | None = None) -> Path:
    remotion_dir = Path("remotion_reel")
    if not remotion_dir.exists():
        raise RuntimeError("Missing remotion_reel directory.")
    if not (remotion_dir / "node_modules").exists():
        raise RuntimeError(
            "Remotion dependencies are not installed yet. Run: npm.cmd install --prefix .\\remotion_reel"
        )

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if output_file is None:
        output_file = bundle_path.parent / "horoscope_reel.mp4"

    render_bundle_path = remotion_dir / "src" / "data" / "render-bundle.json"
    render_bundle_path.parent.mkdir(parents=True, exist_ok=True)
    render_bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")

    command = [
        get_npm_command(),
        "run",
        "render",
        "--",
        str(output_file),
    ]
    subprocess.run(command, cwd=remotion_dir, check=True)
    return output_file


def post_reel(bundle_path: Path, reel_path: Path) -> str:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    caption = build_caption(bundle)
    publisher = MetaReelPublisher(
        access_token=get_meta_access_token(),
        ig_user_id=get_instagram_account_id(),
        graph_version=get_meta_graph_version(),
    )
    return publisher.post_reel(reel_path, caption)


def cleanup_generated_outputs(bundle_path: Path) -> None:
    output_dir = bundle_path.parent
    if output_dir.exists():
        shutil.rmtree(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all-sign horoscope content and optional Remotion reel.")
    parser.add_argument("--generate", action="store_true", help="Generate a fresh horoscope content bundle.")
    parser.add_argument("--render", action="store_true", help="Render a reel using Remotion.")
    parser.add_argument("--post", action="store_true", help="Post the rendered reel to Instagram via Meta Graph API.")
    parser.add_argument("--cleanup", action="store_true", help="Delete generated local outputs after a successful post.")
    parser.add_argument("--input", type=str, help="Path to an existing horoscope_bundle.json for rendering.")
    parser.add_argument("--theme", type=str, help="Optional custom theme to push the content direction.")
    parser.add_argument(
        "--output-root",
        type=str,
        default="generated_reels",
        help="Directory where generated bundles are stored.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    bundle_path: Path | None = None
    output_file: Path | None = None

    if args.generate:
        bundle_path = generate_content(args.theme, output_root)
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
        if output_file is None:
            output_file = bundle_path.parent / "horoscope_reel.mp4"
        if not output_file.exists():
            raise RuntimeError(f"Rendered reel not found: {output_file}")
        post_id = post_reel(bundle_path, output_file)
        print(f"Published Instagram reel: {post_id}")
        if args.cleanup:
            cleanup_generated_outputs(bundle_path)
            print(f"Deleted local output directory: {bundle_path.parent}")

    if not args.generate and not args.render and not args.post:
        parser.print_help()


if __name__ == "__main__":
    main()
