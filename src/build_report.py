"""
Render output/analysis_report.md from data/processed/analysis.json.
Every figure in the report is emitted directly from the analysis so numbers
never drift from the data.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "output")
a = json.load(open(os.path.join(PROC, "analysis.json"), encoding="utf-8"))
val = json.load(open(os.path.join(PROC, "model_validation.json"), encoding="utf-8"))

L = []
w = L.append

m = a["meta"]
w("# Instagram Content Intelligence — Deep Dive")
w(f"**Account:** {m['handle']}  ·  **Brand:** {m['brand']}")
w(f"**Data source:** {m['source']}")
w(f"**Window:** {m['date_range'][0]} → {m['date_range'][1]}  ·  "
  f"**{m['total_records']} posts analyzed** ({m['scored_records']} with reach data)")
w("")
w("> Performance score = a 0–100 blend of percentile-ranked **reach (40%)**, "
  "**engagement rate (25%)**, **saves+shares virality (20%)** and "
  "**comments/conversation (15%)**. It lets a 40-reach post and a 2,000-reach "
  "post be compared fairly.")
w("")

def table(headers, rows):
    w("| " + " | ".join(headers) + " |")
    w("| " + " | ".join("---" for _ in headers) + " |")
    for r in rows:
        w("| " + " | ".join(str(c) for c in r) + " |")
    w("")

# 1. Content type
w("## 1. Content type performance")
rows = []
for t, s in a["content_type_performance"].items():
    rows.append([f"**{t}**", s["count"], s["avg_perf_score"], s["avg_reach"],
                 s["avg_views"], s["avg_engagement_rate"], s["avg_saved"], s["avg_shares"]])
table(["Type", "n", "Avg perf", "Avg reach", "Avg views", "Avg ER", "Avg saves", "Avg shares"], rows)
w("**Read:** Reels drive the widest **reach**; carousels drive the highest "
  "**engagement rate and save/share behavior**; static image posts trail on "
  "every dimension.")
w("")

# 2. Themes
w("## 2. Theme performance (ranked by avg performance score)")
rows = []
for th, s in a["theme_performance"].items():
    rows.append([th, s["count"], s["avg_perf_score"], s["avg_reach"],
                 s["avg_engagement_rate"], s["avg_comments"]])
table(["Theme", "n", "Avg perf", "Avg reach", "Avg ER", "Avg comments"], rows)
w("**Read:** Personal / behind-the-scenes, market-education, and humor lead. "
  "The **Find Home Anywhere global series** and **generic seasonal/lifestyle "
  "tips** are the weakest — and together they account for a large share of the "
  "back catalog.")
w("")

# 3. Hooks
w("## 3. Top hooks & opening lines")
w("### By overall performance score")
rows = [[f"{r['perf_score']}", r["content_type"], r["theme"], r["reach"],
         r["comments"], f"[{r['hook'][:70]}]({r['url']})"] for r in a["hooks_by_perf_score"][:12]]
table(["Perf", "Type", "Theme", "Reach", "Cmts", "Hook"], rows)
w("### By comments (conversation / DM-funnel signal)")
rows = [[r["comments"], r["content_type"], f"[{r['hook'][:75]}]({r['url']})"]
        for r in a["hooks_by_comments"][:10]]
table(["Comments", "Type", "Hook"], rows)
w("")

# 4. Phrase differential
w("## 4. Language that separates winners from losers")
w("Words/phrases that appear in **top-quartile** captions but are largely absent "
  "from **bottom-quartile** captions:")
words = ", ".join(f"`{d['term']}`" for d in a["phrase_differential_words"][:18])
w(f"**Words:** {words}")
w("")
bigrams = ", ".join(f"`{d['term']}`" for d in a["phrase_differential_bigrams"][:16])
w(f"**Phrases:** {bigrams}")
w("")
w("**Read:** Winning captions talk about **Metro Atlanta specifically**, "
  "**first-time buyers**, being **trusted / built**, **opportunity**, "
  "**budget**, **what's next**, and personal **gratitude** — concrete, local, "
  "and story-driven. Losing captions lean on generic travelogue and seasonal "
  "filler.")
w("")

# 5. Cadence
w("## 5. Posting cadence")
w("### Day of week")
rows = [[d, s["count"], s["avg_perf_score"], s["avg_reach"]]
        for d, s in a["cadence_day_of_week"].items()]
table(["Day", "n", "Avg perf", "Avg reach"], rows)
w("### Time of day")
rows = [[h, s["count"], s["avg_perf_score"], s["avg_reach"]]
        for h, s in a["cadence_hour_bucket"].items()]
table(["Window", "n", "Avg perf", "Avg reach"], rows)
w("**Read:** **Wednesday and Saturday** post the strongest performance scores; "
  "**Friday** delivers the widest reach. The **5–8pm evening** window is the "
  "single best time to publish; early morning is weakest.")
w("")

# 6. Top / bottom
def block(title, rows_key, comm_key):
    w(f"## {title}")
    rows = [[f"{r['perf_score']}", r["content_type"], r["day"], r["reach"],
             r["views"], r["comments"], r["saved"], r["shares"],
             f"[{r['hook'][:60]}]({r['url']})"] for r in a[rows_key]]
    table(["Perf", "Type", "Day", "Reach", "Views", "Cmt", "Sav", "Shr", "Hook"], rows)
    c = a[comm_key]
    w(f"- **Types:** {c['types']}")
    w(f"- **Themes:** {c['themes']}")
    w(f"- **Avg caption length:** {c['avg_caption_words']} words  ·  "
      f"**Avg hashtags:** {c['avg_hashtags']}  ·  "
      f"**Lead-gen CTA present:** {c['pct_with_cta']}%")
    w(f"- **Avg reach:** {c['avg_reach']}  ·  **Avg ER:** {c['avg_engagement_rate']}")
    w("")

block("6. The 10 best-performing posts", "top10", "top10_commonalities")
block("7. The 10 lowest-performing posts", "bottom10", "bottom10_commonalities")

w("### What separates them")
w("| Signal | Top 10 | Bottom 10 |")
w("| --- | --- | --- |")
t, b = a["top10_commonalities"], a["bottom10_commonalities"]
w(f"| Format | mostly reels + carousels | {b['types'].get('static',0)}/10 static images |")
w(f"| Hashtags | {t['avg_hashtags']} avg | {b['avg_hashtags']} avg |")
w(f"| Lead-gen CTA | {t['pct_with_cta']}% | {b['pct_with_cta']}% |")
w(f"| Avg reach | {t['avg_reach']} | {b['avg_reach']} |")
w(f"| Engagement rate | {t['avg_engagement_rate']} | {b['avg_engagement_rate']} |")
w("")

# 8. Model
w("## 8. Predictive scoring model — back-test")
w(f"- Spearman(predicted score, reach) = **{val['spearman_pred_vs_reach']}**")
w(f"- Spearman(predicted score, engagement rate) = **{val['spearman_pred_vs_engagement_rate']}**")
w(f"- Posts the model flags **top-quartile** averaged **{val['predicted_top_quartile_avg_reach']} reach** "
  f"vs **{val['predicted_bottom_quartile_avg_reach']}** for predicted-bottom — a "
  f"**{val['reach_separation_x']}× separation**.")
w("")
w("Score any draft before posting:")
w("```bash")
w('python3 src/score.py --type reel \\')
w('  --hook "The job offer was the easy part." \\')
w('  --caption "full caption ... Comment ATLANTA and I\'ll take it from there."')
w("```")
w("")

open(os.path.join(OUT, "analysis_report.md"), "w", encoding="utf-8").write("\n".join(L))
print("Wrote output/analysis_report.md")
