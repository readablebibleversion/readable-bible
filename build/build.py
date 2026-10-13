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


def ld(obj):
    """Structured data (JSON-LD) for search engines."""
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


def breadcrumbs(*items):
    """items: (name, path) pairs, starting after Home."""
    trail = [("Home", "/")] + list(items)
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": DOMAIN + path}
            for i, (name, path) in enumerate(trail)
        ],
    }


def crumb_nav(*items):
    links = ['<a href="/">Home</a>'] + [
        f'<a href="{p}">{esc(n)}</a>' if p else f'<span aria-current="page">{esc(n)}</span>' for n, p in items
    ]
    return '<nav class="crumbs" aria-label="Breadcrumb">' + ' <span aria-hidden="true">&rsaquo;</span> '.join(links) + "</nav>"


def page(title, body, desc, path, extra_head="", jsonld=None, og_type="website", noindex=False):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{'<meta name="robots" content="noindex">' if noindex else f'<link rel="canonical" href="{DOMAIN}{path}">'}
<meta name="theme-color" content="#7a3e1d">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{DOMAIN}{path}">
<meta property="og:image" content="{DOMAIN}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
{''.join(ld(x) for x in (jsonld or []))}
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
    <a href="/topics/">Topics</a>
    <a href="/search/">Search</a>
    <a href="/developers/">Developers</a>
    <a href="/about/">About</a>
    <button class="theme-toggle" type="button" aria-label="Toggle dark mode" title="Toggle dark mode">&#9680;</button>
  </nav>
</header>
{body}
<footer class="site-footer">
  <p><strong>{SITE_NAME}</strong> &middot; An open-source Bible translation &middot; {VERSION}</p>
  <p>Text licensed <a href="{LICENSE_URL}" rel="license">{LICENSE_NAME}</a>. Free to use in your apps, sites, and ministry.</p>
  <p class="footer-links"><a href="/read/">Read</a> <a href="/topics/">Topics</a> <a href="/faq/">FAQ</a> <a href="/developers/">Downloads &amp; API</a> <a href="/about/">About</a></p>
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


def verse_html(v, text, marker, verse_url):
    sup = f'<a class="fn-ref" href="#fn-{marker}" id="fr-{marker}">{marker}</a>' if marker else ""
    body = esc(text).replace("\n", "<br>") if text else '<span class="omitted">&mdash;</span>'
    num = f'<a href="{verse_url}" title="Open this verse">{v}</a>' if text else str(v)
    return f'<span class="verse" id="v{v}"><sup class="vnum">{num}</sup>{body}{sup}</span> '


def clip(text, n=155):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


TOPIC_REF_RE = re.compile(r"^(.+) (\d+):(\d+)(?:-(\d+))?$")


def load_topics(books):
    """Reads build/topics.json and resolves each reference to verses from the translation."""
    by_ref = {b["ref"]: b for b in books}
    topics = json.loads((ROOT / "build" / "topics.json").read_text(encoding="utf-8"))
    for t in topics:
        t["passages"] = []
        for ref in t["refs"]:
            m = TOPIC_REF_RE.match(ref)
            assert m and m.group(1) in by_ref, f"topic {t['slug']}: bad reference {ref}"
            b, ch, v1 = by_ref[m.group(1)], int(m.group(2)), int(m.group(3))
            v2 = int(m.group(4) or v1)
            verses = [(v, txt) for v, txt, _ in b["chapters"].get(ch, []) if v1 <= v <= v2 and txt]
            assert verses, f"topic {t['slug']}: no text for {ref}"
            t["passages"].append({"ref": ref, "book": b, "chapter": ch, "verses": verses})
    return topics


def topic_page(t, all_topics):
    items = []
    for p in t["passages"]:
        b, ch, verses = p["book"], p["chapter"], p["verses"]
        url = f"/{b['slug']}/{ch}/{verses[0][0]}/"
        text = " ".join(
            (f'<sup class="vnum">{v}</sup>' if len(verses) > 1 else "") + esc(txt).replace("\n", " ")
            for v, txt in verses
        )
        items.append(f'<li><a class="topic-ref" href="{url}">{esc(p["ref"])}</a><p>{text}</p></li>')
    others = "".join(f'<a href="/topics/{o["slug"]}/">{esc(o["name"])}</a>' for o in all_topics if o is not t)
    title = f"Bible Verses About {t['name']}"
    body = f"""<main class="topic-page narrow">
  {crumb_nav(("Topics", "/topics/"), (t['name'], None))}
  <h1>{esc(title)}</h1>
  <p class="lede-sm">{esc(t['intro'])}</p>
  <ol class="topic-list">{''.join(items)}</ol>
  <p class="verse-cite">All verses from the {SITE_NAME} ({ABBREV}), a free, open-source Bible in clear, simple English.</p>
  <h2>More topics</h2>
  <div class="chips">{others}</div>
</main>"""
    first = t["passages"][0]
    desc = clip(f"{len(t['passages'])} Bible verses about {t['name'].lower()} in clear, simple English: "
                f"{first['ref']}, \"{first['verses'][0][1]}\"")
    path = f"/topics/{t['slug']}/"
    return page(f"{title} ({ABBREV}) | {SITE_NAME}", body, desc, path, og_type="article", jsonld=[
        breadcrumbs(("Topics", "/topics/"), (t["name"], path)),
        {"@context": "https://schema.org", "@type": "ItemList", "name": title,
         "numberOfItems": len(t["passages"]),
         "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "name": p["ref"],
              "url": f"{DOMAIN}/{p['book']['slug']}/{p['chapter']}/{p['verses'][0][0]}/"}
             for i, p in enumerate(t["passages"])
         ]},
    ])


def topics_index(topics):
    cards = "".join(
        f'<a class="topic-card" href="/topics/{t["slug"]}/"><strong>{esc(t["name"])}</strong>'
        f'<span>{len(t["passages"])} verses</span></a>' for t in topics
    )
    body = f"""<main class="library">
  <div class="page-head">
    <h1>Bible Verses by Topic</h1>
    <p>Find verses about fear, anxiety, hope, love, strength, and more, in clear, simple English.</p>
  </div>
  <div class="topic-grid">{cards}</div>
</main>"""
    return page(f"Bible Verses by Topic | {SITE_NAME} ({ABBREV})", body,
                f"Bible verses about fear, anxiety, strength, love, hope, peace, healing, and more from the {SITE_NAME} ({ABBREV}).",
                "/topics/", jsonld=[breadcrumbs(("Topics", "/topics/"))])


def faq_page():
    faqs = json.loads((ROOT / "build" / "faq.json").read_text(encoding="utf-8"))
    items = "".join(f"<details class=\"faq\"><summary>{esc(f['q'])}</summary><p>{f['a']}</p></details>" for f in faqs)
    body = f"""<main class="prose narrow">
  <h1>Frequently Asked Questions</h1>
  <p>Common questions about the {SITE_NAME} ({ABBREV}).</p>
  {items}
</main>"""
    strip = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s))
    return page(f"FAQ | {SITE_NAME} ({ABBREV})", body,
                f"Answers to common questions about the {SITE_NAME} ({ABBREV}): is it free, can I use it in my app, how to cite it, and more.",
                "/faq/", jsonld=[{
                    "@context": "https://schema.org", "@type": "FAQPage",
                    "mainEntity": [{"@type": "Question", "name": f["q"],
                                    "acceptedAnswer": {"@type": "Answer", "text": strip(f["a"])}} for f in faqs],
                }])


def llms_txt(topics, books):
    lines = [
        f"# {SITE_NAME} ({ABBREV})",
        "",
        f"> The {SITE_NAME} is a free, open-source Bible translation in clear, simple English, licensed {LICENSE_NAME}. "
        f"It covers all 66 books. This is a draft translation ({VERSION}).",
        "",
        "When quoting this translation, cite the reference with the abbreviation, for example \"John 3:16 (READ)\", "
        f"and credit it as: \"{ATTRIBUTION}\"",
        "",
        "## Reading",
        f"- [Home]({DOMAIN}/): About the translation",
        f"- [All books]({DOMAIN}/read/): Index of all 66 books and chapters",
        f"- [Bible verses by topic]({DOMAIN}/topics/): Verse collections for fear, anxiety, hope, love, and more",
        f"- [FAQ]({DOMAIN}/faq/): Licensing, citation, and common questions",
        f"- [About]({DOMAIN}/about/): Purpose and approach of the translation",
        "",
        "## URL patterns",
        f"- Book: {DOMAIN}/{{book}}/ (for example {DOMAIN}/john/)",
        f"- Chapter: {DOMAIN}/{{book}}/{{chapter}}/ (for example {DOMAIN}/john/3/)",
        f"- Verse: {DOMAIN}/{{book}}/{{chapter}}/{{verse}}/ (for example {DOMAIN}/john/3/16/)",
        "- Book slugs are lowercase with dashes: " + ", ".join(b["slug"] for b in books),
        "",
        "## Data",
        f"- [Full text, plain]({DOMAIN}/llms-full.txt): The whole Bible, one verse per line",
        f"- [JSON API index]({DOMAIN}/api/index.json): Free JSON API, no key required",
        f"- [Chapter JSON example]({DOMAIN}/api/john/3.json)",
        f"- [Downloads]({DOMAIN}/developers/): JSON, CSV, USFM, and plain text",
        "",
        "## Topics",
    ] + [f"- [Bible verses about {t['name'].lower()}]({DOMAIN}/topics/{t['slug']}/)" for t in topics] + [
        "",
        "## Optional",
        f"- [Source code and translation data](https://github.com/readablebibleversion/readable-bible)",
        f"- [License]({LICENSE_URL})",
    ]
    return "\n".join(lines) + "\n"


def verse_page(book, ch, v, text, note, prev_v, next_v, topics=()):
    ref = f"{book['ref']} {ch}:{v}"
    ch_label = f"{book['ref']} {ch}"
    url = f"/{book['slug']}/{ch}/{v}/"

    def ctx(item, label):
        if not item:
            return ""
        pv, pt, ptext = item
        return (f'<a class="ctx" href="{pv}"><span class="ref">{label} &middot; {esc(pt)}</span>'
                f'<span>{esc(ptext)}</span></a>')

    note_html = f'<p class="verse-note"><strong>Note:</strong> {esc(note)}</p>' if note else ""
    body = f"""<main class="verse-page narrow">
  {crumb_nav((book['name'], f"/{book['slug']}/"), (ch_label, f"/{book['slug']}/{ch}/"), (f"Verse {v}", None))}
  <h1>{esc(ref)}</h1>
  <blockquote class="verse-big">{esc(text).replace(chr(10), '<br>')}</blockquote>
  <p class="verse-cite">{esc(ref)}, {SITE_NAME} ({ABBREV})</p>
  {note_html}
  <div class="verse-actions">
    <a class="btn primary" href="/{book['slug']}/{ch}/#v{v}">Read all of {esc(ch_label)}</a>
    <a class="btn" href="/{book['slug']}/{ch}/?comment={v}#v{v}">Comment on this verse</a>
    <button class="btn copy-verse" type="button" data-copy="{esc(text.replace(chr(10), ' '))} ({esc(ref)} {ABBREV})">Copy verse</button>
  </div>
  {('<p class="verse-topics">Found in: ' + ', '.join(f'<a href="/topics/{t["slug"]}/">Bible verses about {esc(t["name"].lower())}</a>' for t in topics) + '</p>') if topics else ''}
  <section class="context" aria-label="Surrounding verses">
    {ctx(prev_v, "Previous")}
    {ctx(next_v, "Next")}
  </section>
</main>"""
    desc = clip(f"{ref} ({ABBREV}): {text}")
    return page(f"{ref} | {SITE_NAME} ({ABBREV})", body, desc, url, og_type="article", jsonld=[
        breadcrumbs((book["name"], f"/{book['slug']}/"), (ch_label, f"/{book['slug']}/{ch}/"), (ref, url)),
    ])


def book_page(i, book, prev_b, next_b):
    n_ch = len(book["chapters"])
    first = next((t for _, t, _ in book["chapters"][1] if t), "")
    testament = "Old Testament" if i < OT_COUNT else "New Testament"
    chs = "".join(f'<a href="/{book["slug"]}/{c}/">{c}</a>' for c in sorted(book["chapters"]))
    nav = '<nav class="chapter-nav">' + (
        f'<a class="prev" href="/{prev_b["slug"]}/">&larr; {esc(prev_b["name"])}</a>' if prev_b else '<span></span>') + (
        f'<a class="next" href="/{next_b["slug"]}/">{esc(next_b["name"])} &rarr;</a>' if next_b else '<span></span>') + "</nav>"
    body = f"""<main class="book-page narrow">
  {crumb_nav((book['name'], None))}
  <h1>The Book of {esc(book['name'])}</h1>
  <p class="book-meta">{testament} &middot; {n_ch} chapter{'s' if n_ch > 1 else ''} &middot; {SITE_NAME} ({ABBREV})</p>
  <blockquote class="book-opening"><p>{esc(first)}</p><cite><a href="/{book['slug']}/1/#v1">{esc(book['ref'])} 1:1</a></cite></blockquote>
  <h2>Chapters</h2>
  <div class="ch-grid big">{chs}</div>
  <p><a class="btn primary" href="/{book['slug']}/1/">Start reading {esc(book['name'])}</a></p>
  {nav}
</main>"""
    desc = clip(f"Read the Book of {book['name']} ({n_ch} chapters) in the {SITE_NAME}, a free, open-source "
                f"Bible in clear, simple English. {first}")
    return page(f"The Book of {book['name']} | {SITE_NAME} ({ABBREV})", body, desc, f"/{book['slug']}/",
                jsonld=[breadcrumbs((book["name"], f"/{book['slug']}/"))])


def chapter_page(book, ch, prev_link, next_link):
    verses = book["chapters"][ch]
    notes = []
    parts = []
    for v, text, note in verses:
        marker = ""
        if note:
            marker = chr(ord("a") + len(notes) % 26) + ("" if len(notes) < 26 else str(len(notes) // 26))
            notes.append((marker, v, note))
        parts.append(verse_html(v, text, marker, f"/{book['slug']}/{ch}/{v}/"))
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
    # Titles use the common search form ("Psalm 23", "John 3").
    title_ch = f"{book['ref']} {ch}" if n_ch > 1 else book["name"]
    first = next((t for _, t, _ in verses if t), "")
    desc = clip(f"Read {title_ch} in the {SITE_NAME} ({ABBREV}), a free, open-source Bible in clear, simple English. {first}")
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
    <h1><a class="book-name" href="/{book['slug']}/">{esc(book['name'])}</a>{f'<span class="ch-num">Chapter {ch}</span>' if n_ch > 1 else ''}</h1>
    <p class="comment-hint">Tap any verse to comment or suggest a better wording.</p>
    <p class="text{' poetry' if poetic else ''}">{''.join(parts)}</p>
    {fn}
  </article>
  {nav}
</main>"""
    path = f"/{book['slug']}/{ch}/"
    return page(f"{title_ch} | {SITE_NAME} ({ABBREV})", body, desc, path, og_type="article", jsonld=[
        breadcrumbs((book["name"], f"/{book['slug']}/"), (title_ch, path)),
    ])


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

    # Book overview pages (/john/).
    for i, b in enumerate(books):
        write(f"{b['slug']}/index.html", book_page(i, b, books[i - 1] if i else None, books[i + 1] if i + 1 < len(books) else None))

    # A page for every verse (/john/3/16/): what people search for most.
    all_verses = [(b, ch, v, t, n) for b, ch in flat for v, t, n in b["chapters"][ch] if t]
    def neighbour(k):
        if 0 <= k < len(all_verses):
            ob, oc, ov, ot, _ = all_verses[k]
            return (f"/{ob['slug']}/{oc}/{ov}/", f"{ob['ref']} {oc}:{ov}", clip(ot, 160))
        return None
    # Topic collections (/topics/fear/), linked from the verse pages they include.
    topics = load_topics(books)
    verse_topics = {}
    for t in topics:
        write(f"topics/{t['slug']}/index.html", topic_page(t, topics))
        for p in t["passages"]:
            for v, _ in p["verses"]:
                verse_topics.setdefault((p["book"]["slug"], p["chapter"], v), []).append(t)
    write("topics/index.html", topics_index(topics))
    write("faq/index.html", faq_page())

    for k, (b, ch, v, t, n) in enumerate(all_verses):
        write(f"{b['slug']}/{ch}/{v}/index.html",
              verse_page(b, ch, v, t, n, neighbour(k - 1), neighbour(k + 1), verse_topics.get((b["slug"], ch, v), ())))

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
    write("read/index.html", page(f"Read the Bible Online | {SITE_NAME} ({ABBREV})", read_body,
          f"Read all 66 books of the {SITE_NAME} ({ABBREV}) online free: Old Testament and New Testament "
          f"in clear, simple English.", "/read/", jsonld=[breadcrumbs(("Read", "/read/"))]))

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
                .replace("{{CHAPTERS}}", f"{len(flat):,}")
                .replace("{{TOPICS}}", "".join(f'<a href="/topics/{t["slug"]}/">{esc(t["name"])}</a>' for t in topics)))
    write("index.html", page(f"{SITE_NAME} ({ABBREV}) | A free, open-source Bible in clear English", home,
          f"The {SITE_NAME} ({ABBREV}) is a free, open-source Bible translation written in clear, simple English. "
          f"Read all 66 books online, search every verse, and use it free in your apps.", "/", jsonld=[
              {
                  "@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME,
                  "alternateName": [ABBREV, "Readable Bible", "readable.bible"], "url": DOMAIN + "/",
                  "potentialAction": {
                      "@type": "SearchAction",
                      "target": {"@type": "EntryPoint", "urlTemplate": DOMAIN + "/search/?q={search_term_string}"},
                      "query-input": "required name=search_term_string",
                  },
              },
              {
                  "@context": "https://schema.org", "@type": "Book", "name": SITE_NAME, "alternateName": ABBREV,
                  "url": DOMAIN + "/", "inLanguage": "en", "genre": "Bible translation",
                  "isAccessibleForFree": True, "license": LICENSE_URL, "version": VERSION,
                  "description": "A free, open-source Bible translation in clear, simple English.",
              },
          ]))

    sizes = build_open_data(books, flat)

    for name in ("about", "search", "developers"):
        body = (ROOT / "build" / "templates" / f"{name}.html").read_text(encoding="utf-8")
        body = (body.replace("{{LICENSE_NAME}}", LICENSE_NAME).replace("{{LICENSE_URL}}", LICENSE_URL)
                    .replace("{{ATTRIBUTION}}", esc(ATTRIBUTION)).replace("{{VERSION}}", VERSION)
                    .replace("{{ABBREV}}", ABBREV))
        for key, size in sizes.items():
            body = body.replace("{{SIZE:" + key + "}}", size)
        title = {"about": "About", "search": "Search", "developers": "Downloads & API"}[name]
        descs = {
            "about": f"About the {SITE_NAME} ({ABBREV}): an open-source Bible translation in clear, simple English, free for anyone to read and share.",
            "search": f"Search every verse of the {SITE_NAME} ({ABBREV}) by word, phrase, or reference.",
            "developers": f"Free downloads (JSON, CSV, USFM, text) and a free JSON API for the {SITE_NAME} ({ABBREV}), licensed {LICENSE_NAME}.",
        }
        write(f"{name}/index.html", page(f"{title} | {SITE_NAME}", body, descs[name], f"/{name}/"))

    write("404.html", page(f"Page not found | {SITE_NAME}",
          '<main class="page-head narrow"><h1>Page not found</h1><p>That page doesn&rsquo;t exist. '
          '<a href="/read/">Browse all books</a> or <a href="/search/">search the Bible</a>.</p></main>',
          "Page not found", "/404.html", noindex=True))

    write("llms.txt", llms_txt(topics, books))
    shutil.copy(SITE / "downloads" / "readable-english-bible.txt", SITE / "llms-full.txt")

    urls = (["/", "/read/", "/search/", "/about/", "/developers/", "/faq/", "/topics/"]
            + [f"/topics/{t['slug']}/" for t in topics]
            + [f"/{b['slug']}/" for b in books]
            + [f"/{b['slug']}/{c}/" for b, c in flat]
            + [f"/{b['slug']}/{c}/{v}/" for b, c, v, _, _ in all_verses])
    assert len(urls) <= 50000, "split the sitemap: over 50,000 URLs"
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{DOMAIN}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n")

    print(f"Built {len(books)} books, {len(flat)} chapters, {total} verses -> {SITE}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "translation.xlsx")
