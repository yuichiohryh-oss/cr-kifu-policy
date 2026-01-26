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


def path_exists(path_value, base_dirs):
    path = Path(path_value)
    if path.is_absolute():
        return path.is_file()
    for base_dir in base_dirs:
        if base_dir and (base_dir / path).is_file():
            return True
    return False


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize dataset.jsonl statistics.")
    parser.add_argument("--dataset", required=True, help="Path to dataset.jsonl")
    parser.add_argument("--meta", help="Optional meta.json for grid sizing")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Check referenced image files exist (relative to cwd if needed)",
    )
    parser.add_argument("--out", help="Optional output JSON path")
    return parser.parse_args()


def main():
    args = parse_args()
    if not Path(args.dataset).is_file():
        raise SystemExit(f"Missing file: {args.dataset}")
    if args.meta and not Path(args.meta).is_file():
        raise SystemExit(f"Missing file: {args.meta}")

    dataset_dir = Path(args.dataset).parent
    meta_dir = Path(args.meta).parent if args.meta else None
    repo_root = None
    if dataset_dir.parent.name == "runs":
        repo_root = dataset_dir.parent.parent
    candidate_bases = [dataset_dir, meta_dir, repo_root, Path.cwd()]

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
    run_id_counts = {}
    t_min = None
    t_max = None
    label_missing = 0
    slot_counts = {}
    grid_counts = {}
    image_missing = 0
    image_missing_field = 0

    for sample in iter_jsonl(args.dataset):
        total += 1
        if sample.get("schema_version") != "dataset/1":
            schema_mismatch += 1

        run_id = sample.get("run_id")
        if run_id is not None:
            increment(run_id_counts, run_id)

        t_action = sample.get("t_action")
        if t_action is not None:
            t_action = float(t_action)
            if t_min is None or t_action < t_min:
                t_min = t_action
            if t_max is None or t_action > t_max:
                t_max = t_action

        image_path = sample.get("image_path")
        if image_path is None:
            image_missing_field += 1
        elif args.check_files:
            if not path_exists(image_path, candidate_bases):
                image_missing += 1

        label = sample.get("label")
        pos_grid = label.get("pos_grid") if label else None
        if (
            label is None
            or "slot" not in label
            or pos_grid is None
            or "gx" not in pos_grid
            or "gy" not in pos_grid
        ):
            label_missing += 1
            continue

        slot = int(label["slot"])
        gx = int(pos_grid["gx"])
        gy = int(pos_grid["gy"])
        increment(slot_counts, slot)
        grid_counts[(gx, gy)] = grid_counts.get((gx, gy), 0) + 1

    grid_summary = None
    if gw is not None and gh is not None:
        grid_summary = {
            "gw": gw,
            "gh": gh,
            "counts": build_grid_counts(grid_counts, gw, gh),
        }

    report = {
        "schema_version": "dataset_stats/1",
        "total": total,
        "schema_mismatch": schema_mismatch,
        "run_id_counts": run_id_counts,
        "t_action_range": summarize_range(t_min, t_max),
        "label_missing": label_missing,
        "slot_counts": slot_counts,
        "grid_counts": {
            f"{gx},{gy}": count for (gx, gy), count in grid_counts.items()
        },
        "grid_matrix": grid_summary,
        "image_missing_field": image_missing_field,
        "image_missing": image_missing,
        "check_files": args.check_files,
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))
    if total == 0:
        print("Warning: no samples in dataset.jsonl", file=sys.stderr)


if __name__ == "__main__":
    main()
