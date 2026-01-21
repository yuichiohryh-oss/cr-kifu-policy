import argparse
import json
from pathlib import Path
import sys


def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc


def load_model(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_args():
    parser = argparse.ArgumentParser(description="Score policy model with dataset labels.")
    parser.add_argument("--model", required=True, help="Path to policy.pt")
    parser.add_argument("--dataset", required=True, help="Path to dataset.jsonl")
    parser.add_argument(
        "--topk",
        type=int,
        default=3,
        help="Top-k accuracy to compute (default: 3)",
    )
    parser.add_argument("--out", help="Optional output JSON path")
    return parser.parse_args()


def label_key(label):
    pos_grid = label.get("pos_grid") if label else None
    if pos_grid is None:
        return None
    slot = label.get("slot")
    gx = pos_grid.get("gx")
    gy = pos_grid.get("gy")
    if slot is None or gx is None or gy is None:
        return None
    return (int(slot), int(gx), int(gy))


def sort_labels(labels):
    def score(entry):
        prob = entry.get("prob")
        if prob is None:
            prob = entry.get("count", 0)
        return prob

    return sorted(labels, key=score, reverse=True)


def main():
    args = parse_args()
    for path in (args.model, args.dataset):
        if not Path(path).is_file():
            raise SystemExit(f"Missing file: {path}")

    model = load_model(args.model)
    labels = model.get("labels", [])
    if not labels:
        raise SystemExit("Model contains no labels to score")

    labels_sorted = sort_labels(labels)
    topk = max(1, args.topk)
    topk = min(topk, len(labels_sorted))
    top1 = label_key(labels_sorted[0]) if labels_sorted else None
    topk_labels = {
        label_key(label) for label in labels_sorted[:topk] if label_key(label) is not None
    }

    total = 0
    correct_top1 = 0
    correct_topk = 0
    missing_label = 0

    for sample in iter_jsonl(args.dataset):
        total += 1
        key = label_key(sample.get("label"))
        if key is None:
            missing_label += 1
            continue
        if key == top1:
            correct_top1 += 1
        if key in topk_labels:
            correct_topk += 1

    if total == 0:
        raise SystemExit("No samples found in dataset.jsonl")
    if missing_label > 0:
        print(f"Warning: {missing_label} samples missing labels.", file=sys.stderr)

    top1_acc = correct_top1 / total
    topk_acc = correct_topk / total

    report = {
        "schema_version": "policy_score/1",
        "total_samples": total,
        "top1_correct": correct_top1,
        "top1_acc": top1_acc,
        "topk": topk,
        "topk_correct": correct_topk,
        "topk_acc": topk_acc,
        "label_count": len(labels_sorted),
        "missing_label": missing_label,
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
