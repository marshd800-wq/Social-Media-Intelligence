"""
Compute per-platform baselines for the platform-aware scoring model.

For each platform we score every post on a within-platform 0-100 performance
blend (so Instagram and TikTok are each judged against their OWN distribution),
then aggregate to content-type and theme baselines. The scorer reads these so a
TikTok draft is judged by TikTok norms and an Instagram draft by Instagram norms.

Output: data/processed/platform_baselines.json
"""
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")
recs = json.load(open(os.path.join(PROC, "multiplatform_dataset.json"), encoding="utf-8"))


def pct_ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    n = len(vals)
    r = {}
    for rank, idx in enumerate(order):
        r[idx] = 100.0 * rank / (n - 1) if n > 1 else 50.0
    return r


def score_platform(rows):
    rows = [r for r in rows if r["reach"]]
    reach = [r["reach"] for r in rows]
    er = [r["engagement_rate"] or 0 for r in rows]
    viral = [((r["comments"] + r["shares"] + (r["saved"] or 0)) / r["reach"]) for r in rows]
    pr_reach, pr_er, pr_v = pct_ranks(reach), pct_ranks(er), pct_ranks(viral)
    for i, r in enumerate(rows):
        r["_perf"] = round(0.5 * pr_reach[i] + 0.3 * pr_er[i] + 0.2 * pr_v[i], 1)
    return rows


def agg(rows, key):
    groups = {}
    for r in rows:
        groups.setdefault(r[key], []).append(r["_perf"])
    return {k: round(st.mean(v), 1) for k, v in groups.items()}


out = {}
for p in ("Instagram", "TikTok"):
    rows = score_platform([r for r in recs if r["platform"] == p])
    out[p] = {
        "n": len(rows),
        "avg_reach": round(st.mean(r["reach"] for r in rows)),
        "avg_caption_words": round(st.mean(r["caption_word_count"] for r in rows)),
        "avg_hashtags": round(st.mean(r["hashtag_count"] for r in rows), 1),
        "type_perf": agg(rows, "content_type"),
        "theme_perf": agg(rows, "theme"),
    }

json.dump(out, open(os.path.join(PROC, "platform_baselines.json"), "w"), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2))
