"""Builds the Readable English Bible static site from the translation spreadsheet.

Usage:  python build/build.py [path/to/translation.xlsx]   (default: data/translation.xlsx)
Output: the site/ folder (upload this folder to your host).
"""
import csv
import html
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
STATIC = ROOT / "build" / "static"
SITE_NAME = "Readable English Bible"
ABBREV = "READ"
DOMAIN = "https://readable.bible"
VERSION = "Draft 0.2"
LICENSE_NAME = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION = f"Scripture from the {SITE_NAME} ({ABBREV}), readable.bible, licensed under {LICENSE_NAME}."
OT_COUNT = 39
REF_RE = re.compile(r"^(.+) (\d+):(\d+)$")
USFM_CODES = (
    "GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO "
    "ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL "
    "MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB "
    "JAS 1PE 2PE 1JN 2JN 3JN JUD REV"
).split()


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def esc(s):
    return html.escape(s or "", quote=True)


def load(xlsx):
    ws = openpyxl.load_workbook(xlsx, read_only=True).worksheets[0]
    books = []  # [{name, slug, chapters: {n: [(v, text, note)]}}]
    index = {}
    for ref, text, note in list(ws.iter_rows(values_only=True))[1:]:
        m = REF_RE.match(ref or "")
        if not m:
            continue
        name, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
        if name not in index:
            # Verse references say "Psalm 23:1"; the book itself is "Psalms".
            title = "Psalms" if name == "Psalm" else name
            index[name] = {"name": title, "ref": name, "slug": slug(title), "chapters": {}}
            books.append(index[name])
        index[name]["chapters"].setdefault(ch, []).append(
            (v, (text or "").strip(), (note or "").strip())
        )
    return books


def page(title, body, desc, path, extra_head=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{DOMAIN}{path}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;1,7..72,400&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<script>try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;var f=localStorage.getItem('fontSize');if(f)document.documentElement.style.setProperty('--reader-size',f+'px')}}catch(e){{}}</script>
{extra_head}
</head>
<body>
<header class="site-header">
  <a class="brand" href="/"><img src="/assets/icon.svg" alt="" width="28" height="28"><span>{SITE_NAME}</span></a>
  <nav>
    <a href="/read/">Read</a>
    <a href="/search/">Search</a>
    <a href="/developers/">Developers</a>
    <a href="/about/">About</a>
    <button class="theme-toggle" type="button" aria-label="Toggle dark mode" title="Toggle dark mode">&#9680;</button>
  </nav>
</header>
{body}
<footer class="site-footer">
  <p><strong>{SITE_NAME}</strong> &middot; An open-source Bible translation &middot; {VERSION}</p>
  <p>Text licensed <a href="{LICENSE_URL}" rel="license">{LICENSE_NAME}</a>. Free to use in your apps, sites, and ministry. <a href="/developers/">Downloads &amp; API</a></p>
</footer>
<script src="/assets/books.js"></script>
<script src="/assets/app.js"></script>
</body>
</html>
"""


def write(rel, content):
    out = SITE / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def verse_html(v, text, marker):
    sup = f'<a class="fn-ref" href="#fn-{marker}" id="fr-{marker}">{marker}</a>' if marker else ""
    body = esc(text).replace("\n", "<br>") if text else '<span class="omitted">&mdash;</span>'
    return f'<span class="verse" id="v{v}"><sup class="vnum">{v}</sup>{body}{sup}</span> '


def chapter_page(book, ch, prev_link, next_link):
    verses = book["chapters"][ch]
    notes = []
    parts = []
    for v, text, note in verses:
        marker = ""
        if note:
            marker = chr(ord("a") + len(notes) % 26) + ("" if len(notes) < 26 else str(len(notes) // 26))
            notes.append((marker, v, note))
        parts.append(verse_html(v, text, marker))
    fn = ""
    if notes:
        items = "".join(
            f'<li id="fn-{m}"><a href="#fr-{m}" class="fn-back">{m}</a> <span class="fn-verse">{ch}:{v}</span> {esc(n)}</li>'
            for m, v, n in notes
        )
        fn = f'<section class="footnotes" aria-label="Footnotes"><h2>Notes</h2><ol>{items}</ol></section>'

    def nav_link(link, cls, text_fmt):
        if not link:
            return f'<span class="{cls} disabled"></span>'
        href, text = link
        return f'<a class="{cls}" href="{href}">{text_fmt.format(esc(text))}</a>'

    nav = f"""<nav class="chapter-nav">{nav_link(prev_link, 'prev', '&larr; {}')}{nav_link(next_link, 'next', '{} &rarr;')}</nav>"""
    # Chapters written mostly as poetry lines get one verse per block.
    poetic = sum("\n" in t for _, t, _ in verses) * 2 > len(verses)
    n_ch = len(book["chapters"])
    title_ch = f"{book['name']} {ch}" if n_ch > 1 else book["name"]
    first = verses[0][1] or (verses[1][1] if len(verses) > 1 else "")
    desc = f"{title_ch} in the {SITE_NAME}, a free, open-source translation in clear, simple English. {first[:120]}"
    body = f"""<main class="reader" data-book="{book['slug']}" data-chapter="{ch}">
  <div class="reader-bar">
    <div class="jump">
      <select class="jump-book" aria-label="Book"></select>
      <select class="jump-chapter" aria-label="Chapter"></select>
    </div>
    <div class="size-controls" aria-label="Text size">
      <button type="button" data-size="-1" aria-label="Smaller text">A&minus;</button>
      <button type="button" data-size="1" aria-label="Larger text">A+</button>
    </div>
  </div>
  <article class="chapter">
    <h1><span class="book-name">{esc(book['name'])}</span>{f'<span class="ch-num">Chapter {ch}</span>' if n_ch > 1 else ''}</h1>
    <p class="text{' poetry' if poetic else ''}">{''.join(parts)}</p>
    {fn}
  </article>
  {nav}
</main>"""
    return page(f"{title_ch} | {SITE_NAME}", body, desc, f"/{book['slug']}/{ch}/")


def build_open_data(books, flat):
    """Writes the free downloads (/downloads/) and the static JSON API (/api/). Returns file sizes."""
    assert len(books) == len(USFM_CODES), "expected 66 books in canonical order"
    meta = {
        "name": SITE_NAME,
        "abbreviation": ABBREV,
        "id": "readable",
        "language": "en",
        "version": VERSION,
        "license": LICENSE_NAME,
        "license_url": LICENSE_URL,
        "attribution": ATTRIBUTION,
        "website": DOMAIN,
    }

    def verse_obj(v, text, note):
        obj = {"verse": v, "text": text}
        if note:
            obj["note"] = note
        return obj

    def book_info(i, b):
        return {
            "name": b["name"], "slug": b["slug"], "usfm": USFM_CODES[i],
            "testament": "OT" if i < OT_COUNT else "NT", "chapters": len(b["chapters"]),
        }

    # Full Bible as one JSON file.
    full = dict(meta, books=[
        dict(book_info(i, b), chapters=[
            {"chapter": ch, "verses": [verse_obj(*v) for v in b["chapters"][ch]]}
            for ch in sorted(b["chapters"])
        ]) for i, b in enumerate(books)
    ])
    write("downloads/readable-english-bible.json", json.dumps(full, ensure_ascii=False, separators=(",", ":")))

    # CSV and plain text: one verse per row/line.
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["book", "usfm", "chapter", "verse", "text", "note"])
    lines = [f"{SITE_NAME} ({VERSION}). {ATTRIBUTION}", ""]
    for i, b in enumerate(books):
        for ch in sorted(b["chapters"]):
            for v, text, note in b["chapters"][ch]:
                w.writerow([b["name"], USFM_CODES[i], ch, v, text, note])
                if text:
                    lines.append(f"{b['ref']} {ch}:{v}\t{text.replace(chr(10), ' ')}")
    write("downloads/readable-english-bible.csv", buf.getvalue())
    write("downloads/readable-english-bible.txt", "\n".join(lines) + "\n")

    # USFM: one file per book, zipped.
    usfm_zip = SITE / "downloads" / "readable-english-bible-usfm.zip"
    with zipfile.ZipFile(usfm_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for i, b in enumerate(books):
            code = USFM_CODES[i]
            out = [f"\\id {code} {SITE_NAME} ({ABBREV}, {VERSION}) - {LICENSE_NAME}", "\\usfm 3.0", "\\ide UTF-8",
                   f"\\h {b['name']}", f"\\toc1 {b['name']}", f"\\toc2 {b['name']}", f"\\toc3 {code.title()}",
                   f"\\mt1 {b['name']}"]
            for ch in sorted(b["chapters"]):
                out += [f"\\c {ch}", "\\p"]
                for v, text, note in b["chapters"][ch]:
                    fn = f" \\f + \\fr {ch}:{v} \\ft {note}\\f*" if note else ""
                    parts = text.split("\n") if text else [""]
                    if len(parts) > 1:
                        out.append(f"\\q1 \\v {v} {parts[0]}")
                        out += [f"\\q1 {p}" for p in parts[1:]]
                        out[-1] += fn
                    else:
                        out.append(f"\\v {v} {parts[0]}{fn}".rstrip())
            z.writestr(f"{i + 1:02d}-{code}.usfm", "\n".join(out) + "\n")
        z.writestr("LICENSE.txt", f"{ATTRIBUTION}\n{LICENSE_URL}\n")

    # Static JSON API.
    infos = [book_info(i, b) for i, b in enumerate(books)]
    write("api/index.json", json.dumps(dict(meta, endpoints={
        "books": f"{DOMAIN}/api/books.json",
        "book": f"{DOMAIN}/api/{{book}}.json",
        "chapter": f"{DOMAIN}/api/{{book}}/{{chapter}}.json",
    }), indent=2))
    write("api/books.json", json.dumps(dict(meta, books=[
        dict(info, url=f"{DOMAIN}/api/{info['slug']}.json") for info in infos
    ]), ensure_ascii=False, indent=1))
    for i, b in enumerate(books):
        write(f"api/{b['slug']}.json", json.dumps(dict(meta, book=full["books"][i]), ensure_ascii=False, separators=(",", ":")))
    for j, (b, ch) in enumerate(flat):
        i = books.index(b)
        def ref(k):
            if 0 <= k < len(flat):
                ob, oc = flat[k]
                return {"book": ob["slug"], "chapter": oc, "url": f"{DOMAIN}/api/{ob['slug']}/{oc}.json"}
            return None
        write(f"api/{b['slug']}/{ch}.json", json.dumps(dict(
            meta, book=infos[i], chapter=ch,
            verses=[verse_obj(*v) for v in b["chapters"][ch]],
            previous=ref(j - 1), next=ref(j + 1),
        ), ensure_ascii=False, separators=(",", ":")))

    def size(path):
        n = (SITE / path).stat().st_size
        return f"{n / 1_000_000:.1f} MB" if n >= 1_000_000 else f"{n // 1000} KB"
    return {
        "json": size("downloads/readable-english-bible.json"),
        "csv": size("downloads/readable-english-bible.csv"),
        "txt": size("downloads/readable-english-bible.txt"),
        "usfm": size("downloads/readable-english-bible-usfm.zip"),
    }


def build(xlsx):
    books = load(xlsx)
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(STATIC, SITE)

    # Book index used by the chapter jump menus and search.
    meta = [[b["name"], b["slug"], len(b["chapters"])] for b in books]
    write("assets/books.js", "window.BOOKS=" + json.dumps(meta, separators=(",", ":")) + ";\n")

    # Chapter pages.
    flat = [(b, ch) for b in books for ch in sorted(b["chapters"])]
    for i, (b, ch) in enumerate(flat):
        def link(j):
            if 0 <= j < len(flat):
                ob, oc = flat[j]
                label = f"{ob['name']} {oc}" if len(ob["chapters"]) > 1 else ob["name"]
                return (f"/{ob['slug']}/{oc}/", label)
            return None
        write(f"{b['slug']}/{ch}/index.html", chapter_page(b, ch, link(i - 1), link(i + 1)))
        if ch == 1:
            # /john/ redirects to /john/1/
            write(f"{b['slug']}/index.html",
                  f'<!doctype html><meta charset="utf-8"><title>{esc(b["name"])}</title>'
                  f'<link rel="canonical" href="{DOMAIN}/{b["slug"]}/1/">'
                  f'<meta http-equiv="refresh" content="0; url=/{b["slug"]}/1/">')

    # Library ("Read") page: every book with every chapter.
    def section(label, group):
        cards = []
        for b in group:
            chs = "".join(f'<a href="/{b["slug"]}/{c}/">{c}</a>' for c in sorted(b["chapters"]))
            cards.append(
                f'<details class="book" id="{b["slug"]}"><summary><span>{esc(b["name"])}</span>'
                f'<span class="count">{len(b["chapters"])} ch</span></summary><div class="ch-grid">{chs}</div></details>'
            )
        return f'<section class="testament"><h2>{label}</h2><div class="book-list">{"".join(cards)}</div></section>'

    total = sum(len(vs) for b in books for vs in b["chapters"].values())
    read_body = f"""<main class="library">
  <div class="page-head">
    <h1>Read the Bible</h1>
    <p>All 66 books, {len(flat):,} chapters, and {total:,} verses. Choose a book, then a chapter.</p>
    <input class="filter" type="search" placeholder="Find a book&hellip;" aria-label="Find a book">
  </div>
  {section("Old Testament", books[:OT_COUNT])}
  {section("New Testament", books[OT_COUNT:])}
</main>"""
    write("read/index.html", page(f"Read | {SITE_NAME}", read_body,
          f"Read every book of the {SITE_NAME}, a free, open-source Bible translation in clear English.", "/read/"))

    # Search data: [ref, url, text]
    data = []
    for b in books:
        for ch in sorted(b["chapters"]):
            for v, text, _ in b["chapters"][ch]:
                if text:
                    data.append([f"{b['ref']} {ch}:{v}", f"/{b['slug']}/{ch}/#v{v}", text])
    write("assets/search.json", json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    # Featured verses for the home page.
    lookup = {(b["name"], ch, v): t for b in books for ch, vs in b["chapters"].items() for v, t, _ in vs}
    def verse(name, ch, v):
        return esc(lookup.get((name, ch, v), ""))

    home = (ROOT / "build" / "templates" / "home.html").read_text(encoding="utf-8")
    home = (home.replace("{{JOHN316}}", verse("John", 3, 16))
                .replace("{{PS231}}", verse("Psalms", 23, 1))
                .replace("{{GEN11}}", verse("Genesis", 1, 1))
                .replace("{{VERSES}}", f"{total:,}")
                .replace("{{CHAPTERS}}", f"{len(flat):,}"))
    write("index.html", page(f"{SITE_NAME} | A free, open-source Bible in clear English", home,
          f"The {SITE_NAME} is a free, open-source Bible translation written in clear, simple English that anyone can read.", "/"))

    sizes = build_open_data(books, flat)

    for name in ("about", "search", "developers"):
        body = (ROOT / "build" / "templates" / f"{name}.html").read_text(encoding="utf-8")
        body = (body.replace("{{LICENSE_NAME}}", LICENSE_NAME).replace("{{LICENSE_URL}}", LICENSE_URL)
                    .replace("{{ATTRIBUTION}}", esc(ATTRIBUTION)).replace("{{VERSION}}", VERSION)
                    .replace("{{ABBREV}}", ABBREV))
        for key, size in sizes.items():
            body = body.replace("{{SIZE:" + key + "}}", size)
        title = {"about": "About", "search": "Search", "developers": "Downloads & API"}[name]
        write(f"{name}/index.html", page(f"{title} | {SITE_NAME}", body,
              f"{title} - {SITE_NAME}, an open-source Bible translation.", f"/{name}/"))

    write("404.html", page(f"Page not found | {SITE_NAME}",
          '<main class="page-head narrow"><h1>Page not found</h1><p>That page doesn&rsquo;t exist. '
          '<a href="/read/">Browse all books</a> or <a href="/search/">search the Bible</a>.</p></main>',
          "Page not found", "/404.html"))

    urls = ["/", "/read/", "/search/", "/about/", "/developers/"] + [f"/{b['slug']}/{c}/" for b, c in flat]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{DOMAIN}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n")

    print(f"Built {len(books)} books, {len(flat)} chapters, {total} verses -> {SITE}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "translation.xlsx")
