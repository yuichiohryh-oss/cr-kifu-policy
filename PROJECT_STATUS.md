# PROJECT_STATUS.md

> Doc revision: **rev 1.3**
>
> ※ この **rev** はドキュメント／仕様書の改訂番号です。`schema_version`（例: `kifu/1`, `dataset/1`）とは**別物**です。

## プロジェクト概要

本プロジェクトは、**Clash Royale（クラロワ）の録画動画と操作ログから行動・状態イベントを抽出し、棋譜（イベント列）として構造化し、学習・推論によって次の行動を提案するAIシステム**を構築することを目的とする。

内部開発ではゲーム固有名詞・UI仕様・数値仕様をそのまま扱い、Qiita 等の外部公開時のみ一般化表現へ変換する。

---

## 最優先テーマ

### 🎯 棋譜（イベント列）中心のパイプライン

**（video.mp4 + ops.jsonl + meta.json）→ kifu.jsonl →（kifu.jsonl + video.mp4 + meta.json）→ dataset.jsonl → 学習 → 提案** を唯一の正式ルートとする。

---

## kifu.jsonl（schema v1）

### 基本方針

- 1行 = 1イベント（JSONL）
- 時刻 `t` は **動画開始からの秒（float, sec）**
- **`seq` は run 内で単調増加する通番**
- ソートキーは `(t, seq)`

### 共通フィールド（必須）

| key | type | 内容 |
|---|---|---|
| schema_version | string | "kifu/1" |
| run_id | string | セッション識別子 |
| seq | integer | run 内通番 |
| event_id | string | `${run_id}:${seq}` 推奨 |
| t | number | 動画開始からの秒 |
| type | string | action / spawn / resource |
| actor | string | self / enemy / system |
| confidence | number | [0,1] |

### action イベント（Phase 1）

| key | type | 内容 |
|---|---|---|
| slot | integer | 手札スロット（0–3） |
| pos_grid | object | { gx:int, gy:int } |
| pos_norm | object | { x:float, y:float }（任意） |

---

## 座標系

### pos_norm

- 基準: 盤面ROI（meta.json の roi_board）
- 原点: 左上 (0,0)
- 範囲外は clamp

### pos_grid

- `pos_norm` から算出する離散グリッド

```text
gx = floor(x_norm * gw)
gy = floor(y_norm * gh)
# 上限処理（安全のため必須）
gx = min(gx, gw - 1)
gy = min(gy, gh - 1)
