# README.md

> Doc revision: **rev 1.3**
>
> ※ この **rev** はドキュメント／仕様書の改訂番号です。`schema_version`（例: `kifu/1`, `dataset/1`）とは**別物**です。

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
     ※入力: kifu.jsonl + video.mp4 + meta.json
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
│   ├── build_dataset.py     # kifu + video + meta → dataset + frames
│   ├── validate_run.py      # video + ops + meta (+kifu) validation
│   ├── score_kifu.py         # pred kifu vs gt kifu scoring
│   ├── stats_kifu.py         # kifu stats summary
│   ├── stats_dataset.py      # dataset stats summary
│   ├── stats_ops.py          # ops stats summary
│   ├── score_policy.py       # policy top-k scoring
│   ├── check_phase1.py       # phase 1 criteria check
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

## ops.jsonl（schema v1）

### 最小例

```json
{"t_log":12.221,"kind":"tap","x":360,"y":780}
```

> 例の `x=360` は、meta 例の `video_w=720` に対して **0–719 の範囲内**に収まる値です。

### フィールド

* `t_log`（必須）: run開始からの秒（float, sec）
* `kind`（必須）: 入力種別（v1: `tap`, `key`, `mouse_move`）

  * Phase 1 実装は `tap` のみ解釈すればOK
* `x`,`y`（必須）: **動画フレーム座標（px）**（原点=左上、x→右、y→下）

---

## meta.json（schema v1）

### 同期

動画時刻と操作ログ時刻は次式で対応づけます。

```text
t_video = t_log + offset_sec
```

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

## frames/（rev 1.3 で確定）

* **frames は `runs/<run_id>/frames/` に生成**
* **build_dataset.py が video から必要フレームを切り出して生成**（事前生成不要）
* 命名: `frames/{seq:06d}.png`
* **画像は盤面ROIを切り出した ROI 画像**（フルフレームではない）

---

## kifu.jsonl（schema v1）

```json
{"schema_version":"kifu/1","run_id":"runA","seq":12,"event_id":"runA:12","t":12.345,"type":"action","actor":"self","confidence":1.0,"slot":2,"pos_grid":{"gx":4,"gy":7}}
```

---

## dataset.jsonl（schema v1・最小）

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

### 0) runs/<run_id>/ の最小セット（例: run_20260120_01）

```
runs/run_20260120_01/
├── video.mp4
├── ops.jsonl
└── meta.json
```

> meta.json の `run_id` と `*_path` は、このディレクトリ名に合わせる

### 0.5) run validation (optional)

```bash
python tools/validate_run.py \
  --video runs/run_20260120_01/video.mp4 \
  --ops runs/run_20260120_01/ops.jsonl \
  --meta runs/run_20260120_01/meta.json \
  --kifu runs/run_20260120_01/kifu.jsonl \
  --out runs/run_20260120_01/run_check.json
```

### 1) 棋譜生成（Phase 1: action のみ）

```bash
python tools/extract_kifu.py \
  --video runs/run_20260120_01/video.mp4 \
  --ops runs/run_20260120_01/ops.jsonl \
  --meta runs/run_20260120_01/meta.json \
  --out runs/run_20260120_01/kifu.jsonl
```

### 1.2) ops stats (optional)

```bash
python tools/stats_ops.py \
  --ops runs/run_20260120_01/ops.jsonl \
  --out runs/run_20260120_01/ops_stats.json
```

### 1.5) kifu score (optional)

```bash
python tools/score_kifu.py \
  --pred runs/run_20260120_01/kifu.jsonl \
  --gt runs/run_20260120_01/kifu_gt.jsonl \
  --time-tol-ms 100 \
  --out runs/run_20260120_01/kifu_score.json
```

### 1.6) kifu stats (optional)

```bash
python tools/stats_kifu.py \
  --kifu runs/run_20260120_01/kifu.jsonl \
  --meta runs/run_20260120_01/meta.json \
  --out runs/run_20260120_01/kifu_stats.json
```

### 2) dataset + frames 生成

```bash
python tools/build_dataset.py \
  --video runs/run_20260120_01/video.mp4 \
  --meta runs/run_20260120_01/meta.json \
  --kifu runs/run_20260120_01/kifu.jsonl \
  --out runs/run_20260120_01/dataset.jsonl \
  --frames-dir runs/run_20260120_01/frames
```

### 2.5) dataset validation (optional)

```bash
python tools/validate_run.py \
  --video runs/run_20260120_01/video.mp4 \
  --ops runs/run_20260120_01/ops.jsonl \
  --meta runs/run_20260120_01/meta.json \
  --dataset runs/run_20260120_01/dataset.jsonl \
  --check-files
```

### 2.6) dataset stats (optional)

```bash
python tools/stats_dataset.py \
  --dataset runs/run_20260120_01/dataset.jsonl \
  --meta runs/run_20260120_01/meta.json \
  --check-files \
  --out runs/run_20260120_01/dataset_stats.json
```

### 3) end-to-end smoke run

```bash
python tools/extract_kifu.py \
  --video runs/run_20260120_01/video.mp4 \
  --ops runs/run_20260120_01/ops.jsonl \
  --meta runs/run_20260120_01/meta.json \
  --out runs/run_20260120_01/kifu.jsonl

python tools/build_dataset.py \
  --video runs/run_20260120_01/video.mp4 \
  --meta runs/run_20260120_01/meta.json \
  --kifu runs/run_20260120_01/kifu.jsonl \
  --out runs/run_20260120_01/dataset.jsonl \
  --frames-dir runs/run_20260120_01/frames

python tools/train_policy.py \
  --dataset runs/run_20260120_01/dataset.jsonl \
  --out models/run_20260120_01

python tools/predict_policy.py \
  --model models/run_20260120_01/policy.pt \
  --video runs/run_20260120_01/video.mp4 \
  --meta runs/run_20260120_01/meta.json
```

### 3.5) policy score (optional)

```bash
python tools/score_policy.py \
  --model models/run_20260120_01/policy.pt \
  --dataset runs/run_20260120_01/dataset.jsonl \
  --topk 3 \
  --out models/run_20260120_01/policy_score.json
```

### 4) phase 1 check (optional)

```bash
python tools/check_phase1.py \
  --kifu-score runs/run_20260120_01/kifu_score.json \
  --policy-score models/run_20260120_01/policy_score.json \
  --games 5 \
  --out runs/run_20260120_01/phase1_check.json
```

---

設計判断・仕様の正は PROJECT_STATUS.md を参照してください。
