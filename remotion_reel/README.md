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

GitHub Actions:

- Workflow: `.github/workflows/daily-horoscope-reel.yml`
- Schedule: `04:25 UTC` every day, which is `09:55 AM Asia/Kolkata`
- Required secrets: `GROQ_API_KEY`, `META_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`
- Optional secret: `META_GRAPH_API_VERSION` (defaults to `v24.0`)
