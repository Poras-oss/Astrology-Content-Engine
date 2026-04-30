# Astrology Content Engine Commands

Run these commands from the project root:

```powershell
cd "D:\Astrology Content Engine"
```

## One-Time Setup

Install Remotion dependencies:

```powershell
npm.cmd install --prefix .\remotion_reel
```

Make sure `.env` contains your keys:

```text
GROQ_API_KEY=...
META_ACCESS_TOKEN=...
INSTAGRAM_USER_ID=...
```

## See Available Reel Styles

```powershell
python .\viral_horoscope_pipeline.py --list-styles
```

Available styles:

```text
all_signs
daily
random_daily
random_viral
daily_transit
love_attachment
shadow_callout
compatibility_drama
money_power
weekend_tension
moon_sign_mood
placement_based
fixed_self_respect
fire_do_not_chase
moved_on_but_didnt
moon_scorpio_exposure
generator
```

`daily` uses a date-based rotation for automated posting, so the account keeps cycling through different content pillars:

```text
daily_transit
love_attachment
shadow_callout
compatibility_drama
money_power
weekend_tension
moon_sign_mood
placement_based
```

## Use the Dynamic Prompt Generator

The `generator` style allows you to mix and match formats, themes, tones, and transits for maximum variety.

```powershell
# Basic generator usage
python .\viral_horoscope_pipeline.py --generate --render --style generator

# Customizing the generation
python .\viral_horoscope_pipeline.py --generate --render --style generator `
    --gen-format all12 `
    --gen-theme shadow `
    --gen-tone blunt `
    --gen-transit full-moon
```

Available generator options:

- **Formats:** `4-sign`, `all12`, `3sign-rival`, `1sign`
- **Themes:** `attachment`, `ego`, `boundaries`, `romance`, `career`, `shadow`
- **Tones:** `perceptive-friend`, `dry-wit`, `blunt`, `warm`
- **Transits:** `mercury-rx`, `venus-pisces`, `mars-gemini`, `saturn-sq`, `full-moon`, `north-node`

## Daily Automation


Daily automated style:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style daily
```

Random daily content pillar:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style random_daily
```

Daily transit reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style daily_transit
```

Love and attachment reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style love_attachment
```

Shadow-work callout reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style shadow_callout
```

Compatibility drama reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style compatibility_drama
```

Money, career, and reputation reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style money_power
```

Weekend tension reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style weekend_tension
```

Moon-sign mood reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style moon_sign_mood
```

Placement-based reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style placement_based
```

Fixed signs self-respect reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style fixed_self_respect
```

Fire signs do-not-chase reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style fire_do_not_chase
```

Signs pretending they moved on:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style moved_on_but_didnt
```

Moon in Scorpio exposure reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style moon_scorpio_exposure
```

Random focused viral format:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style random_viral
```

## Daily Automation

The GitHub Actions workflow `.github/workflows/daily-horoscope-reel.yml` runs every day at `09:55 AM Asia/Kolkata`.

On scheduled runs it uses:

```powershell
python viral_horoscope_pipeline.py --generate --style daily
```

Then it renders, uploads the MP4 to Cloudinary, and posts to Instagram using the configured secrets.

You can also run the workflow manually from GitHub Actions and choose a specific style or optional theme.

## Generate Without Rendering

This creates `horoscope_bundle.json`, `instagram_caption.txt`, and `voiceover_script.txt`.

```powershell
python .\viral_horoscope_pipeline.py --generate --style fire_do_not_chase
```

## Render an Existing Bundle

Replace `<timestamp>` with the folder created inside `generated_reels`.

```powershell
python .\viral_horoscope_pipeline.py --render --input .\generated_reels\<timestamp>\horoscope_bundle.json
```

## Add a Custom Theme

Use `--theme` to push the copy direction while keeping the same reel style.

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style fire_do_not_chase --theme "someone who only texts when they feel you pulling away"
```

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style moved_on_but_didnt --theme "checking their stories but pretending it means nothing"
```

## Use a Custom Output Folder

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style random_viral --output-root .\generated_reels
```

## Post to Instagram

Post using a public video URL:

```powershell
python .\viral_horoscope_pipeline.py --post --input .\generated_reels\<timestamp>\horoscope_bundle.json --video-url "https://your-cdn.com/reel.mp4"
```

Generate, render, and post the local rendered reel:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --post --style fire_do_not_chase
```

Post a specific local video file:

```powershell
python .\viral_horoscope_pipeline.py --post --input .\generated_reels\<timestamp>\horoscope_bundle.json --video-path .\generated_reels\<timestamp>\horoscope_reel.mp4
```

## Cleanup After Posting

Use this only when you want to delete the generated output folder after a successful post.

```powershell
python .\viral_horoscope_pipeline.py --generate --render --post --cleanup --style random_viral
```

## Useful Checks

Check Python syntax:

```powershell
python -m py_compile .\viral_horoscope_pipeline.py
```

Check Remotion TypeScript:

```powershell
.\remotion_reel\node_modules\.bin\tsc.cmd --noEmit -p .\remotion_reel\tsconfig.json
```
