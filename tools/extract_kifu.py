import argparse
import json
import math
from pathlib import Path
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


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


def clamp01(value):
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def get_required(meta, key):
    if key not in meta:
        raise ValueError(f"meta.json missing required key: {key}")
    return meta[key]


def parse_roi(meta):
    roi = get_required(meta, "roi_board")
    for key in ("x1", "y1", "x2", "y2"):
        if key not in roi:
            raise ValueError(f"meta.json roi_board missing required key: {key}")
    x1 = float(roi["x1"])
    y1 = float(roi["y1"])
    x2 = float(roi["x2"])
    y2 = float(roi["y2"])
    if x2 <= x1 or y2 <= y1:
        raise ValueError("meta.json roi_board has invalid dimensions")
    return x1, y1, x2, y2


def compute_pos_norm(x, y, roi):
    x1, y1, x2, y2 = roi
    x_norm = (x - x1) / (x2 - x1)
    y_norm = (y - y1) / (y2 - y1)
    return clamp01(x_norm), clamp01(y_norm)


def compute_pos_grid(x_norm, y_norm, gw, gh):
    gx = int(math.floor(x_norm * gw))
    gy = int(math.floor(y_norm * gh))
    if gx < 0:
        gx = 0
    if gy < 0:
        gy = 0
    if gx >= gw:
        gx = gw - 1
    if gy >= gh:
        gy = gh - 1
    return gx, gy


def build_event(run_id, seq, t_video, slot, pos_norm, pos_grid):
    return {
        "schema_version": "kifu/1",
        "run_id": run_id,
        "seq": seq,
        "event_id": f"{run_id}:{seq}",
        "t": t_video,
        "type": "action",
        "actor": "self",
        "confidence": 1.0,
        "slot": slot,
        "pos_grid": {"gx": pos_grid[0], "gy": pos_grid[1]},
        "pos_norm": {"x": pos_norm[0], "y": pos_norm[1]},
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Extract kifu.jsonl from ops.jsonl.")
    parser.add_argument("--video", required=True, help="Path to video.mp4")
    parser.add_argument("--ops", required=True, help="Path to ops.jsonl")
    parser.add_argument("--meta", required=True, help="Path to meta.json")
    parser.add_argument("--out", required=True, help="Output path for kifu.jsonl")
    parser.add_argument(
        "--default-slot",
        type=int,
        default=-1,
        help="Slot to use when ops entry lacks slot (default: -1)",
    )
    parser.add_argument(
        "--require-slot",
        action="store_true",
        help="Fail if ops entry lacks slot.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    for path in (args.video, args.ops, args.meta):
        if not Path(path).is_file():
            raise SystemExit(f"Missing required file: {path}")

    meta = load_json(args.meta)
    run_id = get_required(meta, "run_id")
    offset_sec = float(get_required(meta, "offset_sec"))
    roi = parse_roi(meta)
    gw = int(get_required(meta, "gw"))
    gh = int(get_required(meta, "gh"))
    if gw <= 0 or gh <= 0:
        raise ValueError("meta.json gw/gh must be positive")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_ops = 0
    total_actions = 0
    missing_slot = 0
    seq = 0

    with open(out_path, "w", encoding="utf-8") as out_handle:
        for op in iter_jsonl(args.ops):
            total_ops += 1
            if op.get("kind") != "tap":
                continue
            if "t_log" not in op or "x" not in op or "y" not in op:
                raise ValueError("ops.jsonl entry missing t_log/x/y")

            t_log = float(op["t_log"])
            x = float(op["x"])
            y = float(op["y"])
            t_video = t_log + offset_sec

            slot = op.get("slot")
            if slot is None:
                if args.require_slot:
                    raise ValueError("ops.jsonl entry missing slot while --require-slot set")
                slot = args.default_slot
                missing_slot += 1
            slot = int(slot)

            pos_norm = compute_pos_norm(x, y, roi)
            pos_grid = compute_pos_grid(pos_norm[0], pos_norm[1], gw, gh)

            event = build_event(run_id, seq, t_video, slot, pos_norm, pos_grid)
            out_handle.write(json.dumps(event, separators=(",", ":")) + "\n")
            seq += 1
            total_actions += 1

    if total_actions == 0:
        print("No action events extracted. Check ops.jsonl.", file=sys.stderr)
    if missing_slot > 0:
        print(
            f"Warning: {missing_slot} action events used default slot {args.default_slot}.",
            file=sys.stderr,
        )
    print(
        f"Extracted {total_actions} actions from {total_ops} ops entries.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
