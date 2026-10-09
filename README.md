# Defensive Run Value Translations

Quarto article on defensive run value across the Giants system: fielding,
catcher framing and catcher throwing from Low-A to MLB.

- `article/defensive_dives.html` is the rendered article: a single
  self-contained file you can open in a browser.
- `article/defensive_dives.qmd` + `article/article_lib.py` hold the source.
  Every number in the prose is computed from the data, not typed in.
- `queries/` holds the BigQuery SQL the article runs (project `sfgiants-viewer`).

Data snapshots (`article/data/*.parquet`) are not in the repo. Pull them
fresh from BigQuery when you render.

## Rebuild

Requires [Quarto](https://quarto.org), Python 3.13 and BigQuery access.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
gcloud auth application-default login
cd article
.\render.ps1 -Refresh   # first run: pulls data from BigQuery
.\render.ps1            # later runs reuse the cached snapshots
```
