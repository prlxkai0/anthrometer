# AnthroMeter — Good Times Index (Clean Starter)

This starter renders the GTI line chart and updates the latest value daily via GitHub Actions.
It enforces a non-zero **soft floor** of **100** so the chart never touches 0.

## Files
- `index.html`, `styles.css`, `script.js` — front-end with Plotly
- `data/gti.json` — data series (1900–2025) + timestamp
- `updater.py` — daily nudge (respects soft floor)
- `.github/workflows/update.yml` — scheduled + manual workflow (with write permissions)

## Publish (GitHub Pages)
1. New repo → upload all files to repo **root** (not zipped).
2. Settings → Pages → **Deploy from a branch** → `main` → `/ (root)` → Save.
3. Settings → Actions → General → **Read and write permissions** → Save.
4. Actions tab → **Update GTI Daily** → **Run workflow**.
5. Visit `https://<username>.github.io/<repo>/`.

## Next steps
- Replace `updater.py` with the real GTI scoring pipeline.
- Add category breakdown JSONs and hover annotations.
- Tune sensitivity and floor to match your narrative goals.
