# PROJECT_STATUS.md

## プロジェクト概要

本プロジェクトは、**Clash Royale（クラロワ）の録画動画と操作ログから行動・状態イベントを抽出し、棋譜（イベント列）として構造化し、学習・推論によって次の行動を提案するAIシステム**を構築することを目的とする。

内部開発ではゲーム固有名詞・UI仕様・数値仕様をそのまま扱い、Qiita 等の外部公開時のみ一般化表現へ変換する。

---

## 最優先テーマ

### 🎯 棋譜（イベント列）中心のパイプライン

**動画 → 棋譜（kifu.jsonl） → dataset → 学習 → 提案** を唯一の正式ルートとする。

---

## kifu.jsonl 正式仕様（v1）

### 基本方針

* 1行 = 1イベント（JSONL）
* 時刻 `t` は **動画開始からの秒（float, sec）**
* **`seq` は run 内で単調増加する通番（0,1,2,...)**（同時刻の順序安定化も兼ねる）
* ソートキーは `(t, seq)`
* **`schema_version` を必須** とし後方互換を担保

### 共通フィールド（必須）

| key            | type    | 内容                           |
| -------------- | ------- | ---------------------------- |
| schema_version | string  | "kifu/1"                     |
| run_id         | string  | セッション識別子                     |
| seq            | integer | run 内通番（単調増加・一意）             |
| event_id       | string  | 一意ID（推奨: `${run_id}:${seq}`） |
| t              | number  | 動画開始からの秒                     |
| type           | string  | action / spawn / resource    |
| actor          | string  | self / enemy / system        |
| confidence     | number  | [0,1]                        |

### action イベント（Phase 1 必須）

| key      | type    | 必須 | 内容                             |
| -------- | ------- | -: | ------------------------------ |
| slot     | integer |  ✓ | 手札スロット（0–3）                    |
| pos_grid | object  |  ✓ | { gx:int, gy:int }             |
| pos_norm | object  | 任意 | { x:float, y:float }（盤面ROI正規化） |
| raw      | object  | 任意 | 元ログ/デバッグ用                      |

### spawn / resource（Phase 2+）

* spawn（例）: kind(unit/spell/effect/unknown), track_id, bbox_norm
* resource（例）: value(0–10), max(10)

---

## 座標系（v1）

### pos_norm

* 基準: **盤面ROI**
* 原点: 左上 (0,0)
* 軸方向: x は右へ増加、y は下へ増加
* 範囲: 通常は [0,1]。範囲外は **clamp して [0,1] に収める**

### pos_grid

* 盤面ROIを `gw × gh` に等分
* 原点: 左上 (0,0)
* 軸方向: gx は右へ増加、gy は下へ増加
* 変換:

  * `gx = floor(x * gw)`
  * `gy = floor(y * gh)`
  * 端の丸めで gw/gh になった場合は `min(gx, gw-1)`, `min(gy, gh-1)` にする
* 範囲外: pos_norm 同様に clamp → floor

**gw/gh/ROI は meta.json に必ず保存する（後述）。**

---

## 動画 × 操作ログ同期（v1）

### 方針（Phase 1）

* 動画開始 = t=0
* 固定オフセット方式のみ採用

```
t_video = t_log + offset_sec
```

* `offset_sec` は CLI 引数・meta.json に保存
* 許容誤差目標: ±100ms（最大 ±200ms まで許容）

---

## ops.jsonl（操作ログ）仕様（v1）

### 基本方針

* 1行 = 1入力イベント（JSONL）
* 時刻 `t_log` は **録画開始（run開始）からの秒（float, sec）**

  * これを `offset_sec` で `t_video` に変換する

### 必須フィールド

| key   | type   | 内容                                             |
| ----- | ------ | ---------------------------------------------- |
| t_log | number | 録画開始からの秒                                       |
| kind  | string | tap / key / mouse_move など（Phase 1 は tap のみでも可） |
| x     | number | 画面座標（px）                                       |
| y     | number | 画面座標（px）                                       |

### 任意フィールド

* button（mouse button）
* key（押下キー）
* note（デバッグ）

**Phase 1 では tap から action（slot, pos）を復元できればOK。**

---

## meta.json（ランメタ情報）仕様（v1）

**meta は kifu の meta イベントには入れず、meta.json に集約する（単一の真実）。**

### 必須キー

* run_id
* video_path（相対でも可）
* ops_path
* roi_board: { x1, y1, x2, y2 }（盤面ROIのpx座標）
* gw, gh
* offset_sec
* fps（不明なら null でも可だが、取れるなら保存）
* created_at（ISO文字列）

---

## dataset 生成（方針 v1）

* 出力形式: **dataset.jsonl**（1行=1サンプル）
* 分割: **run 単位で split**（データリーク防止）

  * train/val/test = 80/10/10 をデフォルト
  * run 数が少ない間は train/val のみでも可

---

## Phase 1 合格基準

* action precision ≥ 0.95
* action recall ≥ 0.90（努力目標）
* Top-3 accuracy ≥ 0.60
* 最小データ量: 5試合 or 500 action

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
* kifu.jsonl / meta.json / 小さな ops.jsonl は Git 管理可
