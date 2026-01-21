import argparse
import json
import math
from pathlib import Path
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize policy.pt statistics.")
    parser.add_argument("--model", required=True, help="Path to policy.pt")
    parser.add_argument(
        "--topk",
        type=int,
        default=5,
        help="Number of top labels to include (default: 5)",
    )
    parser.add_argument("--out", help="Optional output JSON path")
    return parser.parse_args()


def label_prob(label, total_samples):
    prob = label.get("prob")
    if prob is not None:
        return float(prob)
    count = label.get("count")
    if count is None or total_samples <= 0:
        return 0.0
    return float(count) / total_samples


def entropy(probs):
    ent = 0.0
    for prob in probs:
        if prob <= 0.0:
            continue
        ent -= prob * math.log(prob, 2)
    return ent


def main():
    args = parse_args()
    model_path = Path(args.model)
    if not model_path.is_file():
        raise SystemExit(f"Missing file: {args.model}")

    model = load_json(model_path)
    labels = model.get("labels", [])
    total_samples = int(model.get("total_samples", 0))

    if not labels:
        raise SystemExit("Model contains no labels")

    if total_samples <= 0:
        total_samples = sum(int(label.get("count", 0)) for label in labels)

    scored = []
    probs = []
    for label in labels:
        prob = label_prob(label, total_samples)
        probs.append(prob)
        scored.append((prob, label))

    scored.sort(key=lambda item: item[0], reverse=True)
    topk = max(1, args.topk)
    topk = min(topk, len(scored))
    top_entries = []
    cumulative = 0.0
    for rank, (prob, label) in enumerate(scored[:topk], 1):
        cumulative += prob
        top_entries.append(
            {
                "rank": rank,
                "slot": label.get("slot"),
                "pos_grid": label.get("pos_grid"),
                "prob": prob,
                "count": label.get("count"),
                "cumulative_prob": cumulative,
            }
        )

    report = {
        "schema_version": "policy_stats/1",
        "label_count": len(labels),
        "total_samples": total_samples,
        "probability": {
            "max": max(probs),
            "min": min(probs),
            "entropy": entropy(probs),
        },
        "topk": topk,
        "top_labels": top_entries,
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))
    if total_samples <= 0:
        print("Warning: total_samples is zero or missing.", file=sys.stderr)


if __name__ == "__main__":
    main()
