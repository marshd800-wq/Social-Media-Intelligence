"""
NOVA Social Media Intelligence Engine — Content Scoring Model
=============================================================
Predicts the RELATIVE performance of a proposed post before Diana publishes it.

The model is not a black box — every weight is either learned from Diana's own
history (data/processed/analysis.json) or is a transparent, documented rule
derived from the top-vs-bottom patterns the analysis surfaced. Output is a
0-100 score, a predicted tier, and a line-item breakdown so the "why" is visible.

Usage:
    python3 src/score.py --type reel \\
        --hook "The job offer was the easy part." \\
        --caption "full caption text ..."

    # or import and call score_content(hook, caption, content_type)
"""
import json
import os
import re
import argparse
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")

_analysis = json.load(open(os.path.join(PROC, "analysis.json"), encoding="utf-8"))

# ---- Learned components ---------------------------------------------------
# Content-type multiplier, learned from avg perf score by type, centered on 50.
_type_perf = {t: (v.get("avg_perf_score") or 50)
              for t, v in _analysis["content_type_performance"].items()}
# Theme multiplier, learned from avg perf score by theme.
_theme_perf = {t: (v.get("avg_perf_score") or 50)
               for t, v in _analysis["theme_performance"].items()}

# Reuse the exact theme classifier from ingest so scoring and dataset agree.
import importlib.util
_spec = importlib.util.spec_from_file_location("ingest", os.path.join(HERE, "ingest.py"))
_ingest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ingest)
classify_theme = _ingest.classify_theme
extract_hashtags = _ingest.extract_hashtags


# ---- Hook-quality heuristics (derived from top-performing hooks) ----------
# Patterns that recur in Diana's top-decile hooks and are absent from the
# bottom decile. Each contributes bounded points.
HOOK_SIGNALS = [
    ("Curiosity / open loop", +8,
     r"(?i)\b(the .* part|nobody (tells|says)|what .* looks like|here'?s (why|what|the)|the (secret|truth|#?1)|do not|don'?t make a move|until you read)\b"),
    ("POV / relatable framing", +7,
     r"(?i)\b(pov|describe your job|how it'?s going|when you|that feeling|imagine)\b"),
    ("Bold / punchy one-liner (short, declarative)", +6, None),  # length-based, handled below
    ("Local specificity (Metro Atlanta / county / city)", +6,
     r"(?i)\b(metro atlanta|cobb|fulton|marietta|kennesaw|smyrna|atlanta|fairburn|dekalb)\b"),
    ("Direct address / calls out a segment", +5,
     r"(?i)(teachers|first[- ]time|move[- ]up|sellers?|buyers?|relocating|been in your home|self-?employed)\b"),
    ("Personal story opener", +5,
     r"(?i)\b(nothing brings me|my mom|i love|not one cold call|grateful|childhood|congratulations)\b"),
    ("Question hook", +3, r"\?"),
    ("Number / list promise", +3, r"(?i)\b(\d+\s+(things|tips|myths|reasons|mistakes|steps|ways)|top \d+)\b"),
]

# Anti-patterns that recur in bottom-decile hooks (generic / seasonal / platitude).
HOOK_PENALTIES = [
    ("Generic seasonal opener ('May is here…', 'Winter is fast approaching…')", -10,
     r"(?i)\b(is here|is fast approaching|marks the start|brings the promise|perfect time to|as (summer|spring|fall|winter))\b"),
    ("Real-estate platitude / cliché", -8,
     r"(?i)\b(owning a home is much more|your home is your haven|more than just a roof|dream home awaits)\b"),
    ("Global 'Find Home Anywhere' travelogue framing", -8,
     r"(?i)\b(find ?home ?anywhere|here or there|your global agent|island (life|living)|la dolce vita)\b"),
]


def _hook_component(hook):
    detail = []
    pts = 0
    words = len((hook or "").split())
    for name, val, pat in HOOK_SIGNALS:
        if pat is None:
            # bold punchy one-liner: short (<= 9 words), no hashtag, ends strong
            if 0 < words <= 9 and "#" not in (hook or ""):
                pts += val
                detail.append((name, val))
        elif re.search(pat, hook or ""):
            pts += val
            detail.append((name, val))
    for name, val, pat in HOOK_PENALTIES:
        if re.search(pat, hook or ""):
            pts += val
            detail.append((name, val))
    # cap hook contribution to a sensible band
    pts = max(-20, min(24, pts))
    return pts, detail


def score_content(hook, caption, content_type):
    content_type = (content_type or "reel").lower().strip()
    if content_type in ("photo", "image", "post"):
        content_type = "static"
    caption = caption or ""
    hook = hook or (caption.split("\n")[0] if caption else "")

    breakdown = []

    # 1) Base from content type (learned). Center 50.
    type_base = _type_perf.get(content_type, 50.0)
    breakdown.append(("Content type baseline (learned)",
                      round(type_base - 50, 1),
                      f"{content_type} historically averages {type_base:.0f}/100"))

    # 2) Theme adjustment (learned).
    theme, _ = classify_theme(caption or hook)
    theme_perf = _theme_perf.get(theme, 50.0)
    # dampen and cap so low-sample themes can't dominate the score
    theme_adj = max(-12, min(12, (theme_perf - 50) * 0.6))
    breakdown.append(("Theme fit (learned)", round(theme_adj, 1),
                      f"'{theme}' averages {theme_perf:.0f}/100"))

    # 3) Hook quality (rules from top vs bottom hooks).
    hook_pts, hook_detail = _hook_component(hook)
    breakdown.append(("Hook quality", round(hook_pts, 1),
                      "; ".join(f"{n} ({v:+d})" for n, v in hook_detail) or "no strong signal"))

    # 4) Hashtag discipline (top posts avg 1.4, bottom avg 5.7).
    ht = len(extract_hashtags(caption))
    if ht <= 3:
        ht_pts = 4
        ht_note = f"{ht} hashtags — disciplined (top posts avg ~1.4)"
    elif ht <= 6:
        ht_pts = 0
        ht_note = f"{ht} hashtags — neutral"
    else:
        ht_pts = -6
        ht_note = f"{ht} hashtags — over-tagged (bottom posts avg ~5.7)"
    breakdown.append(("Hashtag discipline", ht_pts, ht_note))

    # 5) Lead-gen CTA (comment/DM keyword). CTA posts get ~2.3x comments.
    has_cta = bool(re.search(
        r"(?i:comment|dm me|dm|message)[^\n]{0,20}?[\"'“‘]?([A-Z]{2,12})\b", caption))
    cta_pts = 6 if has_cta else 0
    breakdown.append(("Lead-gen CTA (Comment/DM keyword)", cta_pts,
                      "present — drives comments + saves" if has_cta
                      else "none — add 'Comment WORD' to lift comments/DMs"))

    # 6) Caption depth (top posts avg ~124 words; very short captions underperform).
    wc = len(caption.split())
    if wc >= 60:
        depth_pts = 4
        depth_note = f"{wc} words — substantive (top posts avg ~124)"
    elif wc >= 25:
        depth_pts = 1
        depth_note = f"{wc} words — adequate"
    else:
        depth_pts = -3
        depth_note = f"{wc} words — thin; add story/context"
    breakdown.append(("Caption depth", depth_pts, depth_note))

    raw = 50 + sum(b[1] for b in breakdown)
    score = max(1, min(99, round(raw, 1)))

    if score >= 70:
        tier = "TOP TIER — greenlight (matches your best-performing patterns)"
    elif score >= 55:
        tier = "STRONG — post it; small tweaks below could push it higher"
    elif score >= 42:
        tier = "AVERAGE — will likely land mid-pack; strengthen the flagged items"
    else:
        tier = "AT RISK — resembles your lowest-performing posts; rework before posting"

    return {
        "score": score, "tier": tier, "detected_theme": theme,
        "content_type": content_type, "breakdown": breakdown,
        "recommendations": _recommend(breakdown, has_cta, ht, wc, hook_detail),
    }


def _recommend(breakdown, has_cta, ht, wc, hook_detail):
    recs = []
    hook_pts = dict((n, v) for n, v, _ in breakdown).get("Hook quality", 0)
    if hook_pts <= 0:
        recs.append("Rewrite the hook as a curiosity gap, POV, or a bold <9-word "
                    "line — e.g. 'The job offer was the easy part.'")
    if not has_cta:
        recs.append("Add a one-word comment CTA ('Comment NEXT / DEAL / MOVE') to "
                    "trigger the DM funnel — your CTA posts get ~2.3x the comments.")
    if ht > 6:
        recs.append("Cut hashtags to 3 or fewer; your top posts average ~1.4.")
    if wc < 25:
        recs.append("Add context or a short story — thin captions underperform.")
    return recs


def _fmt(res):
    lines = [f"\nPredicted performance: {res['score']}/100  →  {res['tier']}",
             f"Detected theme: {res['detected_theme']}  |  Type: {res['content_type']}",
             "\nScore breakdown:"]
    for name, val, note in res["breakdown"]:
        lines.append(f"  {val:+6.1f}   {name:38} {note}")
    if res["recommendations"]:
        lines.append("\nTo raise the score:")
        for r in res["recommendations"]:
            lines.append(f"  • {r}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Score a proposed Instagram post.")
    ap.add_argument("--type", default="reel", help="reel | carousel | static")
    ap.add_argument("--hook", default="")
    ap.add_argument("--caption", default="")
    args = ap.parse_args()
    if not args.hook and not args.caption:
        # demo on a couple of contrasting examples
        demos = [
            ("reel", "The job offer was the easy part.",
             "The job offer was the easy part. Now you're staring at a map of a "
             "city you've barely visited. This is the part I do every week — I help "
             "people relocate to Metro Atlanta. Comment ATLANTA and I'll take it from there."),
            ("static", "May is here, and with it comes the promise of sunny days.",
             "May is here, and with it comes the promise of sunny days and warm "
             "breezes. #FindHomeAnywhere #BahamasLiving #IslandLife #SummerStartsNow "
             "#GlobalRealEstate #YourGlobalAgent"),
        ]
        for t, h, c in demos:
            print("=" * 78)
            print(f"HOOK: {h}")
            print(_fmt(score_content(h, c, t)))
        print("=" * 78)
    else:
        print(_fmt(score_content(args.hook, args.caption, args.type)))
