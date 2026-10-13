// Anonymous verse comments and upvotes, stored in Netlify Blobs.
//
//   GET  /feedback?book=john&chapter=3                       -> { comments: [...] }
//   POST /feedback { action: "comment", book, chapter, verse, text }
//   POST /feedback { action: "vote", book, chapter, id, session }
//   POST /feedback { action: "report", book, chapter, id }          (hidden after REPORT_LIMIT reports)
//   POST /feedback { action: "delete", book, chapter, id, token }   (token = ADMIN_TOKEN env var)
//   POST /feedback { action: "restore", book, chapter, id, token }  (un-hide a reported comment)
import { getStore } from "@netlify/blobs";
import { createHash, randomUUID } from "node:crypto";
import { isAllowed } from "../lib/moderation.mjs";

const MAX_TEXT = 1000;
const RATE_LIMIT = 5; // comments per IP per window
const RATE_WINDOW_MS = 10 * 60 * 1000;
const REPORT_LIMIT = 3; // reports from different visitors before a comment is hidden
const SLUG_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

const stores = () => ({
  comments: getStore({ name: "comments", consistency: "strong" }),
  votes: getStore({ name: "votes", consistency: "strong" }),
  reports: getStore({ name: "reports", consistency: "strong" }),
  rate: getStore({ name: "rate-limits", consistency: "strong" }),
});

function validPlace(book, chapter, verse) {
  return (
    typeof book === "string" && SLUG_RE.test(book) && book.length <= 40 &&
    Number.isInteger(chapter) && chapter >= 1 && chapter <= 150 &&
    (verse === undefined || (Number.isInteger(verse) && verse >= 1 && verse <= 200))
  );
}

const validId = (id) => typeof id === "string" && /^[0-9a-f-]{36}$/.test(id);
const hashIp = (ip) => createHash("sha256").update(`readable-bible:${ip || "unknown"}`).digest("hex").slice(0, 32);

async function listComments(s, book, chapter) {
  const { blobs } = await s.comments.list({ prefix: `${book}/${chapter}/` });
  const items = await Promise.all(blobs.map((b) => s.comments.get(b.key, { type: "json" })));
  // Re-check on read, so comments posted before a word was added to the list get hidden too.
  return items.filter((c) => c && !c.hidden && isAllowed(c.text)).map(({ id, verse, text, votes, created }) => ({ id, verse, text, votes, created }));
}

async function allowComment(s, ip) {
  const key = hashIp(ip);
  const now = Date.now();
  const recent = ((await s.rate.get(key, { type: "json" })) || []).filter((t) => now - t < RATE_WINDOW_MS);
  if (recent.length >= RATE_LIMIT) return false;
  recent.push(now);
  await s.rate.setJSON(key, recent);
  return true;
}

export default async (req, context) => {
  const s = stores();

  if (req.method === "GET") {
    const url = new URL(req.url);
    const book = url.searchParams.get("book");
    const chapter = Number(url.searchParams.get("chapter"));
    if (!validPlace(book, chapter)) return json({ error: "Invalid book or chapter." }, 400);
    return json({ comments: await listComments(s, book, chapter) });
  }

  if (req.method !== "POST") return json({ error: "Method not allowed." }, 405);

  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid request." }, 400);
  }
  const { action, book, chapter } = body;

  if (action === "comment") {
    const verse = body.verse;
    const text = typeof body.text === "string" ? body.text.trim().replace(/\r\n?/g, "\n") : "";
    if (body.website) return json({ ok: true }); // honeypot field filled in: silently drop bots
    if (!validPlace(book, chapter, verse)) return json({ error: "Invalid verse." }, 400);
    if (text.length < 2 || text.length > MAX_TEXT) return json({ error: `Comments must be 2 to ${MAX_TEXT} characters.` }, 400);
    if (!isAllowed(text)) {
      return json({ error: "Your comment wasn't posted because it contains language that isn't allowed here. Please keep comments respectful and about the verse." }, 422);
    }
    if (!(await allowComment(s, context.ip))) return json({ error: "You're posting too fast. Please wait a few minutes." }, 429);
    const comment = { id: randomUUID(), book, chapter, verse, text, votes: 0, created: new Date().toISOString() };
    await s.comments.setJSON(`${book}/${chapter}/${comment.id}`, comment);
    const { id, votes, created } = comment;
    return json({ comment: { id, verse, text, votes, created } }, 201);
  }

  if (action === "vote") {
    const { id, session } = body;
    if (!validPlace(book, chapter) || !validId(id) || typeof session !== "string" || !/^[0-9a-f-]{36}$/.test(session)) {
      return json({ error: "Invalid vote." }, 400);
    }
    const key = `${book}/${chapter}/${id}`;
    const comment = await s.comments.get(key, { type: "json" });
    if (!comment || comment.hidden) return json({ error: "Comment not found." }, 404);
    const voteKey = `${id}/${session}`;
    if (await s.votes.get(voteKey)) return json({ votes: comment.votes, already: true });
    await s.votes.set(voteKey, "1");
    comment.votes = (comment.votes || 0) + 1;
    await s.comments.setJSON(key, comment);
    return json({ votes: comment.votes });
  }

  if (action === "report") {
    if (!validPlace(book, chapter) || !validId(body.id)) return json({ error: "Invalid report." }, 400);
    const key = `${book}/${chapter}/${body.id}`;
    const comment = await s.comments.get(key, { type: "json" });
    if (!comment) return json({ error: "Comment not found." }, 404);
    // One report per visitor (by hashed IP), so one person can't hide a comment alone.
    const reportKey = `${body.id}/${hashIp(context.ip)}`;
    if (await s.reports.get(reportKey)) return json({ ok: true });
    await s.reports.set(reportKey, "1");
    comment.reports = (comment.reports || 0) + 1;
    if (comment.reports >= REPORT_LIMIT) comment.hidden = true;
    await s.comments.setJSON(key, comment);
    return json({ ok: true });
  }

  if (action === "delete" || action === "restore") {
    const admin = process.env.ADMIN_TOKEN;
    if (!admin || body.token !== admin) return json({ error: "Not allowed." }, 403);
    if (!validPlace(book, chapter) || !validId(body.id)) return json({ error: "Invalid comment." }, 400);
    const key = `${book}/${chapter}/${body.id}`;
    if (action === "delete") {
      await s.comments.delete(key);
    } else {
      const comment = await s.comments.get(key, { type: "json" });
      if (!comment) return json({ error: "Comment not found." }, 404);
      comment.hidden = false;
      comment.reports = 0;
      await s.comments.setJSON(key, comment);
    }
    return json({ ok: true });
  }

  return json({ error: "Unknown action." }, 400);
};

export const config = { path: "/feedback" };
