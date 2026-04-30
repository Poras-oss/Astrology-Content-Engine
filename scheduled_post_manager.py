#!/usr/bin/env python3
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

STATE_FILE = Path("pipeline_state.json")
THEMES_FILE = Path("themes.json")

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

def load_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_next_state(state, themes):
    if not state:
        return {"theme_index": 0, "batch_index": 0}
    
    theme_idx = state.get("theme_index", 0)
    batch_idx = state.get("batch_index", 0)
    
    # Next batch
    batch_idx += 1
    
    # If all 3 batches are done (12 signs), move to next theme
    if batch_idx >= 3:
        batch_idx = 0
        theme_idx += 1
        
        # If all themes are done, restart from theme 0
        if theme_idx >= len(themes):
            theme_idx = 0
            
    return {"theme_index": theme_idx, "batch_index": batch_idx}

def main():
    themes = load_json(THEMES_FILE)
    if not themes:
        print("Error: themes.json not found or empty.")
        return

    state = load_json(STATE_FILE)
    next_state = get_next_state(state, themes)
    
    theme_idx = next_state["theme_index"]
    batch_idx = next_state["batch_index"]
    
    current_theme = themes[theme_idx]
    start_idx = batch_idx * 4
    end_idx = start_idx + 4
    target_signs = SIGNS[start_idx:end_idx]
    
    print(f"--- Running Pipeline ---")
    print(f"Theme: {current_theme['theme']} ({theme_idx + 1}/{len(themes)})")
    print(f"Batch: {batch_idx + 1}/3")
    print(f"Signs: {', '.join(target_signs)}")
    print(f"------------------------")

    # Construct the command
    # Using generator style with 4-sign format
    cmd = [
        "python", "viral_horoscope_pipeline.py",
        "--generate", "--render", "--post", "--cleanup",
        "--style", "generator",
        "--gen-format", "4-sign",
        "--gen-theme", current_theme["theme"],
        "--theme", current_theme["prompt"]
    ]
    
    # We need to pass the target signs. 
    # Since viral_horoscope_pipeline.py doesn't have a CLI flag for target_signs yet,
    # we can either add one or modify the call in generate_content.
    # Let's add a --target-signs flag to viral_horoscope_pipeline.py for easier CLI usage.
    
    # For now, I'll assume I'll add the flag.
    cmd.extend(["--target-signs", ",".join(target_signs)])
    
    try:
        subprocess.run(cmd, check=True)
        # Only update state if successful
        save_json(STATE_FILE, next_state)
        print(f"Successfully posted and updated state to theme {theme_idx}, batch {batch_idx}")
    except subprocess.CalledProcessError as e:
        print(f"Error during pipeline execution: {e}")
        exit(1)

if __name__ == "__main__":
    main()
