"""
NOVA Social Media Intelligence Engine — Pattern Analysis
========================================================
Consumes data/processed/dataset.json and produces:
    data/processed/analysis.json   machine-readable findings (feeds the brief)
    output/analysis_report.md      human-readable deep dive

Performance model
-----------------
Raw likes scale with how far a post was distributed, so comparing raw counts
across posts with 30x differences in reach is misleading. We rank every post
on four normalized signals and blend them into a 0-100 performance score:

    reach (distribution)                 40%   how far the algorithm pushed it
    engagement_rate = int/reach          25%   did the people reached resonate
    (saves+shares)/reach (virality)      20%   high-intent, share-driven growth
    comments/reach (conversation)        15%   DM-funnel / lead signal

Percentile ranks make the blend robust to outliers and unit differences.
"""
import json
import os
import re
import statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

records = json.load(open(os.path.join(PROC, "dataset.json"), encoding="utf-8"))
# only records with a real reach denominator can be rate-scored
scored = [r for r in records if r.get("reach")]


def pct_ranks(values):
    """Return {index: percentile 0-100} for a list of values."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = {}
    n = len(values)
    for rank, idx in enumerate(order):
        ranks[idx] = 100.0 * rank / (n - 1) if n > 1 else 100.0
    return ranks


def compute_performance():
    reach = [r["reach"] for r in scored]
    er = [r["engagement_rate"] or 0 for r in scored]
    viral = [((r["saved"] + r["shares"]) / r["reach"]) for r in scored]
    conv = [(r["comments"] / r["reach"]) for r in scored]
    pr_reach = pct_ranks(reach)
    pr_er = pct_ranks(er)
    pr_viral = pct_ranks(viral)
    pr_conv = pct_ranks(conv)
    for i, r in enumerate(scored):
        r["perf_score"] = round(
            0.40 * pr_reach[i] + 0.25 * pr_er[i]
            + 0.20 * pr_viral[i] + 0.15 * pr_conv[i], 1)


compute_performance()
scored_sorted = sorted(scored, key=lambda r: r["perf_score"], reverse=True)


def agg(group):
    """Summary stats for a list of records."""
    n = len(group)
    if n == 0:
        return {}
    def avg(key):
        vals = [g[key] for g in group if g.get(key) is not None]
        return round(statistics.mean(vals), 2) if vals else None
    def med(key):
        vals = [g[key] for g in group if g.get(key) is not None]
        return round(statistics.median(vals), 2) if vals else None
    return {
        "count": n,
        "avg_perf_score": avg("perf_score"),
        "avg_reach": avg("reach"),
        "median_reach": med("reach"),
        "avg_views": avg("views"),
        "avg_interactions": avg("interactions"),
        "avg_engagement_rate": avg("engagement_rate"),
        "avg_comments": avg("comments"),
        "avg_saved": avg("saved"),
        "avg_shares": avg("shares"),
        "avg_likes": avg("likes"),
    }


# ---- 1. Content type performance -----------------------------------------
by_type = {}
for t in ["reel", "carousel", "static"]:
    by_type[t] = agg([r for r in scored if r["content_type"] == t])

# ---- 2. Theme performance -------------------------------------------------
by_theme = {}
themes = sorted({r["theme"] for r in scored})
for th in themes:
    by_theme[th] = agg([r for r in scored if r["theme"] == th])
by_theme_ranked = dict(sorted(
    by_theme.items(),
    key=lambda kv: kv[1].get("avg_perf_score") or 0, reverse=True))

# ---- 3. Hooks -------------------------------------------------------------
def hook_table(sort_key, top=15):
    rows = sorted(scored, key=lambda r: r.get(sort_key) or 0, reverse=True)[:top]
    return [{
        "hook": r["hook"], "content_type": r["content_type"],
        "theme": r["theme"], "reach": r["reach"], "views": r["views"],
        "comments": r["comments"], "saved": r["saved"], "shares": r["shares"],
        "engagement_rate": r["engagement_rate"], "perf_score": r["perf_score"],
        "date": r["date"], "url": r["url"],
    } for r in rows]

hooks_by_perf = hook_table("perf_score")
hooks_by_views = hook_table("views")
hooks_by_comments = hook_table("comments")

# ---- 4. Phrase differentials (top vs bottom) ------------------------------
STOP = set("""a an the and or but if then this that these those to of in on for
with as is are was were be been being it its i you your my me we our they he she
his her at by from so just not no do does did have has had will would can could
me your you're what when where how why who which while about into out up down over
all any more most some such than too very s t re ve ll m d o get got let lets like
one two three new now here there their them your yours also into around off""".split())


def tokens(text):
    words = re.findall(r"[a-z][a-z'’]+", (text or "").lower())
    return [w for w in words if w not in STOP and len(w) > 2]


def bigrams(text):
    ws = tokens(text)
    return [f"{ws[i]} {ws[i+1]}" for i in range(len(ws) - 1)]


n = len(scored_sorted)
top_q = scored_sorted[: max(1, n // 4)]
bot_q = scored_sorted[-max(1, n // 4):]


def freq(group, fn):
    c = Counter()
    for r in group:
        c.update(set(fn(r["caption"])))  # set => document frequency
    return c


def differential(fn, min_top=3):
    tf = freq(top_q, fn)
    bf = freq(bot_q, fn)
    nt, nb = len(top_q), len(bot_q)
    out = []
    for term, tc in tf.items():
        if tc < min_top:
            continue
        top_share = tc / nt
        bot_share = bf.get(term, 0) / nb
        lift = top_share / bot_share if bot_share else float("inf")
        out.append({
            "term": term, "top_docs": tc, "bottom_docs": bf.get(term, 0),
            "top_share": round(top_share, 3), "bottom_share": round(bot_share, 3),
            "lift": round(lift, 2) if lift != float("inf") else "only_top",
        })
    # sort: infinite lift first, then by lift
    out.sort(key=lambda d: (d["lift"] == "only_top", d["lift"] if d["lift"] != "only_top" else 0), reverse=True)
    return out[:25]

phrase_diff_words = differential(tokens)
phrase_diff_bigrams = differential(bigrams, min_top=2)

# ---- 5. Cadence -----------------------------------------------------------
def cadence(key, order=None):
    groups = defaultdict(list)
    for r in scored:
        groups[r[key]].append(r)
    res = {k: agg(v) for k, v in groups.items()}
    if order:
        res = {k: res[k] for k in order if k in res}
    else:
        res = dict(sorted(res.items(), key=lambda kv: kv[1]["avg_perf_score"] or 0, reverse=True))
    return res

dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
by_dow = cadence("day_of_week", dow_order)

# hour buckets
def bucket_hour(h):
    if h < 6: return "00-06 overnight"
    if h < 11: return "06-11 morning"
    if h < 14: return "11-14 midday"
    if h < 17: return "14-17 afternoon"
    if h < 20: return "17-20 evening"
    return "20-24 night"
for r in scored:
    r["_hourbucket"] = bucket_hour(r["hour"])
by_hour = {k: agg([r for r in scored if r["_hourbucket"] == k])
           for k in ["06-11 morning", "11-14 midday", "14-17 afternoon",
                     "17-20 evening", "20-24 night", "00-06 overnight"]}
by_hour = {k: v for k, v in by_hour.items() if v}

# ---- 6. Top 10 / Bottom 10 commonalities ---------------------------------
def commonalities(group):
    return {
        "types": dict(Counter(r["content_type"] for r in group)),
        "themes": dict(Counter(r["theme"] for r in group)),
        "days": dict(Counter(r["day_of_week"] for r in group)),
        "avg_caption_words": round(statistics.mean(r["caption_word_count"] for r in group), 1),
        "avg_hashtags": round(statistics.mean(r["hashtag_count"] for r in group), 1),
        "pct_with_cta": round(100 * sum(1 for r in group if r["has_cta_comment"]) / len(group)),
        "avg_reach": round(statistics.mean(r["reach"] for r in group)),
        "avg_engagement_rate": round(statistics.mean(r["engagement_rate"] or 0 for r in group), 4),
    }

top10 = scored_sorted[:10]
bot10 = scored_sorted[-10:]

def brief_row(r):
    return {"hook": r["hook"], "content_type": r["content_type"],
            "theme": r["theme"], "day": r["day_of_week"], "reach": r["reach"],
            "views": r["views"], "comments": r["comments"], "saved": r["saved"],
            "shares": r["shares"], "engagement_rate": r["engagement_rate"],
            "perf_score": r["perf_score"], "date": r["date"], "url": r["url"]}

analysis = {
    "meta": {
        "handle": "@dianatheatlrealtor",
        "brand": "Diana the ATL Realtor",
        "source": "Metricool API (authorized) via MCP, brand id 3526631",
        "total_records": len(records),
        "scored_records": len(scored),
        "date_range": [min(r["date"] for r in records), max(r["date"] for r in records)],
    },
    "content_type_performance": by_type,
    "theme_performance": by_theme_ranked,
    "hooks_by_perf_score": hooks_by_perf,
    "hooks_by_views": hooks_by_views,
    "hooks_by_comments": hooks_by_comments,
    "phrase_differential_words": phrase_diff_words,
    "phrase_differential_bigrams": phrase_diff_bigrams,
    "cadence_day_of_week": by_dow,
    "cadence_hour_bucket": by_hour,
    "top10": [brief_row(r) for r in top10],
    "bottom10": [brief_row(r) for r in bot10],
    "top10_commonalities": commonalities(top10),
    "bottom10_commonalities": commonalities(bot10),
}

with open(os.path.join(PROC, "analysis.json"), "w", encoding="utf-8") as f:
    json.dump(analysis, f, indent=2, ensure_ascii=False)

print("Analysis written. Highlights:")
print("\nContent type (avg perf score / avg reach / avg eng rate):")
for t, s in by_type.items():
    print(f"  {t:9} n={s['count']:2}  perf={s['avg_perf_score']:5}  reach={s['avg_reach']:8}  ER={s['avg_engagement_rate']}")
print("\nThemes ranked by avg perf score:")
for th, s in by_theme_ranked.items():
    print(f"  {s['avg_perf_score']:5}  n={s['count']:2}  reach={s['avg_reach']:8}  {th}")
print("\nDay of week (avg perf / avg reach):")
for d, s in by_dow.items():
    print(f"  {d:9} n={s['count']:2}  perf={s['avg_perf_score']:5}  reach={s['avg_reach']}")
