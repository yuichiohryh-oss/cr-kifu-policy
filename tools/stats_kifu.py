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


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def increment(counter, key):
    counter[key] = counter.get(key, 0) + 1


def summarize_range(value_min, value_max):
    if value_min is None or value_max is None:
        return None
    return {"min": value_min, "max": value_max}


def build_grid_counts(grid_counts, gw, gh):
    grid = [[0 for _ in range(gw)] for _ in range(gh)]
    for key, count in grid_counts.items():
        gx, gy = key
        if 0 <= gx < gw and 0 <= gy < gh:
            grid[gy][gx] = count
    return grid


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize kifu.jsonl statistics.")
    parser.add_argument("--kifu", required=True, help="Path to kifu.jsonl")
    parser.add_argument("--meta", help="Optional meta.json for grid sizing")
    parser.add_argument("--out", help="Optional output JSON path")
    return parser.parse_args()


def main():
    args = parse_args()
    if not Path(args.kifu).is_file():
        raise SystemExit(f"Missing file: {args.kifu}")
    if args.meta and not Path(args.meta).is_file():
        raise SystemExit(f"Missing file: {args.meta}")

    gw = None
    gh = None
    if args.meta:
        meta = load_json(args.meta)
        gw = int(meta.get("gw", 0))
        gh = int(meta.get("gh", 0))
        if gw <= 0 or gh <= 0:
            print("Warning: invalid gw/gh in meta.json", file=sys.stderr)
            gw = None
            gh = None

    total = 0
    schema_mismatch = 0
    type_counts = {}
    actor_counts = {}
    slot_counts = {}
    grid_counts = {}
    t_min = None
    t_max = None
    action_t_min = None
    action_t_max = None
    action_t_sum = 0.0
    action_total = 0

    for event in iter_jsonl(args.kifu):
        total += 1
        if event.get("schema_version") != "kifu/1":
            schema_mismatch += 1

        event_type = event.get("type")
        if event_type is not None:
            increment(type_counts, event_type)

        actor = event.get("actor")
        if actor is not None:
            increment(actor_counts, actor)

        t_val = event.get("t")
        if t_val is not None:
            t_val = float(t_val)
            if t_min is None or t_val < t_min:
                t_min = t_val
            if t_max is None or t_val > t_max:
                t_max = t_val

        if event_type != "action":
            continue

        action_total += 1
        if t_val is not None:
            if action_t_min is None or t_val < action_t_min:
                action_t_min = t_val
            if action_t_max is None or t_val > action_t_max:
                action_t_max = t_val
            action_t_sum += t_val

        slot = event.get("slot")
        if slot is not None:
            increment(slot_counts, int(slot))

        pos_grid = event.get("pos_grid")
        if pos_grid and "gx" in pos_grid and "gy" in pos_grid:
            gx = int(pos_grid["gx"])
            gy = int(pos_grid["gy"])
            grid_counts[(gx, gy)] = grid_counts.get((gx, gy), 0) + 1

    action_t_avg = (action_t_sum / action_total) if action_total else None
    grid_summary = None
    if gw is not None and gh is not None:
        grid_summary = {
            "gw": gw,
            "gh": gh,
            "counts": build_grid_counts(grid_counts, gw, gh),
        }

    report = {
        "schema_version": "kifu_stats/1",
        "total": total,
        "schema_mismatch": schema_mismatch,
        "type_counts": type_counts,
        "actor_counts": actor_counts,
        "t_range": summarize_range(t_min, t_max),
        "action": {
            "total": action_total,
            "t_range": summarize_range(action_t_min, action_t_max),
            "t_avg": action_t_avg,
            "slot_counts": slot_counts,
            "grid_counts": {
                f"{gx},{gy}": count for (gx, gy), count in grid_counts.items()
            },
            "grid_matrix": grid_summary,
        },
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))

    if total == 0:
        print("Warning: no events in kifu.jsonl", file=sys.stderr)


if __name__ == "__main__":
    main()
