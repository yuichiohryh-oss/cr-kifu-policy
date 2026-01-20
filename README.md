# cr-kifu-policy

# README.md

## 概要

本リポジトリは、**Clash Royale（クラロワ）の録画動画から行動と状態を棋譜（イベント列）として抽出し、学習によって次の行動を提案するAIシステム**の研究・実装を目的としています。

内部開発ではゲーム固有仕様を前提とし、Qiita 等で公開する際にのみ一般化表現へ変換します。

---

## 全体フロー

```
録画動画 + 操作ログ
        ↓
   棋譜生成 (kifu.jsonl)
        ↓
   学習用dataset生成
        ↓
   行動提案モデル学習
        ↓
   次の行動をTop-k提案
```

---

## ディレクトリ構成（想定）

```
.
├── tools/
│   ├── extract_kifu.py      # 動画・ログ → 棋譜
│   ├── build_dataset.py     # 棋譜 + フレーム → dataset
│   ├── train_policy.py
│   └── predict_policy.py
├── data/
│   ├── kifu/
│   ├── dataset/
│   └── frames/
├── models/
├── PROJECT_STATUS.md
├── AGENT.md
└── README.md
```

---

## 棋譜（kifu.jsonl）フォーマット例

```json
{"t":12.34,"type":"action","actor":"self","slot":2,"pos":{"x":0.62,"y":0.83}}
{"t":12.50,"type":"spawn","actor":"self","kind":"unit","track_id":18}
{"t":12.90,"type":"resource","actor":"self","value":6.5}
```

---

## 開発の進め方（推奨）

1. `action` イベントのみの棋譜生成を完成させる
2. 棋譜を正解ラベルとして提案モデルを学習
3. `spawn` / `resource` を段階的に追加
4. 提案品質を見ながら特徴量・モデルを拡張

---

## このプロジェクトの思想

* 人間が理解できる中間表現（棋譜）を捨てない
* 学習とデバッグを同じ成果物で回す
* AIを「魔法」ではなく「観測と提案の拡張装置」として扱う

---

設計判断・優先度は必ず PROJECT_STATUS.md を参照してください。
