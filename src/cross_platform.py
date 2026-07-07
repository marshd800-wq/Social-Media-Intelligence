"""
Cross-platform analysis: Instagram vs TikTok (the two platforms with real reach).
Produces data/processed/cross_platform.json for the brief + dashboard.
"""
import json
import os
import re
import statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")
recs = json.load(open(os.path.join(PROC, "multiplatform_dataset.json"), encoding="utf-8"))


def summary(rows):
    rows = [r for r in rows if r["reach"]]
    if not rows:
        return {}
    er = [r["engagement_rate"] for r in rows if r["engagement_rate"] is not None]
    return {
        "count": len(rows),
        "avg_reach": round(st.mean(r["reach"] for r in rows)),
        "median_reach": round(st.median(r["reach"] for r in rows)),
        "avg_views": round(st.mean(r["views"] for r in rows if r["views"])),
        "avg_interactions": round(st.mean(r["interactions"] for r in rows), 1),
        "avg_engagement_rate": round(st.mean(er), 4) if er else None,
        "avg_comments": round(st.mean(r["comments"] for r in rows), 2),
        "total_reach": sum(r["reach"] for r in rows),
    }


plat = {p: summary([r for r in recs if r["platform"] == p]) for p in ("Instagram", "TikTok")}

# by content type within each platform
fmt = {}
for p in ("Instagram", "TikTok"):
    fmt[p] = {}
    for t in ("reel", "carousel", "static"):
        g = [r for r in recs if r["platform"] == p and r["content_type"] == t]
        if g:
            fmt[p][t] = summary(g)

# TikTok top posts + hooks
tk = [r for r in recs if r["platform"] == "TikTok" and r["reach"]]
tk_top = sorted(tk, key=lambda r: r["reach"], reverse=True)[:8]
tk_hooks = [{"hook": r["hook"], "reach": r["reach"], "views": r["views"],
            "likes": r["likes"], "comments": r["comments"], "theme": r["theme"],
            "url": r["url"]} for r in tk_top]

# TikTok themes
tk_theme = {}
for th in sorted({r["theme"] for r in tk}):
    g = [r for r in tk if r["theme"] == th]
    tk_theme[th] = {"count": len(g), "avg_reach": round(st.mean(r["reach"] for r in g)),
                    "avg_er": round(st.mean(r["engagement_rate"] or 0 for r in g), 4)}
tk_theme = dict(sorted(tk_theme.items(), key=lambda kv: kv[1]["avg_reach"], reverse=True))


# match posts cross-posted to BOTH platforms (by hook fingerprint)
def fingerprint(hook):
    return re.sub(r"[^a-z0-9 ]", "", (hook or "").lower())[:40]


ig = [r for r in recs if r["platform"] == "Instagram" and r["reach"]]
ig_by_fp = {}
for r in ig:
    ig_by_fp.setdefault(fingerprint(r["hook"]), []).append(r)

matched = []
for t in tk:
    fp = fingerprint(t["hook"])
    if fp and len(fp) > 12 and fp in ig_by_fp:
        i = max(ig_by_fp[fp], key=lambda r: r["reach"])
        matched.append({
            "hook": t["hook"][:60],
            "ig_reach": i["reach"], "tk_reach": t["reach"],
            "ig_er": i["engagement_rate"], "tk_er": t["engagement_rate"],
            "winner_reach": "TikTok" if t["reach"] > i["reach"] else "Instagram",
        })
matched.sort(key=lambda m: max(m["ig_reach"], m["tk_reach"]), reverse=True)

# platforms pulled but not modeled (report honestly)
dormant = {
    "Facebook": "129 posts, median organic reach = 1 (max 11). Effectively no distribution.",
    "YouTube": "3 videos total (627 / 49 / 23 views). Channel barely used.",
    "LinkedIn": "8 posts, 16-83 impressions each, near-zero reactions.",
    "Pinterest": "Pins publishing with 0 impressions and 0 saves. Inactive.",
}

out = {
    "platform_summary": plat,
    "format_by_platform": fmt,
    "tiktok_top_hooks": tk_hooks,
    "tiktok_themes": tk_theme,
    "cross_posted_matches": matched,
    "dormant_platforms": dormant,
}
json.dump(out, open(os.path.join(PROC, "cross_platform.json"), "w"), indent=2, ensure_ascii=False)

print("=== Platform summary ===")
for p, s in plat.items():
    print(f"  {p:10} n={s['count']:3} avg_reach={s['avg_reach']:4} median={s['median_reach']:4} "
          f"avg_views={s.get('avg_views','-')} ER={s['avg_engagement_rate']} totalReach={s['total_reach']}")
print("\n=== Same content, both platforms (reach) ===")
for m in matched:
    print(f"  IG {m['ig_reach']:5} vs TK {m['tk_reach']:5}  -> {m['winner_reach']:9} | {m['hook']}")
print(f"\n  TikTok wins reach on {sum(1 for m in matched if m['winner_reach']=='TikTok')}/{len(matched)} cross-posted")
print("\n=== TikTok themes by reach ===")
for th, s in tk_theme.items():
    print(f"  {s['avg_reach']:5} reach  n={s['count']:2}  {th}")
