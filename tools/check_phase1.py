import argparse
import json
from pathlib import Path
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_args():
    parser = argparse.ArgumentParser(description="Check Phase 1 criteria from score reports.")
    parser.add_argument("--kifu-score", required=True, help="Path to kifu_score.json")
    parser.add_argument(
        "--policy-score", required=True, help="Path to policy_score.json"
    )
    parser.add_argument("--games", type=int, help="Optional number of games")
    parser.add_argument("--min-precision", type=float, default=0.95)
    parser.add_argument("--min-recall", type=float, default=0.90)
    parser.add_argument("--min-topk", type=float, default=0.60)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--min-actions", type=int, default=500)
    parser.add_argument("--min-games", type=int, default=5)
    parser.add_argument("--out", help="Optional output JSON path")
    return parser.parse_args()


def main():
    args = parse_args()
    for path in (args.kifu_score, args.policy_score):
        if not Path(path).is_file():
            raise SystemExit(f"Missing file: {path}")

    kifu_score = load_json(args.kifu_score)
    policy_score = load_json(args.policy_score)

    precision = float(kifu_score.get("precision", 0.0))
    recall = float(kifu_score.get("recall", 0.0))
    gt_total = int(kifu_score.get("gt_total", 0))

    topk_used = int(policy_score.get("topk", 0))
    topk_acc = float(policy_score.get("topk_acc", 0.0))

    checks = []
    checks.append(
        {
            "name": "action_precision",
            "value": precision,
            "threshold": args.min_precision,
            "pass": precision >= args.min_precision,
        }
    )
    checks.append(
        {
            "name": "action_recall",
            "value": recall,
            "threshold": args.min_recall,
            "pass": recall >= args.min_recall,
        }
    )

    topk_name = f"top{args.topk}_acc"
    checks.append(
        {
            "name": topk_name,
            "value": topk_acc,
            "threshold": args.min_topk,
            "pass": topk_acc >= args.min_topk,
            "topk_used": topk_used,
        }
    )

    data_pass = False
    data_reason = []
    if args.games is not None:
        if args.games >= args.min_games:
            data_pass = True
        else:
            data_reason.append(
                f"games {args.games} < min_games {args.min_games}"
            )
    else:
        data_reason.append("games not provided")

    if gt_total >= args.min_actions:
        data_pass = True
    else:
        data_reason.append(
            f"gt_total {gt_total} < min_actions {args.min_actions}"
        )

    checks.append(
        {
            "name": "data_minimum",
            "value": {"games": args.games, "gt_total": gt_total},
            "threshold": {"min_games": args.min_games, "min_actions": args.min_actions},
            "pass": data_pass,
            "notes": data_reason,
        }
    )

    overall = all(check["pass"] for check in checks)
    warnings = []
    if topk_used and topk_used != args.topk:
        warnings.append(
            f"policy_score topk={topk_used} differs from expected {args.topk}"
        )

    report = {
        "schema_version": "phase1_check/1",
        "overall_pass": overall,
        "checks": checks,
        "warnings": warnings,
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))
    if not overall:
        sys.exit(2)


if __name__ == "__main__":
    main()
