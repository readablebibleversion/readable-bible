# Readable English Bible

An open-source Bible translation in clear, simple English. Website: https://readable.bible

## Use it in your app

The translation text is licensed **CC BY 4.0**: free for any use, including commercial, with credit. See [LICENSE.md](LICENSE.md).

- Downloads (JSON, CSV, USFM, plain text): https://readable.bible/developers/
- JSON API: `https://readable.bible/api/books.json`, `https://readable.bible/api/{book}.json`, `https://readable.bible/api/{book}/{chapter}.json`

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
