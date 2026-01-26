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


def increment(counter, key):
    counter[key] = counter.get(key, 0) + 1


def summarize_range(value_min, value_max):
    if value_min is None or value_max is None:
        return None
    return {"min": value_min, "max": value_max}


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize ops.jsonl statistics.")
    parser.add_argument("--ops", required=True, help="Path to ops.jsonl")
    parser.add_argument("--out", help="Optional output JSON path")
    return parser.parse_args()


def main():
    args = parse_args()
    if not Path(args.ops).is_file():
        raise SystemExit(f"Missing file: {args.ops}")

    total = 0
    kind_counts = {}
    t_min = None
    t_max = None
    tap_total = 0
    tap_x_min = None
    tap_x_max = None
    tap_y_min = None
    tap_y_max = None
    tap_missing_fields = 0
    t_log_prev = None
    t_log_nonmonotonic = 0

    for op in iter_jsonl(args.ops):
        total += 1
        kind = op.get("kind")
        if kind is not None:
            increment(kind_counts, kind)

        t_log = op.get("t_log")
        if t_log is not None:
            t_log = float(t_log)
            if t_min is None or t_log < t_min:
                t_min = t_log
            if t_max is None or t_log > t_max:
                t_max = t_log
            if t_log_prev is not None and t_log < t_log_prev:
                t_log_nonmonotonic += 1
            t_log_prev = t_log

        if kind != "tap":
            continue
        tap_total += 1
        if "x" not in op or "y" not in op:
            tap_missing_fields += 1
            continue
        x_val = float(op["x"])
        y_val = float(op["y"])
        if tap_x_min is None or x_val < tap_x_min:
            tap_x_min = x_val
        if tap_x_max is None or x_val > tap_x_max:
            tap_x_max = x_val
        if tap_y_min is None or y_val < tap_y_min:
            tap_y_min = y_val
        if tap_y_max is None or y_val > tap_y_max:
            tap_y_max = y_val

    report = {
        "schema_version": "ops_stats/1",
        "total": total,
        "kind_counts": kind_counts,
        "t_log_range": summarize_range(t_min, t_max),
        "t_log_nonmonotonic": t_log_nonmonotonic,
        "tap": {
            "total": tap_total,
            "missing_fields": tap_missing_fields,
            "x_range": summarize_range(tap_x_min, tap_x_max),
            "y_range": summarize_range(tap_y_min, tap_y_max),
        },
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))
    if total == 0:
        print("Warning: no ops in ops.jsonl", file=sys.stderr)


if __name__ == "__main__":
    main()
