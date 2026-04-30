# Remotion Reel

This folder renders the bundle produced by `viral_horoscope_pipeline.py` into a 1080x1920 Instagram reel.

Current timing:
- Intro: 3 seconds
- Each sign: 4 seconds
- Outro: 3 seconds
- Total for 12 signs: about 54 seconds

Typical flow:

```powershell
python .\viral_horoscope_pipeline.py --generate
npm.cmd install --prefix .\remotion_reel
python .\viral_horoscope_pipeline.py --render --input .\generated_reels\<timestamp>\horoscope_bundle.json
```

Or do both once dependencies are installed:

```powershell
python .\viral_horoscope_pipeline.py --generate --render
```

Focused viral reel styles:

```powershell
python .\viral_horoscope_pipeline.py --generate --render --style daily
python .\viral_horoscope_pipeline.py --generate --render --style random_daily
python .\viral_horoscope_pipeline.py --generate --render --style daily_transit
python .\viral_horoscope_pipeline.py --generate --render --style love_attachment
python .\viral_horoscope_pipeline.py --generate --render --style shadow_callout
python .\viral_horoscope_pipeline.py --generate --render --style compatibility_drama
python .\viral_horoscope_pipeline.py --generate --render --style money_power
python .\viral_horoscope_pipeline.py --generate --render --style weekend_tension
python .\viral_horoscope_pipeline.py --generate --render --style moon_sign_mood
python .\viral_horoscope_pipeline.py --generate --render --style placement_based
python .\viral_horoscope_pipeline.py --generate --render --style fixed_self_respect
python .\viral_horoscope_pipeline.py --generate --render --style fire_do_not_chase
python .\viral_horoscope_pipeline.py --generate --render --style moved_on_but_didnt
python .\viral_horoscope_pipeline.py --generate --render --style moon_scorpio_exposure
python .\viral_horoscope_pipeline.py --generate --render --style random_viral
```

`daily` is the scheduled automation mode. It rotates content pillars by date so the account does not post the same kind of reel every day.

To see the available styles:

```powershell
python .\viral_horoscope_pipeline.py --list-styles
```

GitHub Actions:

- Workflow: `.github/workflows/daily-horoscope-reel.yml`
- Schedule: `04:25 UTC` every day, which is `09:55 AM Asia/Kolkata`
- Required secrets: `GROQ_API_KEY`, `META_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`
- Optional secret: `META_GRAPH_API_VERSION` (defaults to `v19.0`)
