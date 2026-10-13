# Readable English Bible

An open-source Bible translation in clear, simple English. Website: https://readable.bible

## How it works

- `data/translation.xlsx` is the translation (columns: Reference, Verse, Notes).
- `build/build.py` turns the spreadsheet into the website in `site/`.
- Netlify runs the build automatically every time a change is pushed to GitHub (see `netlify.toml`).

## Updating the translation

1. Replace `data/translation.xlsx` with the new version (keep the same file name and columns).
2. Commit and push. The live site updates within a minute or two.

## Previewing locally

```
pip install -r requirements.txt
python build/build.py
python -m http.server 8790 --directory site
```

Then open http://localhost:8790
