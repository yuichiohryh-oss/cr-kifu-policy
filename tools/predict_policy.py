import argparse
import json
from pathlib import Path
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_args():
    parser = argparse.ArgumentParser(description="Predict next action from a policy model.")
    parser.add_argument("--model", required=True, help="Path to policy.pt")
    parser.add_argument("--video", required=True, help="Path to video.mp4")
    parser.add_argument("--meta", required=True, help="Path to meta.json")
    parser.add_argument("--topk", type=int, default=3, help="Number of top actions")
    parser.add_argument("--out", help="Optional output path for predictions jsonl")
    return parser.parse_args()


def label_score(label, total_samples):
    prob = label.get("prob")
    if prob is not None:
        return float(prob)
    count = label.get("count", 0)
    if total_samples > 0:
        return float(count) / total_samples
    return float(count)


def main():
    args = parse_args()
    for path in (args.model, args.video, args.meta):
        if not Path(path).is_file():
            raise SystemExit(f"Missing required file: {path}")

    model = load_json(args.model)
    if model.get("schema_version") != "policy/1":
        print("Warning: unexpected model schema_version", file=sys.stderr)

    labels = model.get("labels", [])
    total_samples = int(model.get("total_samples", 0) or 0)
    if not labels:
        raise SystemExit("Model contains no labels to predict")
    if total_samples <= 0:
        total_samples = sum(int(label.get("count", 0)) for label in labels)

    meta = load_json(args.meta)
    run_id = meta.get("run_id", "unknown")

    labels_sorted = sorted(
        labels,
        key=lambda label: label_score(label, total_samples),
        reverse=True,
    )
    topk = max(1, args.topk)
    topk = min(topk, len(labels_sorted))
    predictions = []
    for rank, label in enumerate(labels_sorted[:topk], 1):
        prob = label_score(label, total_samples)
        predictions.append(
            {
                "rank": rank,
                "run_id": run_id,
                "slot": label["slot"],
                "pos_grid": label["pos_grid"],
                "score": prob,
            }
        )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            for pred in predictions:
                handle.write(json.dumps(pred, separators=(",", ":")) + "\n")
    else:
        for pred in predictions:
            print(json.dumps(pred, separators=(",", ":")))


if __name__ == "__main__":
    main()
