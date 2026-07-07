"""
NOVA Content Scoring Model — PLATFORM-AWARE
===========================================
Predicts the RELATIVE performance of a proposed post before it's published,
judged by the norms of the platform it's going on. Instagram and TikTok reward
opposite things, so the rules branch:

                        Instagram                 TikTok
  caption length        longer wins (~127 wds)    SHORTER wins (~32 wds)
  hashtags              few win (<=3)             normal/expected (no penalty)
  format                carousel > reel > static  video >> photo
  hook                  story + curiosity         short, punchy, personality

Baselines (per-platform type & theme performance) are learned in
platform_model.py from each platform's own distribution.

Usage:
    python3 src/score.py --platform tiktok --type reel \\
        --hook "Describe your job and make it sound illegal... I'll go first." \\
        --caption "short punchy caption #atlantarealestate #fyp"
"""
import json
import os
import re
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROC = os.path.join(ROOT, "data", "processed")

_base = json.load(open(os.path.join(PROC, "platform_baselines.json"), encoding="utf-8"))

import importlib.util
_spec = importlib.util.spec_from_file_location("ingest", os.path.join(HERE, "ingest.py"))
_ingest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ingest)
classify_theme = _ingest.classify_theme
extract_hashtags = _ingest.extract_hashtags

PLATFORMS = {"instagram": "Instagram", "ig": "Instagram", "tiktok": "TikTok", "tt": "TikTok"}

HOOK_SIGNALS = [
    ("Curiosity / open loop", 8,
     r"(?i)\b(the .* part|nobody (tells|says)|what .* looks like|here'?s (why|what|the)|the (secret|truth|#?1)|do not|don'?t make a move|until you read)\b"),
    ("POV / relatable framing", 7,
     r"(?i)\b(pov|describe your job|how it'?s going|when you|that feeling|imagine)\b"),
    ("Bold / punchy one-liner", 6, None),
    ("Local specificity (Metro Atlanta / county / city)", 6,
     r"(?i)\b(metro atlanta|cobb|fulton|marietta|kennesaw|smyrna|atlanta|fairburn|dekalb)\b"),
    ("Direct address / calls out a segment", 5,
     r"(?i)(teachers|first[- ]time|move[- ]up|sellers?|buyers?|relocating|been in your home|self-?employed|bookie)\b"),
    ("Personal story opener", 5,
     r"(?i)\b(nothing brings me|my mom|i love|not one cold call|grateful|childhood|congratulations|miss you)\b"),
    ("Question hook", 3, r"\?"),
    ("Number / list promise", 3, r"(?i)\b(\d+\s+(things|tips|myths|reasons|mistakes|steps|ways)|top \d+)\b"),
]
HOOK_PENALTIES = [
    ("Generic seasonal opener", -10,
     r"(?i)\b(is here|is fast approaching|marks the start|brings the promise|perfect time to|as (summer|spring|fall|winter))\b"),
    ("Real-estate platitude / cliché", -8,
     r"(?i)\b(owning a home is much more|your home is your haven|more than just a roof|dream home awaits)\b"),
    ("Global 'Find Home Anywhere' travelogue framing", -8,
     r"(?i)\b(find ?home ?anywhere|here or there|your global agent|island (life|living)|la dolce vita)\b"),
]


def _hook_component(hook, platform):
    detail, pts = [], 0
    words = len((hook or "").split())
    for name, val, pat in HOOK_SIGNALS:
        if pat is None:  # bold punchy one-liner — rewarded MORE on TikTok
            if 0 < words <= 9 and "#" not in (hook or ""):
                v = val + 3 if platform == "TikTok" else val
                pts += v
                detail.append((name, v))
        elif re.search(pat, hook or ""):
            pts += val
            detail.append((name, val))
    for name, val, pat in HOOK_PENALTIES:
        if re.search(pat, hook or ""):
            pts += val
            detail.append((name, val))
    pts = max(-20, min(26, pts))
    return pts, detail


def score_content(hook, caption, content_type, platform="Instagram"):
    platform = PLATFORMS.get((platform or "instagram").lower().strip(), platform)
    if platform not in _base:
        platform = "Instagram"
    base = _base[platform]
    content_type = (content_type or "reel").lower().strip()
    if content_type in ("photo", "image", "post"):
        content_type = "static"
    if content_type in ("video", "tiktok", "short"):
        content_type = "reel"
    if platform == "TikTok" and content_type == "carousel":
        content_type = "static"      # TikTok has no carousels
    caption = caption or ""
    hook = hook or (caption.split("\n")[0] if caption else "")
    breakdown = []

    # 1) content-type baseline (per platform)
    tp = base["type_perf"].get(content_type, 50.0)
    breakdown.append((f"{platform} content-type baseline", round(tp - 50, 1),
                      f"{content_type} averages {tp:.0f}/100 on {platform}"))

    # 2) theme baseline (per platform)
    theme, _ = classify_theme(caption or hook)
    thp = base["theme_perf"].get(theme, 50.0)
    theme_adj = max(-12, min(12, (thp - 50) * 0.6))
    breakdown.append(("Theme fit", round(theme_adj, 1),
                      f"'{theme}' averages {thp:.0f}/100 on {platform}"))

    # 3) hook quality
    hook_pts, hook_detail = _hook_component(hook, platform)
    breakdown.append(("Hook quality", round(hook_pts, 1),
                      "; ".join(f"{n} ({v:+d})" for n, v in hook_detail) or "no strong signal"))

    # 4) hashtag rule — platform-specific
    ht = len(extract_hashtags(caption))
    if platform == "TikTok":
        if ht == 0:
            ht_pts, ht_note = 0, "no hashtags — a few (#fyp, local tags) help discovery on TikTok"
        elif ht <= 8:
            ht_pts, ht_note = 3, f"{ht} hashtags — normal for TikTok discovery"
        else:
            ht_pts, ht_note = -3, f"{ht} hashtags — excessive even for TikTok"
    else:  # Instagram: discipline wins
        if ht <= 3:
            ht_pts, ht_note = 4, f"{ht} hashtags — disciplined (top IG posts avg ~1.4)"
        elif ht <= 6:
            ht_pts, ht_note = 0, f"{ht} hashtags — neutral"
        else:
            ht_pts, ht_note = -6, f"{ht} hashtags — over-tagged (bottom IG posts avg ~5.7)"
    breakdown.append(("Hashtag fit", ht_pts, ht_note))

    # 5) lead-gen CTA (both platforms)
    has_cta = bool(re.search(
        r"(?i:comment|dm me|dm|message|drop|text)[^\n]{0,20}?[\"'“‘]?([A-Z]{2,12})\b", caption))
    breakdown.append(("Lead-gen CTA", 6 if has_cta else 0,
                      "present — drives comments/DMs" if has_cta
                      else "none — add 'Comment/DM/Text WORD'"))

    # 6) caption depth — INVERTED by platform
    wc = len(caption.split())
    if platform == "TikTok":
        if wc <= 20:
            depth_pts, depth_note = 4, f"{wc} words — short & punchy (TikTok norm ~32)"
        elif wc <= 60:
            depth_pts, depth_note = 1, f"{wc} words — okay for TikTok"
        else:
            depth_pts, depth_note = -4, f"{wc} words — too long for TikTok; trim it"
    else:  # Instagram: depth wins
        if wc >= 60:
            depth_pts, depth_note = 4, f"{wc} words — substantive (top IG posts avg ~124)"
        elif wc >= 25:
            depth_pts, depth_note = 1, f"{wc} words — adequate"
        else:
            depth_pts, depth_note = -3, f"{wc} words — thin for IG; add story/context"
    breakdown.append(("Caption depth", depth_pts, depth_note))

    raw = 50 + sum(b[1] for b in breakdown)
    score = max(1, min(99, round(raw, 1)))
    if score >= 70:
        tier = f"TOP TIER — greenlight for {platform}"
    elif score >= 55:
        tier = f"STRONG — post it on {platform}"
    elif score >= 42:
        tier = "AVERAGE — strengthen the flagged items"
    else:
        tier = f"AT RISK — resembles low performers on {platform}; rework first"

    return {"score": score, "tier": tier, "platform": platform,
            "detected_theme": theme, "content_type": content_type,
            "breakdown": breakdown,
            "recommendations": _recommend(platform, breakdown, has_cta, ht, wc)}


def _recommend(platform, breakdown, has_cta, ht, wc):
    recs = []
    if dict((n, v) for n, v, _ in breakdown).get("Hook quality", 0) <= 0:
        recs.append("Rewrite the hook: curiosity gap, POV, or a bold short line.")
    if not has_cta:
        recs.append("Add a one-word CTA (Comment/DM/Text WORD) — lifts comments ~2.3x.")
    if platform == "Instagram":
        if ht > 6:
            recs.append("Cut hashtags to 3 or fewer — IG top posts average ~1.4.")
        if wc < 25:
            recs.append("Add story/context — thin captions underperform on Instagram.")
    else:  # TikTok
        if wc > 60:
            recs.append("Trim the caption — TikTok winners are short; put depth in the video.")
        if ht == 0:
            recs.append("Add a few TikTok tags (#fyp + local) to aid discovery.")
    return recs


def _fmt(res):
    lines = [f"\n[{res['platform']}] Predicted: {res['score']}/100  →  {res['tier']}",
             f"Detected theme: {res['detected_theme']}  |  Type: {res['content_type']}",
             "\nScore breakdown:"]
    for name, val, note in res["breakdown"]:
        lines.append(f"  {val:+6.1f}   {name:34} {note}")
    if res["recommendations"]:
        lines.append("\nTo raise the score:")
        for r in res["recommendations"]:
            lines.append(f"  • {r}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Score a proposed post (platform-aware).")
    ap.add_argument("--platform", default="instagram", help="instagram | tiktok")
    ap.add_argument("--type", default="reel", help="reel | carousel | static")
    ap.add_argument("--hook", default="")
    ap.add_argument("--caption", default="")
    args = ap.parse_args()
    if not args.hook and not args.caption:
        # same short/casual clip scored for each platform — note the divergence
        h = "Describe your job and make it sound illegal... I'll go first."
        c = "Describe your job and make it sound illegal. I let myself into strangers' homes. #atlantarealestate #fyp"
        for plat in ("instagram", "tiktok"):
            print("=" * 74)
            print(_fmt(score_content(h, c, "reel", plat)))
        print("=" * 74)
    else:
        print(_fmt(score_content(args.hook, args.caption, args.type, args.platform)))
