"""
Astrology Reel Prompt Generator
Generates viral Instagram Reel prompts for astrology apps targeting Millennials.
"""

from datetime import datetime
import os
from dataclasses import dataclass
from typing import Literal


# ── Types ────────────────────────────────────────────────────────────────────

FormatType  = Literal["4-sign", "all12", "3sign-rival", "1sign"]
ThemeType   = Literal["attachment", "ego", "boundaries", "romance", "career", "shadow"]
ToneType    = Literal["perceptive-friend", "dry-wit", "blunt", "warm"]
TransitType = Literal["mercury-rx", "venus-pisces", "mars-gemini", "saturn-sq", "full-moon", "north-node"]


# ── Config maps ──────────────────────────────────────────────────────────────

FORMAT_META: dict[FormatType, dict] = {
    "4-sign":      {"count": 4,  "label": "4-sign spotlight",  "hook_style": "Named & exposed",       "mechanic": "Send this to them"},
    "all12":       {"count": 12, "label": "All 12 signs",       "hook_style": "Scroll to find yours",  "mechanic": "Share with your circle"},
    "3sign-rival": {"count": 3,  "label": "3-sign rivalry",     "hook_style": "Called out directly",   "mechanic": "Tag the one who did this"},
    "1sign":       {"count": 1,  "label": "Single sign deep-dive", "hook_style": "Deep recognition",   "mechanic": "Screenshot & save"},
}

THEME_LINES: dict[ThemeType, str] = {
    "attachment": "how your sign clings, avoids, or disappears when love gets real",
    "ego":        "where your sign's ego quietly gets in its own way",
    "boundaries": "the boundary your sign sets — and the one it keeps crossing for others",
    "romance":    "what your sign actually wants vs. what it will admit to wanting",
    "career":     "the hidden ambition move your sign is about to make",
    "shadow":     "the version of your sign that shows up when no one's watching",
}

THEME_EMOTIONS: dict[ThemeType, str] = {
    "attachment": "attachment patterns, avoidance, anxious behaviours",
    "ego":        "ego, pride, self-image, insecurity masked as confidence",
    "boundaries": "boundaries, people-pleasing, resentment",
    "romance":    "romantic chemistry, desire, longing",
    "career":     "ambition, competition, fear of visibility",
    "shadow":     "shadow behaviour, projection, blind spots",
}

TONE_INSTRUCTIONS: dict[ToneType, str] = {
    "perceptive-friend": (
        "Write as a perceptive friend with taste — someone who studied psychology "
        "and reads charts on the side. Not a wellness influencer. Not a Reddit astrology post."
    ),
    "dry-wit": (
        "Write with dry, deadpan wit. Observations land like receipts, not lectures. "
        "No warmth, all precision."
    ),
    "blunt": (
        "Be blunt and direct. No softening. State the truth about each sign like "
        "you're reading from a file you weren't supposed to find."
    ),
    "warm": (
        "Be warm and intimate — like a late-night voice note from someone who genuinely "
        "gets you. Soft but sharp."
    ),
}

TRANSIT_CONTEXT: dict[TransitType, str] = {
    "mercury-rx":    "Mercury retrograde (communication, contracts, exes resurfacing, misread signals)",
    "venus-pisces":  "Venus in Pisces (idealized love, dissolution of boundaries, longing, romanticism)",
    "mars-gemini":   "Mars in Gemini (scattered energy, fast decisions, verbal aggression, mental restlessness)",
    "saturn-sq":     "Saturn square (accountability, delayed rewards, pressure on foundations, maturity tests)",
    "full-moon":     "Full Moon energy (emotional peaks, reveals, completions, what can no longer be hidden)",
    "north-node":    "North Node shift (destiny redirects, soul-level urges, moving away from comfort zones)",
}

BANNED_WORDS = [
    "major shift", "stay grounded", "new chapter", "trust the universe",
    "take bold action", "energy", "vibration", "manifest",
]


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class PromptConfig:
    format:       FormatType       = "4-sign"
    theme:        ThemeType        = "attachment"
    tone:         ToneType         = "perceptive-friend"
    transit:      TransitType      = "mercury-rx"
    target_signs: list[str] | None = None


# ── Core generator ────────────────────────────────────────────────────────────

def generate_prompt(config: PromptConfig) -> str:
    """Return the full prompt string for the given config."""

    day_fmt = "%#d" if os.name == "nt" else "%-d"
    today     = datetime.now().strftime(f"%A, %B {day_fmt}, %Y")
    meta      = FORMAT_META[config.format]
    n         = meta["count"]
    theme_ln  = THEME_LINES[config.theme]
    theme_emo = THEME_EMOTIONS[config.theme]
    tone_ins  = TONE_INSTRUCTIONS[config.tone]
    transit   = TRANSIT_CONTEXT[config.transit]
    banned    = ", ".join(f'"{w}"' for w in BANNED_WORDS)

    # Count rule
    if config.target_signs:
        sign_list = ", ".join(config.target_signs)
        count_rule = f"Include exactly these zodiac signs in this order: {sign_list}. Do not include any other signs."
    elif n == 1:
        count_rule = "Return exactly 1 sign object in the signs array. Choose the sign most activated by this transit."
    else:
        count_rule = (
            f"Return exactly {n} sign objects in the signs array. "
            f"Pick the {n} signs most activated by this transit. Do not repeat sign names."
            if n < 12
            else "Include all 12 zodiac signs. Do not repeat sign names."
        )

    prompt = f"""Today is {today}.

Create one focused, high-retention Instagram Reel script in this exact viral style:

HEADLINE FORMAT: "The thing your [sign] does when [emotionally activated situation]"

Core angle:
Expose {theme_ln}.

Active transit to weave in:
{transit}
Every sign card must name a specific element from this transit — the placement, the tension it creates, or the behaviour it triggers in that sign. This is the astrology substance that makes the reel feel real, not generic.

Targeting:
- Millennials (25–40) on Instagram Reels and TikTok
- The first 2 seconds must make the viewer feel either named, exposed, warned, or curious
- This is not a daily all-sign horoscope — it is a sharp identity reel for a focused group

Tone:
{tone_ins}

Creative goal:
- Make the viewer think "I need to send this to them"
- Every sign should have a specific emotional receipt, not generic advice
- Use mild tension, {theme_emo}, and self-awareness
- Add astrology substance: name the transit, placement, modality, element, ruling planet, or Moon mood that explains why this sign is being activated
- Each sign card must contain ONE astrology reason and ONE recognisable real-life behaviour
- Sound like a perceptive friend with taste — not a therapist, preacher, or fortune cookie
- NEVER use: {banned}
- Never diagnose people or make absolute harmful claims
- Give each sign a DIFFERENT reason — no repeated templates

Return valid JSON only with this exact shape:
{{
  "meta": {{
    "title": "short series title, 3-6 words",
    "hook": "first spoken line of the reel — under 10 words, makes viewer feel called out",
    "theme": "1 sentence theme summary",
    "caption_hook": "opening caption line, highly scroll-stopping, no hashtags",
    "caption_body": "70-140 word caption for Instagram — intimate, no generic wellness language, ends on a question or invitation",
    "cta": "1 line call to action — tag someone or save this",
    "audio_direction": "2-3 words describing the music mood (e.g. lo-fi melancholy, slow cinematic, soft tension)",
    "cover_text": "3-5 words for the reel cover thumbnail"
  }},
  "signs": [
    {{
      "sign": "Aries",
      "theme": "3-6 word identity label",
      "private_truth": "1 emotionally sharp sentence about what this sign secretly does",
      "tension": "1 sentence naming the internal conflict activated by this transit",
      "shift": "1 sentence telling them what changes or what they need to see",
      "screenshot_line": "1 punchy line built to be screenshotted and shared",
      "share_line": "1 line they would send to a specific person in their life",
      "reel_lines": [
        "Line 1: direct callout — under 11 words",
        "Line 2: transit trigger + real-life behaviour — under 11 words",
        "Line 3: the warning, reveal, or boundary — under 11 words"
      ],
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}

Rules:
- {count_rule}
- Keep each reel_lines item under 11 words
- Line 1 = direct callout. Line 2 = astrology trigger + behaviour. Line 3 = warning, reveal, or boundary
- Make the hook and cover_text match the headline style exactly
- Escape any line breaks inside JSON strings as \\n
- Return ONLY valid JSON. No markdown, no backticks, no preamble."""

    return prompt


# ── Batch generator ───────────────────────────────────────────────────────────

def generate_all_prompts() -> dict[str, str]:
    """
    Generate every combination of format × theme × tone × transit.
    Returns a dict keyed by '{format}__{theme}__{tone}__{transit}'.
    """
    results = {}
    for fmt in FORMAT_META:
        for theme in THEME_LINES:
            for tone in TONE_INSTRUCTIONS:
                for transit in TRANSIT_CONTEXT:
                    key = f"{fmt}__{theme}__{tone}__{transit}"
                    cfg = PromptConfig(format=fmt, theme=theme, tone=tone, transit=transit)
                    results[key] = generate_prompt(cfg)
    return results


# ── Quick helpers ─────────────────────────────────────────────────────────────

def get_viral_picks() -> list[tuple[str, str]]:
    """
    Return the highest-virality prompt configurations with their prompts.
    These combos score 10/10 based on emotional activation + shareability.
    """
    picks = [
        ("shadow × romance × blunt × full-moon",
         PromptConfig("4-sign",  "shadow",     "blunt",            "full-moon")),
        ("attachment × romance × perceptive-friend × mercury-rx",
         PromptConfig("4-sign",  "attachment", "perceptive-friend", "mercury-rx")),
        ("ego × career × dry-wit × saturn-sq",
         PromptConfig("3sign-rival", "ego",    "dry-wit",           "saturn-sq")),
        ("boundaries × attachment × warm × venus-pisces",
         PromptConfig("4-sign",  "boundaries", "warm",              "venus-pisces")),
    ]
    return [(label, generate_prompt(cfg)) for label, cfg in picks]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json, sys

    parser = argparse.ArgumentParser(description="Astrology Reel Prompt Generator")
    parser.add_argument("--format",  default="4-sign",            choices=list(FORMAT_META.keys()))
    parser.add_argument("--theme",   default="attachment",         choices=list(THEME_LINES.keys()))
    parser.add_argument("--tone",    default="perceptive-friend",  choices=list(TONE_INSTRUCTIONS.keys()))
    parser.add_argument("--transit", default="mercury-rx",         choices=list(TRANSIT_CONTEXT.keys()))
    parser.add_argument("--all",     action="store_true",          help="Generate all combinations")
    parser.add_argument("--viral",   action="store_true",          help="Print top viral picks only")
    args = parser.parse_args()

    if args.viral:
        for label, prompt in get_viral_picks():
            print(f"\n{'='*60}")
            print(f"  {label}")
            print(f"{'='*60}\n")
            print(prompt)
        sys.exit(0)

    if args.all:
        all_prompts = generate_all_prompts()
        print(json.dumps({k: v for k, v in all_prompts.items()}, indent=2, ensure_ascii=False))
        sys.exit(0)

    cfg    = PromptConfig(format=args.format, theme=args.theme, tone=args.tone, transit=args.transit)
    result = generate_prompt(cfg)
    print(result)