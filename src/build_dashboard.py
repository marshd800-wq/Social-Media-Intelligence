"""
Regenerate the dashboard's embedded data from the processed JSONs and write
both output/dashboard.html and the site-root index.html.

This makes the dashboard rebuildable without hand-editing: the weekly refresh
runs the pipeline, then this script re-injects the three <script type=json>
blobs (data / xdata / pbase) into the HTML template.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "output")


def build_data_blob():
    """The 'data' blob = Instagram analysis, same shape the dashboard expects."""
    a = json.load(open(os.path.join(PROC, "analysis.json"), encoding="utf-8"))
    out = {"meta": a["meta"]}
    out["content_type"] = {k: {"count": v["count"], "perf": v["avg_perf_score"],
        "reach": v["avg_reach"], "views": v["avg_views"], "er": v["avg_engagement_rate"],
        "saved": v["avg_saved"], "shares": v["avg_shares"]}
        for k, v in a["content_type_performance"].items()}
    out["themes"] = [{"name": k, "count": v["count"], "perf": v["avg_perf_score"],
        "reach": v["avg_reach"], "er": v["avg_engagement_rate"], "comments": v["avg_comments"]}
        for k, v in a["theme_performance"].items()]
    out["hooks"] = [{"hook": h["hook"], "type": h["content_type"], "theme": h["theme"],
        "reach": h["reach"], "comments": h["comments"], "perf": h["perf_score"], "url": h["url"]}
        for h in a["hooks_by_perf_score"][:10]]
    out["dow"] = {k: {"count": v["count"], "perf": v["avg_perf_score"], "reach": v["avg_reach"]}
        for k, v in a["cadence_day_of_week"].items()}
    out["hour"] = {k: {"count": v["count"], "perf": v["avg_perf_score"], "reach": v["avg_reach"]}
        for k, v in a["cadence_hour_bucket"].items()}
    out["top10"] = [{"hook": r["hook"], "type": r["content_type"], "day": r["day"],
        "reach": r["reach"], "views": r["views"], "comments": r["comments"],
        "perf": r["perf_score"], "url": r["url"]} for r in a["top10"]]
    out["bottom10"] = [{"hook": r["hook"], "type": r["content_type"], "day": r["day"],
        "reach": r["reach"], "perf": r["perf_score"], "url": r["url"]} for r in a["bottom10"]]
    out["val"] = json.load(open(os.path.join(PROC, "model_validation.json")))
    return out


def build_xdata_blob():
    x = json.load(open(os.path.join(PROC, "cross_platform.json"), encoding="utf-8"))
    return {"summary": x["platform_summary"], "matches": x["cross_posted_matches"],
            "tk_hooks": x["tiktok_top_hooks"], "tk_themes": x["tiktok_themes"],
            "dormant": x["dormant_platforms"]}


def inject(html, blob_id, obj):
    payload = json.dumps(obj, ensure_ascii=False)
    pat = re.compile(r'(<script id="%s" type="application/json">).*?(</script>)' % blob_id, re.S)
    if not pat.search(html):
        raise SystemExit(f"blob '{blob_id}' not found in template")
    return pat.sub(lambda m: m.group(1) + payload + m.group(2), html, count=1)


def main():
    html = open(os.path.join(OUT, "dashboard.html"), encoding="utf-8").read()
    html = inject(html, "data", build_data_blob())
    html = inject(html, "xdata", build_xdata_blob())
    html = inject(html, "pbase", json.load(open(os.path.join(PROC, "platform_baselines.json"))))
    open(os.path.join(OUT, "dashboard.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(html)
    print("Rebuilt output/dashboard.html and index.html from processed data.")


if __name__ == "__main__":
    main()
