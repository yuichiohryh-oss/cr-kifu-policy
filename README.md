# README.md

## 概要

本リポジトリは、**Clash Royale（クラロワ）の録画動画と操作ログから棋譜（イベント列）を生成し、学習によって次の行動を提案するAIシステム**の研究・実装を目的としています。

内部開発ではクラロワ固有仕様を前提とし、Qiita 等で公開する際にのみ一般化表現へ変換します。

---

## 全体フロー

```
録画動画 + 操作ログ (ops.jsonl)
        ↓
   ランメタ生成 (meta.json)
        ↓
   棋譜生成 (kifu.jsonl)
        ↓
   dataset 生成 (dataset.jsonl)
        ↓
   行動提案モデル学習
        ↓
   次の行動を Top-k 提案
```

---

## ディレクトリ構成

```
.
├── tools/
│   ├── extract_kifu.py      # 動画・操作ログ → 棋譜
│   ├── build_dataset.py     # 棋譜 → 学習用 dataset
│   ├── train_policy.py
│   └── predict_policy.py
├── runs/
│   └── <run_id>/
│       ├── video.mp4
│       ├── ops.jsonl
│       ├── meta.json
│       └── kifu.jsonl
├── models/
├── PROJECT_STATUS.md
├── AGENT.md
└── README.md
```

---

## kifu.jsonl（v1）例

```json
{"schema_version":"kifu/1","run_id":"runA","seq":12,"event_id":"runA:12","t":12.345,"type":"action","actor":"self","confidence":1.0,"slot":2,"pos_grid":{"gx":4,"gy":7}}
```

* `seq` は run 内で単調増加する通番
* `event_id` は `${run_id}:${seq}` を推奨

---

## ops.jsonl（v1）最小例

```json
{"t_log":12.221,"kind":"tap","x":840,"y":1560}
```

* `t_log` は run開始からの秒
* 同期は PROJECT_STATUS.md の式（`t_video = t_log + offset_sec`）で行う

---

## meta.json（v1）最小例

```json
{
  "run_id": "runA",
  "video_path": "runs/runA/video.mp4",
  "ops_path": "runs/runA/ops.jsonl",
  "roi_board": {"x1":0,"y1":110,"x2":720,"y2":1540},
  "gw": 6,
  "gh": 9,
  "offset_sec": 0.12,
  "fps": 60,
  "created_at": "2026-01-20T10:00:00+09:00"
}
```

---

## 最小実行例（Phase 1: action のみ）

```bash
python tools/extract_kifu.py \
  --video runs/runA/video.mp4 \
  --ops runs/runA/ops.jsonl \
  --meta runs/runA/meta.json \
  --out runs/runA/kifu.jsonl
```

---

## dataset 生成（概要）

* 出力: `runs/<run_id>/dataset.jsonl`（または `data/` 配下に集約）
* 分割: run 単位で train/val/test（80/10/10）がデフォルト

---

設計判断・仕様の正は PROJECT_STATUS.md を参照してください。
