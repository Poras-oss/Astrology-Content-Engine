#!/usr/bin/env python3
"""
upload_to_cloudinary.py  –  Upload a local video file to Cloudinary and
print the secure public URL to stdout.

Usage (called by the GitHub Actions workflow):
    python upload_to_cloudinary.py path/to/horoscope_reel.mp4

Required environment variables:
    CLOUDINARY_CLOUD_NAME
    CLOUDINARY_API_KEY
    CLOUDINARY_API_SECRET

Free-tier limits (Cloudinary):
    - 25 GB storage
    - 25 GB monthly bandwidth
    - Transformations included
    All more than enough for daily 9:16 reels.

Setup (one-time):
    1. Sign up at https://cloudinary.com  (free, no credit card)
    2. From your dashboard copy Cloud Name, API Key, API Secret
    3. Add them as GitHub Actions secrets:
         CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

import requests


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
    local_env = load_dotenv(Path(".env"))
    val = (os.environ.get(key, "") or local_env.get(key, "")).strip()
    if not val:
        raise RuntimeError(f"Missing environment variable: {key}")
    return val


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
