import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


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


def parse_args():
    parser = argparse.ArgumentParser(description="Train a baseline policy model.")
    parser.add_argument("--dataset", required=True, help="Path to dataset.jsonl")
    parser.add_argument("--out", required=True, help="Output directory for model")
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        raise SystemExit(f"Missing dataset: {args.dataset}")

    counter = Counter()
    total = 0
    for sample in iter_jsonl(args.dataset):
        label = sample.get("label")
        if label is None:
            raise ValueError("dataset.jsonl entry missing label")
        pos_grid = label.get("pos_grid")
        if pos_grid is None:
            raise ValueError("dataset.jsonl entry missing label.pos_grid")
        slot = label.get("slot")
        gx = pos_grid.get("gx")
        gy = pos_grid.get("gy")
        if slot is None or gx is None or gy is None:
            raise ValueError("dataset.jsonl entry missing slot or pos_grid gx/gy")
        key = (int(slot), int(gx), int(gy))
        counter[key] += 1
        total += 1

    if total == 0:
        raise SystemExit("No samples found in dataset.jsonl")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "policy.pt"

    labels = []
    for (slot, gx, gy), count in counter.most_common():
        labels.append(
            {
                "slot": slot,
                "pos_grid": {"gx": gx, "gy": gy},
                "count": count,
                "prob": count / total,
            }
        )

    model = {
        "schema_version": "policy/1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_samples": total,
        "labels": labels,
    }

    with open(model_path, "w", encoding="utf-8") as handle:
        json.dump(model, handle, separators=(",", ":"))

    print(f"Wrote model to {model_path}")


if __name__ == "__main__":
    main()
