import argparse
import json
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


def get_required(data, key, context):
    if key not in data:
        raise ValueError(f"{context} missing required key: {key}")
    return data[key]


def parse_roi(meta):
    roi = get_required(meta, "roi_board", "meta.json")
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


def ensure_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "opencv-python is required. Install with: pip install opencv-python"
        ) from exc
    return cv2


def read_video_info(video_path):
    cv2 = ensure_cv2()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Failed to open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = (frame_count / fps) if fps > 0 else 0.0
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_sec": duration,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Validate run inputs and sync offset.")
    parser.add_argument("--video", required=True, help="Path to video.mp4")
    parser.add_argument("--ops", required=True, help="Path to ops.jsonl")
    parser.add_argument("--meta", required=True, help="Path to meta.json")
    parser.add_argument("--kifu", help="Optional kifu.jsonl to validate")
    parser.add_argument("--dataset", help="Optional dataset.jsonl to validate")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Check referenced dataset image files exist",
    )
    parser.add_argument(
        "--sync-window-ms",
        type=float,
        default=100.0,
        help="Allowed sync drift window in milliseconds (default: 100)",
    )
    parser.add_argument("--out", help="Optional JSON report path")
    return parser.parse_args()


def summarize_range(value_min, value_max):
    if value_min is None or value_max is None:
        return None
    return {"min": value_min, "max": value_max}


def main():
    args = parse_args()
    for path in (args.video, args.ops, args.meta):
        if not Path(path).is_file():
            raise SystemExit(f"Missing required file: {path}")
    if args.kifu and not Path(args.kifu).is_file():
        raise SystemExit(f"Missing kifu file: {args.kifu}")
    if args.dataset and not Path(args.dataset).is_file():
        raise SystemExit(f"Missing dataset file: {args.dataset}")

    meta = load_json(args.meta)
    run_id = get_required(meta, "run_id", "meta.json")
    offset_sec = float(get_required(meta, "offset_sec", "meta.json"))
    video_w = int(get_required(meta, "video_w", "meta.json"))
    video_h = int(get_required(meta, "video_h", "meta.json"))
    fps_meta = float(get_required(meta, "fps", "meta.json"))
    gw = int(get_required(meta, "gw", "meta.json"))
    gh = int(get_required(meta, "gh", "meta.json"))
    roi = parse_roi(meta)

    errors = []
    warnings = []

    if gw <= 0 or gh <= 0:
        errors.append("meta.json gw/gh must be positive")

    roi_x1, roi_y1, roi_x2, roi_y2 = roi
    if roi_x1 < 0 or roi_y1 < 0 or roi_x2 > video_w or roi_y2 > video_h:
        warnings.append("roi_board extends outside video bounds")

    video_info = read_video_info(args.video)
    if video_info["width"] and video_info["width"] != video_w:
        warnings.append("meta.json video_w does not match actual video width")
    if video_info["height"] and video_info["height"] != video_h:
        warnings.append("meta.json video_h does not match actual video height")
    if video_info["fps"] and fps_meta and abs(video_info["fps"] - fps_meta) > 0.5:
        warnings.append("meta.json fps does not match actual video fps")

    sync_window_sec = max(0.0, args.sync_window_ms / 1000.0)
    duration_sec = video_info["duration_sec"]

    ops_total = 0
    ops_tap = 0
    tap_out_of_bounds = 0
    tap_out_of_range = 0
    t_video_min = None
    t_video_max = None

    for op in iter_jsonl(args.ops):
        ops_total += 1
        if "t_log" not in op:
            errors.append("ops.jsonl entry missing t_log")
            continue
        if op.get("kind") != "tap":
            continue
        if "x" not in op or "y" not in op:
            errors.append("ops.jsonl tap entry missing x/y")
            continue

        ops_tap += 1
        t_log = float(op["t_log"])
        t_video = t_log + offset_sec
        if t_video_min is None or t_video < t_video_min:
            t_video_min = t_video
        if t_video_max is None or t_video > t_video_max:
            t_video_max = t_video

        x = float(op["x"])
        y = float(op["y"])
        if x < 0 or x >= video_w or y < 0 or y >= video_h:
            tap_out_of_bounds += 1

        if duration_sec > 0:
            if t_video < -sync_window_sec or t_video > duration_sec + sync_window_sec:
                tap_out_of_range += 1

    kifu_stats = None
    if args.kifu:
        kifu_total = 0
        kifu_action = 0
        seq_prev = None
        seq_issues = 0
        run_id_mismatch = 0
        schema_mismatch = 0
        for event in iter_jsonl(args.kifu):
            kifu_total += 1
            if event.get("schema_version") != "kifu/1":
                schema_mismatch += 1
            if event.get("run_id") != run_id:
                run_id_mismatch += 1
            seq = event.get("seq")
            if seq is not None:
                seq = int(seq)
                if seq_prev is not None and seq <= seq_prev:
                    seq_issues += 1
                seq_prev = seq
            if event.get("type") == "action":
                kifu_action += 1
        kifu_stats = {
            "total": kifu_total,
            "action": kifu_action,
            "schema_mismatch": schema_mismatch,
            "run_id_mismatch": run_id_mismatch,
            "seq_issues": seq_issues,
        }

    dataset_stats = None
    if args.dataset:
        dataset_total = 0
        dataset_schema_mismatch = 0
        dataset_run_id_mismatch = 0
        dataset_missing_fields = 0
        dataset_missing_images = 0
        for sample in iter_jsonl(args.dataset):
            dataset_total += 1
            if sample.get("schema_version") != "dataset/1":
                dataset_schema_mismatch += 1
            if sample.get("run_id") != run_id:
                dataset_run_id_mismatch += 1

            if "sample_id" not in sample or "image_path" not in sample:
                dataset_missing_fields += 1
                continue

            label = sample.get("label")
            pos_grid = label.get("pos_grid") if label else None
            if (
                label is None
                or "slot" not in label
                or pos_grid is None
                or "gx" not in pos_grid
                or "gy" not in pos_grid
            ):
                dataset_missing_fields += 1
                continue

            if args.check_files:
                image_path = Path(sample["image_path"])
                if not image_path.is_file():
                    dataset_missing_images += 1

        if dataset_missing_fields > 0:
            errors.append(
                f"dataset.jsonl has {dataset_missing_fields} entries missing fields"
            )
        if args.check_files and dataset_missing_images > 0:
            errors.append(
                f"dataset.jsonl has {dataset_missing_images} missing image files"
            )

        dataset_stats = {
            "total": dataset_total,
            "schema_mismatch": dataset_schema_mismatch,
            "run_id_mismatch": dataset_run_id_mismatch,
            "missing_fields": dataset_missing_fields,
            "missing_images": dataset_missing_images,
            "check_files": args.check_files,
        }

    report = {
        "schema_version": "run_check/1",
        "run_id": run_id,
        "meta": {
            "video_w": video_w,
            "video_h": video_h,
            "fps": fps_meta,
            "offset_sec": offset_sec,
            "gw": gw,
            "gh": gh,
            "roi_board": {
                "x1": roi_x1,
                "y1": roi_y1,
                "x2": roi_x2,
                "y2": roi_y2,
            },
        },
        "video": video_info,
        "ops": {
            "total": ops_total,
            "tap": ops_tap,
            "tap_out_of_bounds": tap_out_of_bounds,
            "tap_out_of_range": tap_out_of_range,
            "t_video_range": summarize_range(t_video_min, t_video_max),
            "sync_window_ms": args.sync_window_ms,
        },
        "kifu": kifu_stats,
        "dataset": dataset_stats,
        "warnings": warnings,
        "errors": errors,
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
