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


def parse_args():
    parser = argparse.ArgumentParser(description="Score predicted kifu against ground truth.")
    parser.add_argument("--pred", required=True, help="Predicted kifu.jsonl")
    parser.add_argument("--gt", required=True, help="Ground-truth kifu.jsonl")
    parser.add_argument(
        "--time-tol-ms",
        type=float,
        default=100.0,
        help="Time tolerance in ms for matching (default: 100)",
    )
    parser.add_argument("--out", help="Optional output JSON path")
    return parser.parse_args()


def load_actions(path):
    actions = []
    for event in iter_jsonl(path):
        if event.get("type") != "action":
            continue
        if "t" not in event or "slot" not in event or "pos_grid" not in event:
            raise ValueError(f"{path}: action event missing t/slot/pos_grid")
        pos_grid = event["pos_grid"]
        if "gx" not in pos_grid or "gy" not in pos_grid:
            raise ValueError(f"{path}: action event missing pos_grid gx/gy")
        actions.append(
            {
                "t": float(event["t"]),
                "slot": int(event["slot"]),
                "gx": int(pos_grid["gx"]),
                "gy": int(pos_grid["gy"]),
            }
        )
    return actions


def index_by_label(actions):
    label_map = {}
    for action in actions:
        key = (action["slot"], action["gx"], action["gy"])
        label_map.setdefault(key, []).append(action)
    for key in label_map:
        label_map[key].sort(key=lambda item: item["t"])
    return label_map


def match_actions(pred_actions, gt_index, tol_sec):
    matched = 0
    time_deltas = []
    for pred in pred_actions:
        key = (pred["slot"], pred["gx"], pred["gy"])
        candidates = gt_index.get(key)
        if not candidates:
            continue
        best_idx = None
        best_dt = None
        upper = pred["t"] + tol_sec
        for idx, gt in enumerate(candidates):
            dt = abs(gt["t"] - pred["t"])
            if gt["t"] > upper and best_dt is not None:
                break
            if dt <= tol_sec and (best_dt is None or dt < best_dt):
                best_dt = dt
                best_idx = idx
        if best_idx is not None:
            candidates.pop(best_idx)
            matched += 1
            time_deltas.append(best_dt)
    return matched, time_deltas


def summarize_time_deltas(time_deltas):
    if not time_deltas:
        return None
    values = [delta * 1000.0 for delta in time_deltas]
    return {
        "min_ms": min(values),
        "max_ms": max(values),
        "avg_ms": sum(values) / len(values),
    }


def main():
    args = parse_args()
    for path in (args.pred, args.gt):
        if not Path(path).is_file():
            raise SystemExit(f"Missing file: {path}")

    tol_sec = max(0.0, args.time_tol_ms / 1000.0)
    pred_actions = load_actions(args.pred)
    gt_actions = load_actions(args.gt)

    pred_actions.sort(key=lambda item: item["t"])
    gt_index = index_by_label(gt_actions)

    matched, time_deltas = match_actions(pred_actions, gt_index, tol_sec)
    pred_total = len(pred_actions)
    gt_total = len(gt_actions)

    precision = matched / pred_total if pred_total else 0.0
    recall = matched / gt_total if gt_total else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    report = {
        "schema_version": "kifu_score/1",
        "pred_total": pred_total,
        "gt_total": gt_total,
        "matched": matched,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "time_tolerance_ms": args.time_tol_ms,
        "match_mode": "time+slot+pos_grid",
        "match_time_ms": summarize_time_deltas(time_deltas),
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))
    if pred_total == 0 or gt_total == 0:
        print("Warning: empty pred or gt actions.", file=sys.stderr)


if __name__ == "__main__":
    main()
