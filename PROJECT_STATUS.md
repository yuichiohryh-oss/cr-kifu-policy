# PROJECT_STATUS.md

## プロジェクト概要

本プロジェクトは、**Clash Royale（クラロワ）の録画動画と操作ログから行動・状態イベントを抽出し、棋譜（イベント列）として構造化し、学習・推論によって次の行動を提案するAIシステム**を構築することを目的とする。

内部開発ではゲーム固有名詞・UI仕様・数値仕様をそのまま扱い、Qiita 等の外部公開時のみ一般化表現へ変換する。

---

## 最優先テーマ

### 🎯 棋譜（イベント列）中心のパイプライン

**動画 → 棋譜（kifu.jsonl） → dataset → 学習 → 提案** を唯一の正式ルートとする。

---

## 棋譜（kifu.jsonl）正式仕様（v1）

### 基本方針

* 1行 = 1イベント（JSONL）
* 時刻 `t` は **動画開始からの秒（float, sec）**
* 同一 `t` 内の順序は `seq` で安定化（ソートキー `(t, seq)`）
* **schema_version を必須** とし後方互換を担保

### 共通フィールド（必須）

| key            | type    | 内容                               |
| -------------- | ------- | -------------------------------- |
| schema_version | string  | "kifu/1"                         |
| event_id       | string  | 一意ID（run_id:seq）                 |
| run_id         | string  | セッション識別子                         |
| t              | number  | 動画開始からの秒                         |
| seq            | integer | 同時刻内の順序                          |
| type           | string  | action / spawn / resource / meta |
| actor          | string  | self / enemy / system            |
| confidence     | number  | [0,1]                            |

### action イベント（Phase 1 必須）

| key      | type    | 必須 | 内容                   |
| -------- | ------- | -: | -------------------- |
| slot     | integer |  ✓ | 手札スロット（0–3）          |
| pos_grid | object  |  ✓ | { gx:int, gy:int }   |
| pos_norm | object  | 任意 | { x:float, y:float } |
| raw      | object  | 任意 | デバッグ用                |

---

## 座標系

* pos_norm：盤面ROI基準で正規化
* pos_grid：盤面ROIを gw×gh に分割した離散グリッド

---

## 動画 × 操作ログ同期（Phase 1）

* 動画開始 = t=0
* 固定オフセット方式を採用

```
t_video = t_log + offset_sec
```

* offset_sec は CLI で指定
* 許容誤差：±100ms（最大 ±200ms）

---

## Phase 1 合格基準

* action precision ≥ 0.95
* action recall ≥ 0.90（努力目標）
* Top-3 accuracy ≥ 0.60
* 最小データ量：5試合 or 500 action

---

## 開発スタック

* Python 3.11
* PyTorch
* OpenCV + ffmpeg
* numpy / tqdm / pydantic / rich

---

## データ運用

* runs/<run_id>/ 単位で管理
* 動画・frames は Git 管理外
* kifu.jsonl / meta.json は Git 管理可
