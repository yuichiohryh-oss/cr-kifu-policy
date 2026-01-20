# README.md

## 概要

本リポジトリは、**Clash Royale（クラロワ）の録画動画と操作ログから棋譜（イベント列）を生成し、学習によって次の行動を提案するAIシステム**の研究・実装を目的としています。

内部開発ではクラロワ固有仕様を前提とし、Qiita 等で公開する際にのみ一般化表現へ変換します。

---

## 全体フロー

```
録画動画 + 操作ログ
        ↓
   棋譜生成 (kifu.jsonl)
        ↓
   dataset 生成
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
│       ├── kifu.jsonl
│       └── meta.json
├── models/
├── PROJECT_STATUS.md
├── AGENT.md
└── README.md
```

---

## kifu.jsonl フォーマット（v1 抜粋）

```json
{"schema_version":"kifu/1","event_id":"runA:12","run_id":"runA","t":12.345,"seq":12,"type":"action","actor":"self","confidence":1.0,"slot":2,"pos_grid":{"gx":4,"gy":7}}
```

---

## 最小実行例（Phase 1）

```bash
python tools/extract_kifu.py \
  --video runs/runA/video.mp4 \
  --ops runs/runA/ops.jsonl \
  --out runs/runA/kifu.jsonl \
  --gw 6 --gh 9 \
  --offset-sec 0.12
```

---

## 開発方針

* まず action イベントのみを高精度で抽出する
* 棋譜（kifu.jsonl）を唯一の正解データとする
* Phase 1 合格後に spawn / resource を追加する

---

設計判断・仕様の正は PROJECT_STATUS.md を参照してください。
