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
    x1 = int(round(float(roi["x1"])))
    y1 = int(round(float(roi["y1"])))
    x2 = int(round(float(roi["x2"])))
    y2 = int(round(float(roi["y2"])))
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


def parse_args():
    parser = argparse.ArgumentParser(description="Build dataset.jsonl and frames.")
    parser.add_argument("--video", required=True, help="Path to video.mp4")
    parser.add_argument("--meta", required=True, help="Path to meta.json")
    parser.add_argument("--kifu", required=True, help="Path to kifu.jsonl")
    parser.add_argument("--out", required=True, help="Output path for dataset.jsonl")
    parser.add_argument(
        "--frames-dir",
        required=True,
        help="Directory to write ROI frames",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    for path in (args.video, args.meta, args.kifu):
        if not Path(path).is_file():
            raise SystemExit(f"Missing required file: {path}")

    meta = load_json(args.meta)
    run_id = get_required(meta, "run_id", "meta.json")
    roi = parse_roi(meta)
    fps = float(get_required(meta, "fps", "meta.json"))
    if fps <= 0:
        raise ValueError("meta.json fps must be positive")

    cv2 = ensure_cv2()
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"Failed to open video: {args.video}")

    frames_dir = Path(args.frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_samples = 0
    with open(out_path, "w", encoding="utf-8") as out_handle:
        for event in iter_jsonl(args.kifu):
            if event.get("type") != "action":
                continue
            seq = get_required(event, "seq", "kifu.jsonl event")
            t_action = float(get_required(event, "t", "kifu.jsonl event"))
            slot = get_required(event, "slot", "kifu.jsonl event")
            pos_grid = get_required(event, "pos_grid", "kifu.jsonl event")
            gx = get_required(pos_grid, "gx", "kifu.jsonl pos_grid")
            gy = get_required(pos_grid, "gy", "kifu.jsonl pos_grid")

            frame_index = int(round(t_action * fps))
            if frame_index < 0:
                raise ValueError(f"Negative frame index for seq {seq}")

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"Failed to read frame {frame_index} for seq {seq}")

            height, width = frame.shape[:2]
            x1, y1, x2, y2 = roi
            x1 = max(0, min(x1, width - 1))
            x2 = max(x1 + 1, min(x2, width))
            y1 = max(0, min(y1, height - 1))
            y2 = max(y1 + 1, min(y2, height))
            roi_frame = frame[y1:y2, x1:x2]
            if roi_frame.size == 0:
                raise ValueError(f"Empty ROI for seq {seq}")

            frame_name = f"{int(seq):06d}.png"
            frame_path = frames_dir / frame_name
            if not cv2.imwrite(str(frame_path), roi_frame):
                raise ValueError(f"Failed to write frame {frame_path}")

            record = {
                "schema_version": "dataset/1",
                "sample_id": f"{run_id}:{seq}",
                "run_id": run_id,
                "t_action": t_action,
                "image_path": frame_path.as_posix(),
                "label": {"slot": int(slot), "pos_grid": {"gx": int(gx), "gy": int(gy)}},
                "meta_ref": Path(args.meta).as_posix(),
            }
            out_handle.write(json.dumps(record, separators=(",", ":")) + "\n")
            total_samples += 1

    cap.release()
    if total_samples == 0:
        print("No action samples written. Check kifu.jsonl.", file=sys.stderr)
    else:
        print(f"Wrote {total_samples} samples.", file=sys.stderr)


if __name__ == "__main__":
    main()
