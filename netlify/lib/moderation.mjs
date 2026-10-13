// Comment moderation: any comment matching these lists is rejected before it is saved,
// and existing comments that match are hidden. Edit the lists below to change the rules.
//
// Careful: several words appear in the Bible itself (hell, Satan, devil, demon, damnation,
// 666, lame, pricks, "the cock crowed", the city of Ai), so they are NOT blocked on their
// own. Only clearly rude or satanic phrases are blocked, so people can still discuss the verses.

// Words blocked when a word STARTS with them (catches "fucking", "shitty", etc.).
const BLOCKED_PREFIXES = [
  // Cuss words
  "fuck", "fuk", "fck", "motherf", "shit", "bullshit", "bitch", "cunt", "cocksuck", "pussy",
  "asshole", "arsehole", "dumbass", "jackass", "smartass", "badass", "wank", "twat", "bollock",
  "goddam", "dammit", "damnit", "piss", "slut", "whore", "skank", "douche", "jizz", "porn",
  // Slurs and derogatory terms
  "nigg", "nigga", "faggot", "fagg", "retard", "tranny", "kike", "wetback", "chink", "gook",
  "beaner", "raghead", "towelhead", "dyke",
];

// Whole words or phrases (an optional trailing "s" is also matched).
const BLOCKED_WORDS = [
  // Cuss words
  "damn", "crap", "ass", "arse", "bastard", "dick", "tits", "boobs", "wtf", "stfu", "omfg",
  // Slurs (whole word only, so "spices" and "cocoon" are fine)
  "fag", "spic", "coon",
  // Rude / insulting
  "stupid", "idiot", "idiotic", "moron", "moronic", "dumb", "imbecile", "loser", "shut up",
  "kill yourself", "kys", "go to hell", "burn in hell", "rot in hell", "i hate you", "you suck",
  "this sucks", "sucks", "garbage", "trash", "pathetic", "clown", "joke translation",
  // Satanic
  "hail satan", "praise satan", "worship satan", "worship the devil", "devil worship",
  "satanism", "satanist", "satanists", "satanic", "church of satan", "baphomet", "hail lucifer",
  "praise lucifer", "lucifer is lord", "luciferian", "antichrist is lord", "hail the beast",
  "black mass", "necronomicon",
  // Saying it's AI
  "artificial intelligence", "chatgpt", "chat gpt", "gpt", "openai", "open ai", "llm", "llms",
  "large language model", "language model", "machine generated", "machine-generated",
  "computer generated", "computer-generated", "machine translated", "machine translation",
  "chatbot", "chat bot", "written by a bot", "a bot wrote", "bot generated", "robot wrote",
  "claude", "copilot", "gemini ai", "bard ai", "grok",
];

// Roots blocked even when spaced or dotted out ("f u c k", "f.u.c.k"). Only long,
// unambiguous roots go here, because spaces are removed before checking.
const BLOCKED_SQUASHED = ["fuck", "motherf", "nigger", "nigga", "faggot", "cunts", "retard"];

const LEET = { 0: "o", 1: "i", 3: "e", 4: "a", 5: "s", 7: "t", "@": "a", $: "s", "!": "i" };

// "AI" as its own word in capitals or lowercase ("AI", "ai", "A.I."), but not "Ai",
// the city in Joshua 7-8.
const AI_RE = /(^|[^A-Za-z])(AI|ai|A\.I\.?|a\.i\.?)(?![A-Za-z])/;

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const phrase = (w) => w.split(/[\s-]+/).map(esc).join("[\\s\\-_.]*");
const PREFIX_RE = new RegExp(`(^|[^a-z])(${BLOCKED_PREFIXES.map(phrase).join("|")})`, "i");
const WORD_RE = new RegExp(`(^|[^a-z])(${BLOCKED_WORDS.map(phrase).join("|")})s?(?![a-z])`, "i");

function variants(text) {
  const plain = text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const leet = plain.replace(/[013457@$!]/g, (c) => LEET[c]);
  // Collapse letters repeated 3+ times ("stuuupid" -> "stupid").
  const collapse = (s) => s.replace(/([a-z])\1{2,}/g, "$1");
  return [plain, leet, collapse(plain), collapse(leet)];
}

/** Returns true if the comment may be posted. */
export function isAllowed(text) {
  if (AI_RE.test(text)) return false;
  for (const v of variants(text)) {
    if (PREFIX_RE.test(v) || WORD_RE.test(v)) return false;
    const squashed = v.replace(/[^a-z]/g, "");
    if (BLOCKED_SQUASHED.some((w) => squashed.includes(w))) return false;
  }
  return true;
}
