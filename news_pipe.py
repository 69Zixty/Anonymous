#!/usr/bin/env python3
import os, json, time, hashlib
from datetime import datetime, timezone
import requests, feedparser

# ---- CONFIG ----
# Feeds you want to post (name, url)
FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),  # official
    ("Nasdaq - Cryptocurrencies", "https://www.nasdaq.com/feed/rssoutbound?category=Cryptocurrencies"),
    ("CryptoNews", "https://cryptonews.com/news/feed/"),
    ("Coinpedia", "https://coinpedia.org/feed/"),
    ("Real-time Headlines", "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"),
    ("Market Pulse", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("Nasdaq - Stocks", "https://www.nasdaq.com/feed/rssoutbound?category=Stocks"),
    ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
    ("Yahoo! Finance", "https://finance.yahoo.com/news/rss"),
    ("Investing", "https://www.investing.com/rss/news.rss"),
    
]

# Optional: only post if the title contains any of these keywords (case-insensitive).
# Leave empty [] to post everything.
KEYWORDS = []  # e.g., ["ETF", "SEC", "Bitcoin", "Solana"]

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
STATE_FILE = "state.json"
POST_DELAY_SECONDS = 0.6   # be gentle to Discord if multiple posts

# ---- UTIL ----
def uid_for(entry):
    # Prefer GUID/id, else link, else hash of title+published
    if "id" in entry and entry.id:
        base = entry.id
    elif "link" in entry and entry.link:
        base = entry.link
    else:
        base = (entry.get("title") or "") + (entry.get("published") or "") + (entry.get("updated") or "")
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()

def matches_keywords(title):
    if not KEYWORDS: return True
    t = (title or "").lower()
    return any(k.lower() in t for k in KEYWORDS)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen": {}}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)

def post_to_discord(title, url, source):
    content = f"**{title}**\n{url}\n_(via {source})_"
    r = requests.post(DISCORD_WEBHOOK, json={"content": content}, timeout=20)
    r.raise_for_status()

def process_feed(name, url, state):
    parsed = feedparser.parse(url)
    if parsed.bozo and not parsed.entries:
        print(f"[WARN] Failed to parse {name} at {url}: {parsed.bozo_exception}")
        return 0
    seen = state["seen"].setdefault(url, [])
    new_count = 0
    # iterate newest first
    for entry in reversed(parsed.entries):
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        if not matches_keywords(title):
            continue
        uid = uid_for(entry)
        if uid in seen:  # already posted
            continue
        # Post
        post_to_discord(title, link, name)
        seen.append(uid)
        # keep last 500 ids per feed to avoid unbounded growth
        if len(seen) > 500:
            del seen[: len(seen) - 500]
        new_count += 1
        time.sleep(POST_DELAY_SECONDS)
    return new_count

def main():
    assert DISCORD_WEBHOOK, "Missing DISCORD_WEBHOOK_URL env var"
    state = load_state()
    totals = 0
    for (name, url) in FEEDS:
        try:
            totals += process_feed(name, url, state)
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
    save_state(state)
    print(f"Done. Posted {totals} new items at {datetime.now(timezone.utc).isoformat()}.")

if __name__ == "__main__":
    main()
