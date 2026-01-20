# README.md

## 概要

本リポジトリは、**Clash Royale（クラロワ）の録画動画と操作ログから棋譜（イベント列）を生成し、学習によって次の行動を提案するAIシステム**の研究・実装を目的としています。

内部開発ではクラロワ固有仕様を前提とし、Qiita 等で公開する際にのみ一般化表現へ変換します。

---

## 全体フロー（正式ルート）

```
(video.mp4 + ops.jsonl + meta.json)
        ↓
   棋譜生成 (kifu.jsonl)
        ↓
   dataset 生成 (dataset.jsonl + frames/)
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
│   ├── extract_kifu.py      # video + ops + meta → kifu
│   ├── build_dataset.py     # kifu + meta + video → dataset + frames
│   ├── train_policy.py
│   └── predict_policy.py
├── runs/
│   └── <run_id>/
│       ├── video.mp4
│       ├── ops.jsonl
│       ├── meta.json
│       ├── kifu.jsonl
│       ├── dataset.jsonl
│       └── frames/
│           ├── 000000.png
│           ├── 000001.png
│           └── ...
├── models/
├── PROJECT_STATUS.md
├── AGENT.md
└── README.md
```

---

## ops.jsonl（v1）

### 最小例

```json
{"t_log":12.221,"kind":"tap","x":840,"y":1560}
```

### 座標系（重要）

* `x`,`y` は **動画フレーム座標（px）**（原点=左上、x→右、y→下）
* `t_log` は run開始からの秒

---

## meta.json（v1）

### 最小例

```json
{
  "run_id": "runA",
  "video_path": "runs/runA/video.mp4",
  "ops_path": "runs/runA/ops.jsonl",
  "video_w": 720,
  "video_h": 1600,
  "roi_board": {"x1":0,"y1":110,"x2":720,"y2":1540},
  "gw": 6,
  "gh": 9,
  "offset_sec": 0.12,
  "fps": 60,
  "created_at": "2026-01-20T10:00:00+09:00"
}
```

---

## frames/（v1.3 で確定）

* **frames は `runs/<run_id>/frames/` に生成**
* **build_dataset.py が video から必要フレームを切り出して生成**（事前生成不要）
* 命名: `frames/{seq:06d}.png`（dataset の sample_id と対応）

---

## kifu.jsonl（v1）

```json
{"schema_version":"kifu/1","run_id":"runA","seq":12,"event_id":"runA:12","t":12.345,"type":"action","actor":"self","confidence":1.0,"slot":2,"pos_grid":{"gx":4,"gy":7}}
```

---

## dataset.jsonl（v1 最小）

```json
{
  "schema_version": "dataset/1",
  "sample_id": "runA:12",
  "run_id": "runA",
  "t_action": 12.345,
  "image_path": "runs/runA/frames/000012.png",
  "label": {"slot": 2, "pos_grid": {"gx": 4, "gy": 7}},
  "meta_ref": "runs/runA/meta.json"
}
```

---

## 最小実行例

### 1) 棋譜生成（Phase 1: action のみ）

```bash
python tools/extract_kifu.py \
  --video runs/runA/video.mp4 \
  --ops runs/runA/ops.jsonl \
  --meta runs/runA/meta.json \
  --out runs/runA/kifu.jsonl
```

### 2) dataset + frames 生成

```bash
python tools/build_dataset.py \
  --video runs/runA/video.mp4 \
  --meta runs/runA/meta.json \
  --kifu runs/runA/kifu.jsonl \
  --out runs/runA/dataset.jsonl \
  --frames-dir runs/runA/frames
```

---

設計判断・仕様の正は PROJECT_STATUS.md を参照してください。
