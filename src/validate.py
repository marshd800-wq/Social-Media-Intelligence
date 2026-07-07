"""
Back-test the scoring model against Diana's real history.
Confirms the predicted score actually separates winners from losers.
"""
import json
import os
import statistics
from score import score_content

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
d = json.load(open(os.path.join(ROOT, "data", "processed", "dataset.json"), encoding="utf-8"))
scored = [r for r in d if r["reach"]]


def rank(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0] * len(v)
    for k, i in enumerate(order):
        r[i] = k
    return r


def spearman(x, y):
    rx, ry = rank(x), rank(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = sum((a - mx) ** 2 for a in rx) ** 0.5
    sy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (sx * sy)


def main():
    preds, er, reach = [], [], []
    for r in scored:
        preds.append(score_content(r["hook"], r["caption"], r["content_type"])["score"])
        er.append(r["engagement_rate"] or 0)
        reach.append(r["reach"])
    paired = sorted(zip(preds, reach, er), reverse=True)
    q = len(paired) // 4
    top, bot = paired[:q], paired[-q:]
    result = {
        "n": len(scored),
        "spearman_pred_vs_engagement_rate": round(spearman(preds, er), 3),
        "spearman_pred_vs_reach": round(spearman(preds, reach), 3),
        "predicted_top_quartile_avg_reach": round(statistics.mean(x[1] for x in top)),
        "predicted_bottom_quartile_avg_reach": round(statistics.mean(x[1] for x in bot)),
        "reach_separation_x": round(statistics.mean(x[1] for x in top)
                                    / statistics.mean(x[1] for x in bot), 1),
    }
    print(json.dumps(result, indent=2))
    with open(os.path.join(ROOT, "data", "processed", "model_validation.json"), "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
