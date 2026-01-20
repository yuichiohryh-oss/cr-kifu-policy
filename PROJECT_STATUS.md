# PROJECT_STATUS.md

## プロジェクト概要

本プロジェクトは、**Clash Royale（クラロワ）の録画動画と操作ログから行動・状態イベントを抽出し、棋譜（イベント列）として構造化し、学習・推論によって次の行動を提案するAIシステム**を構築することを目的とする。

内部開発ではゲーム固有名詞・UI仕様・数値仕様をそのまま扱い、Qiita 等の外部公開時のみ一般化表現へ変換する。

---

## 最優先テーマ

### 🎯 棋譜（イベント列）中心のパイプライン

**（video.mp4 + ops.jsonl + meta.json）→ kifu.jsonl → dataset.jsonl → 学習 → 提案** を唯一の正式ルートとする。

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

---

## 座標系（v1）

### pos_norm（盤面ROI正規化）

* 基準: **盤面ROI**
* 原点: 左上 (0,0)
* 軸方向: x は右へ増加、y は下へ増加
* 範囲外: clamp して [0,1] に収める

### pos_grid（離散グリッド）

* 盤面ROIを `gw × gh` に等分
* 原点: 左上 (0,0)
* 軸方向: gx は右へ増加、gy は下へ増加
* 変換:

  * `gx = floor(x * gw)`
  * `gy = floor(y * gh)`
  * 端の丸めで gw/gh になった場合は `min(gx, gw-1)`, `min(gy, gh-1)`

---

## 動画 × 操作ログ同期（v1）

* 動画開始 = t=0
* 固定オフセット方式のみ採用

```
t_video = t_log + offset_sec
```

* `offset_sec` は meta.json に保存
* 許容誤差目標: ±100ms（最大 ±200ms）

---

## ops.jsonl（操作ログ）仕様（v1）

### 時刻

* `t_log` は **録画開始（run開始）からの秒（float, sec）**

### 座標系（重要・v1確定）

* `x`,`y` は **動画フレーム座標（px）**

  * 原点: 動画フレーム左上 (0,0)
  * 軸方向: x→右、y→下
  * 範囲: `0 <= x < video_w`, `0 <= y < video_h`

> 端末画面座標や scrcpy ウィンドウ座標でログが出る場合は、ログ生成側で動画座標へ変換してから ops.jsonl に保存する。

### 必須フィールド

| key   | type   | 内容                                            |
| ----- | ------ | --------------------------------------------- |
| t_log | number | run開始からの秒                                     |
| kind  | string | tap / key / mouse_move 等（Phase 1 は tap のみでも可） |
| x     | number | 動画座標（px）                                      |
| y     | number | 動画座標（px）                                      |

---

## meta.json（ランメタ情報）仕様（v1）

**meta は meta.json に集約する（単一の真実）。kifu の meta イベントは v1 では使わない。**

### 必須キー

* run_id
* video_path
* ops_path
* video_w, video_h（動画フレーム解像度 px）
* roi_board: { x1, y1, x2, y2 }（盤面ROIのpx座標。基準は動画座標）
* gw, gh
* offset_sec
* fps（不明なら null 可）
* created_at（ISO文字列）

（必要になったら任意で）screen_w/screen_h, scrcpy_scale, window_offset などを追加してよい。

---

## dataset 生成（方針 v1）

### 出力形式

* dataset.jsonl（1行=1サンプル）

### dataset.jsonl 最小スキーマ（v1）

| key            | type   | 必須 | 内容                       |
| -------------- | ------ | -: | ------------------------ |
| schema_version | string |  ✓ | "dataset/1"              |
| sample_id      | string |  ✓ | `${run_id}:${seq}` 推奨    |
| run_id         | string |  ✓ | run識別子                   |
| t_action       | number |  ✓ | 行動時刻（動画基準秒）              |
| image_path     | string |  ✓ | 盤面ROI画像パス（相対推奨）          |
| label          | object |  ✓ | Phase1: {slot, pos_grid} |
| meta_ref       | string | 任意 | meta.json 参照             |

### split

* run 単位 split（80/10/10 デフォルト）

---

## Phase 1 合格基準

* action precision ≥ 0.95
* action recall ≥ 0.90（努力目標）
* Top-3 accuracy ≥ 0.60
* 最小データ量: 5試合 or 500 action
