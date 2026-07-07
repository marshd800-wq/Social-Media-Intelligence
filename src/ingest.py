"""
NOVA Social Media Intelligence Engine — Data Ingestion
=====================================================
Parses raw Metricool Instagram exports (posts + reels connectors) for
@dianatheatlrealtor into a single normalized dataset.

Source: Metricool API via MCP (brand "Diana the ATL Realtor", id 3526631),
authorized pull from Diana's own Instagram business account — not scraped.

Outputs:
    data/processed/dataset.json   full structured records
    data/processed/dataset.csv    flat table for spreadsheets
"""
import json
import re
import csv
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
os.makedirs(PROC, exist_ok=True)

# Column order matches the metric arrays requested from Metricool.
# Reels: IGRE02,03,06,07,10,11,12,21,23,24,27,28,29
REEL_COLS = ["date", "caption", "url", "comments", "likes", "reach",
             "saved", "shares", "views", "avg_watch_time", "retention",
             "view_rate", "reposts"]
# Posts: IGPO02,03,06,07,08,13,14,15,27,28,12
POST_COLS = ["date", "caption", "url", "ig_type", "comments", "likes",
             "reach", "saved", "shares", "views", "interactions"]


def _load_rows(path):
    raw = open(path, encoding="utf-8").read()
    i = raw.find("{")
    return json.loads(raw[i:])["rows"]


def _num(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 3)
    except (ValueError, TypeError):
        return None


def parse_date(s):
    # format: YYYYMMDDHHMMSS
    return datetime.strptime(s, "%Y%m%d%H%M%S")


# ---- Theme classification -------------------------------------------------
# Ordered: first matching theme with the highest keyword score wins.
THEME_KEYWORDS = {
    "Find Home Anywhere (global series)": [
        "findhomeanywhere", "here or there", "canada", "bahamas", "cayman",
        "uae", "dubai", "italy", "portugal", "spain", "mexico", "aruba",
        "uk ", "island", "paradise", "global agent", "yourglobalagent",
        "tuscan", "abroad",
    ],
    "Seller / move-up equity": [
        "sell", "selling", "seller", "listing", "list your", "equity",
        "your net", "home value", "zestimate", "move up", "move-up",
        "moved up", "been in your home", "next chapter", "outgrew",
        "downsize", "staging", "stage", "market-ready", "list it",
    ],
    "Buyer / first-time / financing": [
        "buyer", "buying", "buy a home", "pre-approved", "preapproved",
        "pre-approval", "first-time", "first time", "down payment",
        "mortgage", "interest rate", "lower interest", "qualify",
        "seller credits", "down payment assistance", "lender", "203k",
        "homebuying", "home buying", "afford", "rent",
    ],
    "Listing / deal of the day / home tour": [
        "deal of the day", "beds", "baths", "sqft", "sq ft", "square feet",
        "open house", "new construction", "coming soon", "modern farmhouse",
        "pop-up alert", "just listed", "home tour", "primary suite",
        "kitchenette", "corner lot",
    ],
    "Relocation to Atlanta": [
        "relocate", "relocating", "moving to atlanta", "job offer",
        "new city", "make atlanta home", "relocation", "from another market",
        "barely visited",
    ],
    "Market stats / education": [
        "market", "rates", "stats", "appreciation", "trends", "myth",
        "tax", "interest rate", "data", "numbers", "% off", "neighborhoods",
        "equity growth", "inspection", "remodeling", "renovation",
    ],
    "Lifestyle / seasonal / home tips": [
        "thanksgiving", "turkey", "hosting", "host", "coffee table",
        "styling", "style your", "winter", "cozy", "holiday", "decor",
        "recipe", "guests", "harsh weather", "spiced", "fall ", "season",
        "home ready", "warm you up", "treat",
    ],
    "Personal / behind the scenes": [
        "i love", "my mom", "my job", "love my job", "behind the scenes",
        "pov", "describe your job", "closing day", "cold call",
        "why i", "fills my cup", "melted my heart", "adopt a teacher",
        "mindset", "mental health", "personal", "shocked", "my name",
        "two things", "always have my focus", "sharpening my skills",
        "trust the process", "growth happens", "grateful",
    ],
    "Humor / relatable": [
        "illegal", "sound illegal", "piggy bank", "y'all think",
        "lunchmoney", "humor", "did you know", "opens piggy bank",
    ],
}


def classify_theme(caption):
    low = caption.lower()
    scores = {}
    for theme, kws in THEME_KEYWORDS.items():
        scores[theme] = sum(1 for kw in kws if kw in low)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "Uncategorized", scores
    return best, scores


def extract_hook(caption):
    """First line of the caption, trimmed. This is the scroll-stopping opener."""
    if not caption:
        return ""
    first = caption.strip().split("\n")[0].strip()
    # if first line is very short (emoji-only), append second line
    if len(first) < 8:
        lines = [l.strip() for l in caption.strip().split("\n") if l.strip()]
        if len(lines) > 1:
            first = (first + " " + lines[1]).strip()
    return first[:200]


def extract_hashtags(caption):
    return re.findall(r"#(\w+)", caption or "")


def word_count(caption):
    return len((caption or "").split())


def build_record(cols, row, content_type):
    d = dict(zip(cols, row))
    caption = d.get("caption") or ""
    likes = _num(d.get("likes")) or 0
    comments = _num(d.get("comments")) or 0
    saved = _num(d.get("saved")) or 0
    shares = _num(d.get("shares")) or 0
    reach = _num(d.get("reach")) or 0
    views = _num(d.get("views")) or 0
    interactions = likes + comments + saved + shares
    dt = parse_date(d["date"])
    theme, _ = classify_theme(caption)

    rec = {
        "url": d.get("url"),
        "date": dt.strftime("%Y-%m-%d"),
        "datetime": dt.strftime("%Y-%m-%d %H:%M"),
        "year": dt.year,
        "day_of_week": dt.strftime("%A"),
        "hour": dt.hour,
        "content_type": content_type,          # reel | carousel | static
        "theme": theme,
        "hook": extract_hook(caption),
        "caption": caption,
        "caption_word_count": word_count(caption),
        "hashtags": extract_hashtags(caption),
        "hashtag_count": len(extract_hashtags(caption)),
        # DM/comment-to-action CTA: "Comment NEXT", "DM me BUY", "comment 'DEAL'".
        # Trigger word is case-insensitive; the keyword token must be genuinely
        # UPPERCASE so "comment below" does not count as a lead-gen CTA.
        "has_cta_comment": bool(re.search(
            r"(?i:comment|dm me|dm|message)[^\n]{0,20}?[\"'“‘]?([A-Z]{2,12})\b",
            caption)),
        "likes": likes,
        "comments": comments,
        "saved": saved,
        "shares": shares,
        "reach": reach,
        "views": views,
        "interactions": interactions,
        # engagement rate normalizes resonance against how many were reached
        "engagement_rate": round(interactions / reach, 4) if reach else None,
        "save_rate": round(saved / reach, 4) if reach else None,
        "comment_rate": round(comments / reach, 4) if reach else None,
    }
    if content_type == "reel":
        rec["avg_watch_time"] = _num(d.get("avg_watch_time"))
        rec["view_rate"] = _num(d.get("view_rate"))
        rec["reposts"] = _num(d.get("reposts"))
    return rec


def main():
    posts = _load_rows(os.path.join(RAW, "ig_posts_raw.txt"))
    reels = _load_rows(os.path.join(RAW, "ig_reels_raw.txt"))

    records = []
    for row in reels:
        records.append(build_record(REEL_COLS, row, "reel"))
    for row in posts:
        d = dict(zip(POST_COLS, row))
        ctype = "carousel" if d["ig_type"] == "FEED_CAROUSEL_ALBUM" else "static"
        records.append(build_record(POST_COLS, row, ctype))

    # de-dupe by url (safety), keep the richer record
    seen = {}
    for r in records:
        seen[r["url"]] = r
    records = sorted(seen.values(), key=lambda r: r["date"], reverse=True)

    with open(os.path.join(PROC, "dataset.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # flat CSV
    flat_cols = ["date", "content_type", "theme", "day_of_week", "hour",
                 "hook", "likes", "comments", "saved", "shares", "reach",
                 "views", "interactions", "engagement_rate", "hashtag_count",
                 "caption_word_count", "url"]
    with open(os.path.join(PROC, "dataset.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=flat_cols, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)

    print(f"Ingested {len(records)} records")
    from collections import Counter
    print("By type:", dict(Counter(r["content_type"] for r in records)))
    print("By theme:", dict(Counter(r["theme"] for r in records)))
    with_reach = [r for r in records if r["reach"]]
    print(f"Records with reach>0: {len(with_reach)} / {len(records)}")


if __name__ == "__main__":
    main()
