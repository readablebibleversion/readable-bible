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

## Verse comments

Readers can click any verse to post an anonymous comment and upvote others (once per browser session).
Comments are handled by `netlify/functions/feedback.mjs` and stored in Netlify Blobs.

- Spam protection: hidden honeypot field and 5 comments per visitor per 10 minutes.
- Blocked words: comments containing anything in `netlify/lib/moderation.mjs` are rejected.
- Reports: each comment has a Report button. It hides the comment for the reporter right away,
  and for everyone after 3 reports from different visitors.
- Admin: set an `ADMIN_TOKEN` environment variable in Netlify, then
  `POST /feedback {"action":"delete" or "restore","book":"john","chapter":3,"id":"<comment id>","token":"<ADMIN_TOKEN>"}`.
  `restore` un-hides a comment that was reported by mistake.

To test comments locally: `npx netlify-cli dev --dir site --functions netlify/functions --port 8888`

## Previewing locally

```
pip install -r requirements.txt
python build/build.py
python -m http.server 8790 --directory site
```

Then open http://localhost:8790
