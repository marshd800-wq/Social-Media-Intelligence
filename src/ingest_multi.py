"""
Multi-platform ingestion — merges Instagram (already normalized) with TikTok
into one cross-platform dataset. Reuses the Instagram theme classifier and hook
extractor so themes/hooks are directly comparable across platforms.

Facebook, YouTube, LinkedIn, and Pinterest were pulled but are NOT modeled here:
their organic distribution is negligible (Facebook median reach = 1; YouTube = 3
videos; LinkedIn = 8 posts at 16-83 impressions; Pinterest pins at 0 impressions).
Those are reported as-is in the brief rather than fit to a model on ~0 signal.

Output: data/processed/multiplatform_dataset.json
"""
import json
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")
RAW = os.path.join(ROOT, "data", "raw")

# reuse IG pipeline helpers
import importlib.util
_spec = importlib.util.spec_from_file_location("ingest", os.path.join(HERE, "ingest.py"))
_ig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ig)


def load_instagram():
    recs = json.load(open(os.path.join(PROC, "dataset.json"), encoding="utf-8"))
    for r in recs:
        r["platform"] = "Instagram"
    return recs


def load_tiktok():
    data = json.load(open(os.path.join(RAW, "tiktok_raw.json"), encoding="utf-8"))
    cols = data["cols"]
    out = []
    for row in data["rows"]:
        d = dict(zip(cols, row))
        dt = datetime.strptime(d["date"], "%Y%m%d%H%M%S")
        caption = d["caption"] or ""
        likes = int(d["likes"] or 0)
        comments = int(d["comments"] or 0)
        shares = int(d["shares"] or 0)
        reach = int(d["reach"] or 0)
        views = int(d["views"] or 0)
        interactions = likes + comments + shares            # TikTok API gives no saves
        theme, _ = _ig.classify_theme(caption)
        out.append({
            "platform": "TikTok",
            "url": d["url"],
            "date": dt.strftime("%Y-%m-%d"),
            "datetime": dt.strftime("%Y-%m-%d %H:%M"),
            "year": dt.year,
            "day_of_week": dt.strftime("%A"),
            "hour": dt.hour,
            # video -> reel-equivalent, photo -> static-equivalent (for format compare)
            "content_type": "reel" if d["type"] == "VIDEO" else "static",
            "native_type": d["type"],
            "theme": theme,
            "hook": _ig.extract_hook(caption),
            "caption": caption,
            "caption_word_count": _ig.word_count(caption),
            "hashtags": _ig.extract_hashtags(caption),
            "hashtag_count": len(_ig.extract_hashtags(caption)),
            "has_cta_comment": _ig.build_record.__globals__["re"].search(
                r"(?i:comment|dm me|dm|message|drop|text)[^\n]{0,20}?[\"'“‘]?([A-Z]{2,12})\b",
                caption) is not None,
            "likes": likes, "comments": comments, "saved": None, "shares": shares,
            "reach": reach, "views": views, "interactions": interactions,
            "engagement_rate": round(interactions / reach, 4) if reach else None,
            "comment_rate": round(comments / reach, 4) if reach else None,
            "full_watch_rate": d.get("fullwatchrate"),
            "avg_watch_time": d.get("avgwatch"),
        })
    return out


def load_youtube():
    path = os.path.join(RAW, "youtube_raw.json")
    if not os.path.exists(path):
        return []
    data = json.load(open(path, encoding="utf-8"))
    cols = data["cols"]
    out = []
    for row in data["rows"]:
        d = dict(zip(cols, row))
        dt = datetime.strptime(d["date"], "%Y%m%d%H%M%S")
        title = d["title"] or ""
        likes = int(d["likes"] or 0)
        comments = int(d["comments"] or 0)
        shares = int(d["shares"] or 0)
        views = int(d["views"] or 0)
        interactions = likes + comments + shares            # YouTube has no saves
        theme, _ = _ig.classify_theme(title)
        out.append({
            "platform": "YouTube",
            "url": d["url"],
            "date": dt.strftime("%Y-%m-%d"),
            "datetime": dt.strftime("%Y-%m-%d %H:%M"),
            "year": dt.year,
            "day_of_week": dt.strftime("%A"),
            "hour": dt.hour,
            "content_type": "reel",           # long-form video -> video bucket
            "native_type": "VIDEO",
            "theme": theme,
            "hook": title,                    # YouTube's "hook" is the title
            "caption": title,
            "caption_word_count": _ig.word_count(title),
            "hashtags": [], "hashtag_count": 0, "has_cta_comment": False,
            "likes": likes, "comments": comments, "saved": None, "shares": shares,
            # YouTube reports views, not reach — use views as the distribution metric
            "reach": views, "views": views, "interactions": interactions,
            "engagement_rate": round(interactions / views, 4) if views else None,
            "comment_rate": round(comments / views, 4) if views else None,
            "avg_watch_min": d.get("avg_view_min"),
        })
    return out


def main():
    recs = load_instagram() + load_tiktok() + load_youtube()
    recs.sort(key=lambda r: r["date"], reverse=True)
    json.dump(recs, open(os.path.join(PROC, "multiplatform_dataset.json"), "w"),
              indent=2, ensure_ascii=False)
    from collections import Counter
    print("Total records:", len(recs))
    print("By platform:", dict(Counter(r["platform"] for r in recs)))
    tk = [r for r in recs if r["platform"] == "TikTok" and r["reach"]]
    ig = [r for r in recs if r["platform"] == "Instagram" and r["reach"]]
    import statistics as s
    print(f"Instagram: n={len(ig)} avg_reach={s.mean(r['reach'] for r in ig):.0f} "
          f"avg_ER={s.mean(r['engagement_rate'] for r in ig if r['engagement_rate'] is not None):.4f}")
    print(f"TikTok:    n={len(tk)} avg_reach={s.mean(r['reach'] for r in tk):.0f} "
          f"avg_views={s.mean(r['views'] for r in tk):.0f} "
          f"avg_ER={s.mean(r['engagement_rate'] for r in tk if r['engagement_rate'] is not None):.4f}")


if __name__ == "__main__":
    main()
