# TECH_SPEC.md — Zenn記事生成 v5.1 スキルベースシステム 技術仕様書

> 対象バージョン: v5.1  
> 最終更新: 2026-04-20  
> このドキュメントは実装者向けの精密な技術仕様です。

---

## 1. checkpoint.json スキーマ詳細

### 1.1 フルスキーマ定義

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CheckpointState",
  "type": "object",
  "required": [
    "phase",
    "next_action",
    "material_iter",
    "article_iter",
    "material_fallback_count",
    "best_material_score",
    "best_article_score",
    "best_material_iter",
    "best_article_iter",
    "last_updated"
  ],
  "properties": {
    "phase": {
      "type": "string",
      "enum": ["layer1", "topic_selection", "experience_authoring", "material_pdca", "article_pdca", "done"],
      "description": "現在のフェーズ。layer1=戦略・評価設計、topic_selection=トピック選定、experience_authoring=著者経験ログ生成（v5.2 NEW）、material_pdca=素材PDCA、article_pdca=記事PDCA、done=完了"
    },
    "next_action": {
      "type": "string",
      "enum": [
        "run_strategist",
        "run_eval_designer",
        "run_system_analyst",
        "run_topic_selector",
        "run_experience_author",
        "run_material_iter",
        "run_article_iter",
        "material_fallback",
        "consolidate",
        "finalize",
        "done"
      ],
      "description": "次に実行するアクション識別子（v5.2 で run_experience_author を追加）"
    },
    "material_iter": {
      "type": "integer",
      "minimum": 0,
      "maximum": 5,
      "default": 0,
      "description": "素材PDCAの現在イテレーション番号（0起算、最大5）"
    },
    "article_iter": {
      "type": "integer",
      "minimum": 0,
      "maximum": 10,
      "default": 0,
      "description": "記事PDCAの現在イテレーション番号（0起算、最大10）"
    },
    "material_fallback_count": {
      "type": "integer",
      "minimum": 0,
      "maximum": 2,
      "default": 0,
      "description": "material_fallbackの発動回数（最大2回）"
    },
    "best_material_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 0.0,
      "description": "素材PDCAで達成した最高スコア（0.0〜1.0）"
    },
    "best_article_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 0.0,
      "description": "記事PDCAで達成した最高スコア（0.0〜1.0）"
    },
    "best_material_iter": {
      "type": ["integer", "null"],
      "minimum": 0,
      "default": null,
      "description": "最高素材スコアを記録したイテレーション番号。未記録時はnull"
    },
    "best_article_iter": {
      "type": ["integer", "null"],
      "minimum": 0,
      "default": null,
      "description": "最高記事スコアを記録したイテレーション番号。未記録時はnull"
    },
    "last_updated": {
      "type": "string",
      "format": "date-time",
      "description": "最終更新時刻（ISO8601形式、例: 2026-04-20T09:00:00+09:00）"
    }
  },
  "additionalProperties": false
}
```

---

### 1.2 状態遷移テーブル

| 現在の phase | 現在の next_action | 実行後の条件 | 遷移先 phase | 遷移先 next_action |
|---|---|---|---|---|
| `layer1` | `run_strategist` | 常に | `layer1` | `run_eval_designer` |
| `layer1` | `run_eval_designer` | `strategy.md` の `requires_system_analysis=true` | `layer1` | `run_system_analyst` |
| `layer1` | `run_eval_designer` | `requires_system_analysis=false` | `topic_selection` | `run_topic_selector` |
| `layer1` | `run_system_analyst` | 常に | `topic_selection` | `run_topic_selector` |
| `topic_selection` | `run_topic_selector` | 常に | `experience_authoring` | `run_experience_author` |
| `experience_authoring` | `run_experience_author` | 常に（成功/失敗にかかわらず） | `material_pdca` | `run_material_iter` |
| `material_pdca` | `run_material_iter` | score >= 0.85 OR material_iter == 5 | `article_pdca` | `run_article_iter` |
| `material_pdca` | `run_material_iter` | score < 0.85 AND material_iter < 5 | `material_pdca` | `run_material_iter` |
| `article_pdca` | `run_article_iter` | score >= 0.80 AND article_iter < 3 | `article_pdca` | `finalize` |
| `article_pdca` | `run_article_iter` | score >= 0.80 AND article_iter >= 3 | `article_pdca` | `consolidate` |
| `article_pdca` | `run_article_iter` | article_iter >= 3 AND score < 0.70 AND material_fallback_count < 2 | `material_pdca` | `material_fallback` |
| `article_pdca` | `run_article_iter` | article_iter == 10 | `article_pdca` | `consolidate` |
| `article_pdca` | `run_article_iter` | 上記以外 | `article_pdca` | `run_article_iter` |
| `article_pdca` | `consolidate` | Consolidator + 再 Review 完了 | `article_pdca` | `finalize` |
| `material_pdca` | `material_fallback` | 常に（material_fallback_count++ / material_iter=0 / article_iter=0 / best_article_*リセット / `iterations/`→`iterations_fallback_{n}/`アーカイブ） | `material_pdca` | `run_material_iter` |
| `article_pdca` | `finalize` | 常に | `done` | `done` |
| `done` | `done` | — | `done` | `done` |

**有効な `next_action` の phase別制約（VALID_TRANSITIONS）:**

| phase | 有効な next_action 値 |
|---|---|
| `layer1` | `run_strategist`, `run_eval_designer`, `run_system_analyst` |
| `topic_selection` | `run_topic_selector` |
| `experience_authoring` | `run_experience_author` (v5.2 NEW) |
| `material_pdca` | `run_material_iter`, `material_fallback` |
| `article_pdca` | `run_article_iter`, `material_fallback`, `consolidate`, `finalize` |
| `done` | `done` |

---

### 1.3 各主要状態でのチェックポイント例

#### (A) Fresh Start — 初回起動直後

```json
{
  "phase": "layer1",
  "next_action": "run_strategist",
  "material_iter": 0,
  "article_iter": 0,
  "material_fallback_count": 0,
  "best_material_score": 0.0,
  "best_article_score": 0.0,
  "best_material_iter": null,
  "best_article_iter": null,
  "last_updated": "2026-04-20T09:00:00+09:00"
}
```

#### (B) Mid Material PDCA — 素材PDCA 3回目完了、スコア0.72

```json
{
  "phase": "material_pdca",
  "next_action": "run_material_iter",
  "material_iter": 3,
  "article_iter": 0,
  "material_fallback_count": 0,
  "best_material_score": 0.72,
  "best_article_score": 0.0,
  "best_material_iter": 2,
  "best_article_iter": null,
  "last_updated": "2026-04-20T10:15:00+09:00"
}
```

#### (C) Mid Article PDCA — 記事PDCA 2回目完了、スコア0.75

```json
{
  "phase": "article_pdca",
  "next_action": "run_article_iter",
  "material_iter": 5,
  "article_iter": 2,
  "material_fallback_count": 0,
  "best_material_score": 0.86,
  "best_article_score": 0.75,
  "best_material_iter": 4,
  "best_article_iter": 1,
  "last_updated": "2026-04-20T11:30:00+09:00"
}
```

#### (D) Material Fallback 発動後 — 記事スコア0.62でフォールバック1回目

`trigger_material_fallback` は material_iter / article_iter だけでなく best_article_* もリセットする（v5.1 変更）:

```json
{
  "phase": "material_pdca",
  "next_action": "run_material_iter",
  "material_iter": 0,
  "article_iter": 0,
  "material_fallback_count": 1,
  "best_material_score": 0.80,
  "best_article_score": 0.0,
  "best_material_iter": 3,
  "best_article_iter": null,
  "last_updated": "2026-04-20T12:45:00+09:00"
}
```

直前に存在していた `output/iterations/` は orchestrator 側で `output/iterations_fallback_1/` にリネームされている。

#### (E) Done — 記事スコア0.82で正常完了

```json
{
  "phase": "done",
  "next_action": "done",
  "material_iter": 4,
  "article_iter": 5,
  "material_fallback_count": 0,
  "best_material_score": 0.88,
  "best_article_score": 0.82,
  "best_material_iter": 3,
  "best_article_iter": 4,
  "last_updated": "2026-04-20T14:00:00+09:00"
}
```

---

## 2. SubAgent Spawn コントラクトテンプレート

### 2.1 テンプレートA — シングルエージェントスポーン

```
あなたは {agent_name} です。
タスク: {task_description}

入力ファイル:
- {input_file_1}: {description}
- {input_file_2}: {description}

出力:
- {output_file} に書き込む
- tool_result には path + 2-4文のサマリーのみ返す（10KB rule）

制約:
- {constraints}
```

**プレースホルダー仕様:**

| プレースホルダー | 型 | 説明 |
|---|---|---|
| `{agent_name}` | string | エージェント役割名（例: `Strategist`, `MaterialReviewer`） |
| `{task_description}` | string | 単一タスクの明確な説明。動詞から始める |
| `{input_file_N}` | Path (絶対パス) | `file_registry.py` の `Paths.*` 定数を使用 |
| `{description}` | string | ファイルの内容・用途を1文で説明 |
| `{output_file}` | Path (絶対パス) | 書き込み先ファイルパス |
| `{constraints}` | string (複数行可) | 箇条書きで制約を列挙 |

**10KB rule:** tool_result は必ず10KB以下に収める。本文はファイルに書き込み、返却はパスとサマリーのみ。

---

### 2.2 テンプレートB — 並列スポーン（Phase 0専用）

Phase 0（Layer1の戦略フェーズ）においてのみ、`TrendResearcher` と `PainExtractor` を並列実行できます。

```
## 並列実行指示（Phase 0 専用）

以下の2エージェントを同時にスポーンしてください。

### エージェント1: TrendResearcher
あなたは TrendResearcher です。
タスク: {trend_task_description}

入力ファイル:
- なし（外部情報源を参照）

出力:
- {TRENDS_PATH} に書き込む
- tool_result には path + 2-4文のサマリーのみ返す（10KB rule）

制約:
- Zennトレンドとテック系SNSトレンドを対象とする
- 直近30日以内の情報を優先する

---

### エージェント2: PainExtractor
あなたは PainExtractor です。
タスク: {pain_task_description}

入力ファイル:
- {STRATEGY_PATH}: 戦略エージェントが生成したテーマ・ターゲット情報

出力:
- {READER_PAINS_PATH} に書き込む
- tool_result には path + 2-4文のサマリーのみ返す（10KB rule）

制約:
- ターゲット読者の具体的な悩みを5〜10件列挙する
- 解決可能性の評価を各悩みに付記する

---

## 親エージェントの待機処理
両エージェントの完了後、以下のパスを読み込んでください:
- {TRENDS_PATH}
- {READER_PAINS_PATH}
```

**並列実行の制約:**
- Phase 0（`phase=layer1`, `next_action=run_strategist` または `run_eval_designer`）のみ許可
- 各エージェントは独立したファイルに出力する（出力先の重複禁止）
- 親エージェントは両方の完了を確認してから次のステージへ進む
- 並列実行中はcheckpointを更新しない（完了後にまとめて更新）

---

## 3. 6スクリプト API シグネチャ

### 3.1 file_registry.py

ファイルパスの一元管理モジュール。全スクリプトはこのモジュール経由でパスを参照します。

```python
from pathlib import Path

class Paths:
    """全出力ファイルパスの定数クラス。環境変数 OUTPUT_DIR で出力先を変更可能。"""

    OUTPUT_DIR: Path          # デフォルト: Path("./output")
    STRATEGY: Path            # output/strategy.md — Strategistエージェントの出力
    EVAL_CRITERIA: Path       # output/eval_criteria.md — EvalDesignerの評価基準
    TRENDS: Path              # output/trends.md — TrendResearcherのトレンド調査結果
    READER_PAINS: Path        # output/reader_pains.md — PainExtractorの読者悩みリスト
    THESIS: Path              # output/thesis.md — 記事テーゼ・主張軸
    MATERIAL_REVIEW: Path     # output/material_review.md — 素材レビュー結果（スコア含む）
    STYLE_GUIDE: Path         # output/style_guide.md — 文体・構成ガイドライン
    AGENT_MEMORY: Path        # output/agent_memory.json — エージェント間共有メモリ
    ARTICLE_DRAFT: Path       # output/article_draft.md — 記事ドラフト（最新イテレーション）
    ARTICLE_REVIEW: Path      # output/article_review.md — 記事レビュー結果（スコア含む）
    FB_LOG: Path              # output/fb_log.json — フィードバックログ
    CHECKPOINT: Path          # output/checkpoint.json — チェックポイント状態
    FINAL_ARTICLE: Path       # output/final_article.md — 最終確定記事
    REPORT: Path              # output/report.md — 実行サマリーレポート


def resolve_path(name: str) -> Path:
    """
    Paths クラスの属性名文字列からPathオブジェクトを返す。

    Args:
        name: Paths クラスの属性名（例: "STRATEGY", "CHECKPOINT"）

    Returns:
        対応する Path オブジェクト

    Raises:
        ValueError: name が Paths の属性として存在しない場合
    """
    ...
```

---

### 3.2 metrics.py

記事テキストの定量評価モジュール。ハードフェイル（即時減点）ルールを実装します。

```python
@dataclass
class ArticleMetrics:
    code_ratio: float                    # コードブロック内行数 / 全行数
    desu_masu_ratio: float               # です・ます体の文末比率
    max_consecutive_same_length: int     # ±10字以内の同長文が連続した最大数


@dataclass
class HardFailResult:
    applied: bool           # いずれかの HARD FAIL 条件にヒットした場合 True
    cap: float | None       # 適用される score cap（複数ヒット時は min）
    reasons: list[str]      # "code_ratio 0.25 > 0.20" 等のヒット理由（複数可）


# v5.1 既定閾値（metrics.py の DEFAULT_HARD_FAIL と一致）
DEFAULT_HARD_FAIL = {
    "code_ratio_limit": 0.20,
    "code_ratio_cap": 0.60,
    "desu_masu_min": 0.80,
    "desu_masu_cap": 0.55,
    "consecutive_length_max": 4,
    "consecutive_length_cap": 0.50,
}


def compute_article_metrics(article_text: str) -> ArticleMetrics:
    """記事テキストから定量メトリクスを計算する。"""
    ...


def check_hard_fail(metrics: ArticleMetrics, hf: dict | None = None) -> HardFailResult:
    """
    HARD FAIL 条件を判定し HardFailResult を返す。

    判定条件（hf=None の場合は DEFAULT_HARD_FAIL を使用）:
        1. code_ratio > code_ratio_limit (0.20)     → cap=code_ratio_cap (0.60)
        2. desu_masu_ratio < desu_masu_min (0.80)   → cap=desu_masu_cap (0.55)
        3. max_consecutive_same_length > consecutive_length_max (4)
                                                    → cap=consecutive_length_cap (0.50)

    複数条件にヒットした場合、cap は最小値を採用する。
    """
    ...


def apply_hard_fail(review_score: float, hard_fail: HardFailResult) -> float:
    """
    HARD FAIL cap を適用して最終スコアを返す。

    hard_fail.applied が False または cap が None の場合は review_score をそのまま返す。
    そうでなければ min(review_score, hard_fail.cap) を返す。
    """
    ...


def apply_major_penalty(score: float, major_count: int) -> float:
    """
    major feedback の件数に応じてスコアに cap を適用する（v5.1 追加）。

    cap ルール（閾値との整合を保つための設計）:
        major_count >= 3 → cap = 0.70  （MATERIAL_FALLBACK 閾値以下に落とす）
        major_count >= 2 → cap = 0.79  （article threshold 0.80 未満）
        major_count >= 1 → cap = 0.84  （material threshold 0.85 未満）
        major_count == 0 → 変化なし

    major feedback が残っている限り該当 PDCA の閾値を突破できなくなり、
    次 iter での改善が強制される。
    """
    ...


def fix_code_ratio(article_text: str, target_ratio: float = 0.18) -> str:
    """
    コードブロック内の空行と単独コメント行（先頭 '#' / '//'）のみを除去して
    code_ratio を target_ratio 以下に抑える（v5.1 追加、FIX-A-2 対応）。

    実質的なコード行は削除しない。最大 3 反復で target 未達なら現状の文字列を返す
    （以降は cap 適用 + フィードバックで Writer 側に改善を促す）。
    """
    ...


def fix_desu_masu(text: str) -> str:
    """
    だ・である調の文末をです・ます調に自動変換する。

    対象パターン（例）:
        - 「〜だ。」→「〜です。」
        - 「〜である。」→「〜です。」
        - 「〜した。」は変換不要（既にです・ます調と同等）

    Args:
        text: 変換対象のテキスト

    Returns:
        str: 変換後のテキスト
    """
    ...


def fix_consecutive_length(text: str) -> str:
    """
    同一文字数の段落が連続する箇所を分割・調整する。

    連続3段落以上が同一文字数の場合、末尾の段落に補足文を追加して
    文字数を変化させる。

    Args:
        text: 調整対象のテキスト

    Returns:
        str: 調整後のテキスト
    """
    ...
```

---

### 3.3 fb_log.py

フィードバックログの読み書きと差分計算モジュール。

**重要バグ修正（v5.0→v5.1）:** `save_fb_log` の `diffs` 引数が v5.0 では常に空リスト `[]` で呼び出されていました。v5.1 では `compute_fb_diff(entries)` の結果を必ず渡してください。

```python
@dataclass
class FBEntry:
    """単一フィードバックエントリ（fb_log.json の entries 要素）"""
    id: str               # "FB-M-001" / "FB-A-001" 形式（M=material, A=article）
    iteration: int        # エントリを記録した iter 番号
    phase: str            # "material" | "article"
    axis: str             # レビュー軸名
    severity: str         # "major" | "minor"
    description: str      # フィードバック本文
    status: str           # "new" | "persisted" | "resolved"
    created_at: int       # 生成 iter
    resolved_at: int | None = None


@dataclass
class FBDiff:
    """2 iter 間のフィードバック差分サマリー（fb_log.json の diffs 要素）"""
    resolution_rate: float          # 前 iter の active エントリのうち解決された割合
    new_count: int                  # status="new" の件数
    persisted_count: int            # status="persisted" の件数
    major_persisted_count: int      # 上記のうち severity="major"
    major_persisted_streak: int     # major_persisted_count>0 が連続している iter 数


def load_fb_log(path: str) -> list[FBEntry]:
    """
    フィードバックログファイルを読み込み、entries 部分のみを返す。

    Args:
        path: fb_log.json のパス（Paths.FB_LOG）

    Returns:
        list[FBEntry]: エントリリスト。ファイルが存在しない場合は空リスト。
    """
    ...


def save_fb_log(path: str, entries: list[FBEntry], diffs: list[dict]) -> None:
    """
    フィードバックログをファイルに保存する。

    【v5.1 バグ修正】diffs が空リストで entries が存在する場合は、
    内部で _compute_simple_diffs(entries) による自動計算にフォールバックする。
    canonical な書き込みパスは append_fb_diff()。

    Args:
        path: 書き込み先パス（Paths.FB_LOG）
        entries: record_fb() で構築した FBEntry リスト
        diffs: dict のリスト（FBDiff を asdict 化したもの）。
               空リストの場合、auto-compute フォールバックが働く

    Returns:
        None
    """
    ...


def record_fb(
    entries: list[FBEntry],
    new_feedbacks: list[dict],
    iteration: int,
    phase: str,
) -> list[FBEntry]:
    """
    review.json の feedback（dict リスト）を既存の FBEntry リストに反映する。

    - 同一 axis + severity の既存 new/persisted エントリがあれば status="persisted" 化
    - 一致しない既存エントリは status="resolved"（resolved_at=iteration）に
    - マッチしない new_feedbacks は新規 FBEntry として append（ID は連番採番）

    Args:
        entries: 既存の FBEntry リスト（load_fb_log() の返り値）
        new_feedbacks: 今 iter の review.json["feedback"] —
                       各要素は {"axis": str, "severity": str, "text": str}
        iteration: 現在の iter 番号
        phase: "material" | "article"

    Returns:
        list[FBEntry]: 更新後のエントリリスト（元リストは破壊しない）
    """
    ...


def compute_fb_diff(
    prev_entries: list[FBEntry],
    curr_entries: list[FBEntry],
) -> FBDiff:
    """
    前 iter と現 iter のエントリ間差分を FBDiff として返す。

    Args:
        prev_entries: 前 iter の FBEntry リスト
        curr_entries: 現 iter の FBEntry リスト（record_fb の返り値）

    Returns:
        FBDiff: resolution_rate, new_count, persisted_count,
                major_persisted_count, major_persisted_streak を含む

    注意: major_persisted_streak は compute_fb_diff だけでは確定せず、
          append_fb_diff が過去 diff 履歴を読んで加算する
    """
    ...


def append_fb_diff(
    path: str,
    entries: list[FBEntry],
    prev_entries: list[FBEntry],
    iteration: int,
    phase: str,
) -> FBDiff:
    """
    compute_fb_diff を実行し、streak を加算した上で fb_log.json に追記する
    canonical 書き込みパス。INSTRUCTIONS から呼ぶ際はこれを使い、
    save_fb_log(..., []) による empty-diff 書き込みは避けること。

    Args:
        path: fb_log.json のパス
        entries: record_fb() の返り値
        prev_entries: record_fb 呼び出し前の entries（= load_fb_log の返り値）
        iteration: 現在の iter
        phase: "material" | "article"

    Returns:
        FBDiff: 追記した diff（streak 更新済み）
    """
    ...
```

**v5.1 変更**: `check_fb_stagnation` と `StagnationResult` dataclass は v5.1 で削除された（停滞検出は `stagnation_check.detect_stagnation` / `should_trigger_gap_alert` に一本化）。

---

### 3.4 stagnation_check.py（NEW）

停滞検出の専用モジュール。v5.1 では `fb_log.check_fb_stagnation` を削除してこの実装に一本化（tolerance=0.01 の単一基準に統一）。

```python
def compute_resolution_rate(diffs: list) -> float:
    """
    フィードバック差分リストから解決率を計算する。

    Args:
        diffs: compute_fb_diff() が返す差分リスト

    Returns:
        float: resolved=True の件数 / 全件数（0.0〜1.0）
               diffs が空の場合は 0.0 を返す
    """
    ...


def detect_stagnation(entries: list, window: int = 3) -> bool:
    """
    直近 `window` イテレーションのスコアが停滞状態かを判定する。

    停滞条件: max(直近window件のスコア) <= min(直近window件のスコア) + 0.01

    Args:
        entries: フィードバックエントリリスト（各エントリに "score" キーを含む）
        window: 判定ウィンドウ幅（デフォルト: 3）

    Returns:
        bool: 停滞している場合 True
              entries が window 件未満の場合は False（判定不能）
    """
    ...


def should_trigger_gap_alert(entries: list, threshold: float, window: int = 3) -> bool:
    """
    ギャップアラートを発動すべきかを判定する。

    発動条件: detect_stagnation() が True かつ 直近スコアの最大値 < threshold

    Args:
        entries: フィードバックエントリリスト
        threshold: 目標スコアの閾値（素材PDCAは 0.85、記事PDCAは 0.80）
        window: detect_stagnation に渡すウィンドウ幅（デフォルト: 3）

    Returns:
        bool: ギャップアラートを発動すべき場合 True
    """
    ...
```

---

### 3.5 gap_alert.py（NEW）

スコアギャップとアラートメッセージ生成の専用モジュール。Leadエージェントが次のイテレーションプロンプトにアラートを埋め込むために使用します。

```python
def compute_gap(current_score: float, threshold: float) -> float:
    """
    現在スコアと目標閾値のギャップを計算する。

    Args:
        current_score: 現在の最高スコア（0.0〜1.0）
        threshold: 目標スコアの閾値（例: 0.85, 0.80）

    Returns:
        float: threshold - current_score（正の値=未達、負の値=達成済み）
    """
    ...


def format_gap_alert(
    current_score: float,
    threshold: float,
    feedback_history: list
) -> str:
    """
    Leadエージェントが次イテレーションプロンプトに挿入するアラート文字列を生成する。

    Args:
        current_score: 現在の最高スコア
        threshold: 目標スコアの閾値
        feedback_history: フィードバックエントリリスト（"feedback" キーを含む）

    Returns:
        str: フォーマット済みアラートメッセージ。形式:
            "GAP ALERT: current={:.2f}, target={:.2f}, gap={:.2f}
            {recurring_issues の箇条書き（top 3）}"

    例:
        "GAP ALERT: current=0.62, target=0.80, gap=0.18
        - 具体例が不足している
        - 導入部が長すぎる
        - コードブロックのコメントが日本語でない"
    """
    ...


def extract_recurring_issues(feedback_history: list, top_n: int = 3) -> list[str]:
    """
    フィードバック履歴から繰り返し言及されている問題点を抽出する。

    実装方針:
        1. 各エントリの "feedback" テキストを形態素解析（または簡易分割）
        2. 頻出フレーズ・キーワードをカウント
        3. 出現頻度上位 top_n 件を返す

    Args:
        feedback_history: フィードバックエントリリスト
        top_n: 返す問題点の最大件数（デフォルト: 3）

    Returns:
        list[str]: 頻出問題点のリスト（頻度降順）
                   フィードバックが不足している場合は空リストを返す
    """
    ...
```

---

### 3.6 checkpoint.py（NEW）

チェックポイントの読み書きとルーティングの専用モジュール。

```python
def read_checkpoint(path: Path) -> dict:
    """
    チェックポイントファイルを読み込む。

    Args:
        path: checkpoint.json のパス（Paths.CHECKPOINT）

    Returns:
        dict: チェックポイント状態。ファイルが存在しない場合はフレッシュスタート状態:
            {
                "phase": "layer1",
                "next_action": "run_strategist",
                "material_iter": 0,
                "article_iter": 0,
                "material_fallback_count": 0,
                "best_material_score": 0.0,
                "best_article_score": 0.0,
                "best_material_iter": null,
                "best_article_iter": null,
                "last_updated": "<現在時刻のISO8601>"
            }
    """
    ...


def write_checkpoint(path: Path, state: dict) -> None:
    """
    チェックポイントをファイルに書き込む。

    last_updated フィールドを現在時刻（ISO8601）で自動更新してから保存する。

    Args:
        path: 書き込み先パス（Paths.CHECKPOINT）
        state: 更新後のチェックポイント状態 dict

    Returns:
        None

    注意: 書き込みは atomic write（一時ファイル経由）で実装すること
    """
    ...


def route_next_action(checkpoint: dict) -> str:
    """
    checkpoint["next_action"] をそのまま返す（v5.1 実装はバリデーションなし）。

    Args:
        checkpoint: read_checkpoint() が返す状態 dict

    Returns:
        str: checkpoint["next_action"] の値（キー欠落時は "run_strategist"）
    """
    ...


def is_complete(checkpoint: dict) -> bool:
    """phase == "done" の場合 True を返す。"""
    ...


def advance_layer1(
    checkpoint: dict,
    completed_step: str,
    requires_system_analysis: bool = False,
) -> dict:
    """
    Layer 1 のステップ完了後の状態を返す。

    遷移:
        completed_step="strategist"        → next_action="run_eval_designer"
        completed_step="eval_designer":
            requires_system_analysis=True  → next_action="run_system_analyst"
            requires_system_analysis=False → phase="material_pdca",
                                             next_action="run_material_iter"
        completed_step="system_analyst"    → phase="material_pdca",
                                             next_action="run_material_iter"

    Args:
        checkpoint: 現在の状態
        completed_step: "strategist" | "eval_designer" | "system_analyst"
        requires_system_analysis: strategy.md の frontmatter から取得したフラグ
            （eval_designer 完了時のみ参照される）
    """
    ...


def advance_material_iter(
    checkpoint: dict,
    score: float,
    threshold: float = 0.85,
    max_iter: int = 5,
) -> dict:
    """
    Material PDCA 1 iter 完了後の状態を返す（iter++、best 更新、遷移判定）。

    score >= threshold OR material_iter >= max_iter
        → phase="article_pdca", next_action="run_article_iter"
    それ以外は next_action="run_material_iter"（ループ継続）
    """
    ...


def advance_article_iter(
    checkpoint: dict,
    score: float,
    threshold: float = 0.80,
    max_iter: int = 10,
    fallback_max: int = 2,
) -> dict:
    """
    Article PDCA 1 iter 完了後の状態を返す。

    遷移:
        score >= threshold AND article_iter >= 3        → next_action="consolidate"
        score >= threshold AND article_iter < 3         → next_action="finalize"
        article_iter >= 3 AND score < 0.70 AND
            material_fallback_count < fallback_max      → next_action="material_fallback"
        article_iter >= max_iter                        → next_action="consolidate"
        上記以外                                          → next_action="run_article_iter"

    Consolidator は iter >= 3 かつ finalize 直前のみ実行される（v5.1 変更）。
    """
    ...


def trigger_material_fallback(checkpoint: dict) -> dict:
    """
    Material PDCA にバックトラックする。

    更新:
        phase="material_pdca"
        next_action="run_material_iter"
        material_fallback_count += 1
        article_iter=0, material_iter=0
        best_article_iter=None, best_article_score=0.0（v5.1 追加: Finalizer が
            古い iter を指さないよう明示リセット。orchestrator 側で
            iterations/ → iterations_fallback_{count}/ のリネームと組み合わせる）
    """
    ...


def advance_after_consolidate(checkpoint: dict) -> dict:
    """Consolidator + 再 Review 完了後に next_action="finalize" にする（v5.1 追加）。"""
    ...


def mark_done(checkpoint: dict) -> dict:
    """phase="done", next_action="done" にして完了状態にマーク。"""
    ...
```

---

## 4. SKILL.md / INSTRUCTIONS.md テンプレート構造

### 4.1 SKILL.md テンプレート

スキルのメタ情報を定義するYAMLファイル。スキルルーターがスキル選択に使用します。

```yaml
name: skill-name                    # スキル識別子（kebab-case）
description: One-line description   # スキルの一行説明（英語推奨）
triggers:
  - keyword patterns                # このスキルが起動するキーワード・フレーズのリスト
capabilities:
  - what this skill can do          # できること（箇条書き）
limitations:
  - what it cannot do               # できないこと・前提条件（箇条書き）
```

**各フィールドの記述ガイドライン:**

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `name` | string | 必須 | kebab-case。ディレクトリ名と一致させる |
| `description` | string | 必須 | 50文字以内。スキルルーターの埋め込み検索に使用 |
| `triggers` | list[string] | 必須 | ユーザー発話やコンテキストから検出するパターン |
| `capabilities` | list[string] | 必須 | 実装済みの機能のみ記載（予定は除く） |
| `limitations` | list[string] | 推奨 | 既知の制限・依存関係・前提条件 |

---

### 4.2 INSTRUCTIONS.md 構成

スキルの実行手順を定義するMarkdownファイル。Leadエージェントが読み込んで実行計画を立てます。

```markdown
# {Skill Name}

## 役割
このスキルが担当する責務を2〜3文で説明する。
何を入力として受け取り、何を出力するかを明示する。

## 起動条件
- 起動されるべきユーザーリクエストのパターン
- 前提として完了していなければならないステージ
- 必要な入力ファイルの存在確認

## Stage Dispatch Table

| Stage | next_action値 | 実行内容 | 完了条件 |
|---|---|---|---|
| ステージ名1 | `run_xxx` | 実行するサブエージェントと処理 | スコアや出力ファイルの存在など |
| ステージ名2 | `run_yyy` | 実行するサブエージェントと処理 | 完了を判断する条件 |
| ... | ... | ... | ... |

## 実行手順

### Step 1: チェックポイント確認
checkpoint.py の read_checkpoint() でフェーズを確認する。
route_next_action() で次のアクションを取得する。

### Step 2: {next_action に対応する処理}
サブエージェントのスポーン方法と引数を具体的に記述する。
出力ファイルのパスは file_registry.py の Paths クラスから取得する。

### Step N: チェックポイント更新
状態変化後は必ず write_checkpoint() でチェックポイントを更新する。
更新タイミング: サブエージェントの出力ファイルが確認できた直後。

## checkpoint更新ルール

各アクション完了後の状態遷移を具体的に記述する。

| アクション完了 | 更新する fields | 値の変化 |
|---|---|---|
| `run_material_iter` 完了 | `material_iter`, `best_material_score`, `best_material_iter`, `next_action` | iter+1、best更新（改善時のみ）、遷移先を判定 |
| `run_article_iter` 完了 | `article_iter`, `best_article_score`, `best_article_iter`, `next_action` | iter+1、best更新（改善時のみ）、遷移先を判定 |

## エラー時フォールバック

| エラー種別 | 対処方法 |
|---|---|
| サブエージェントがファイルを生成しなかった | チェックポイントを更新せずリトライ（最大2回） |
| スコアが数値として解析できない | score=0.0 として記録し、次のイテレーションへ進む |
| 入力ファイルが存在しない | ValueError を送出し、前のステージから再実行するよう促す |
| material_fallback_count が上限（2）に達した | finalize に強制遷移し、警告を report.md に記録 |
```

---

## 8. Phase 4 既知バグ詳細（2026-04-20 E2E実行で発見）

> **発見日**: 2026-04-20  
> **発見契機**: `fix/phase1-code-corrections` ブランチでのフルE2E実行（記事テーマ: システム自己紹介記事）  
> **ステータス**: 全件未修正（Phase 4 修正対象）  
> **対応REQUIREMENTS.md**: R-09〜R-16

---

### Bug-A1: `_extract_sentences()` がYAML frontmatterと区切り行を文として計上

**場所**: `metrics.py` / `_extract_sentences()` 関数

**症状**: desu_masu比率が実際の文章より低く計算される。  
article.md 先頭の7行分YAML frontmatter（`---`、`title:`、`emoji:`等）と`---`区切り行が「文」としてカウントされ、分母が水増しされる。

**実測値**:
- E2Eで frontmatter 7行 + `---` 4行 ≒ 11文が余分にカウント
- 本文desu_masu文が80/100文でも計算上は80/111 ≈ 0.72 となりHARDFAIL発動

**現在のコード（問題箇所）**:
```python
def _extract_sentences(text: str) -> list[str]:
    sentences = re.split(r'[。！？\n]+', text)  # 全行を一律分割
    return [s.strip() for s in sentences if s.strip()]
```

**修正方針**:
```python
def _extract_sentences(text: str) -> list[str]:
    # YAMLfrontmatter除去
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)
    # Markdownテーブル行除去（|で始まる行）
    lines = [l for l in text.split('\n') if not l.strip().startswith('|')]
    text = '\n'.join(lines)
    sentences = re.split(r'[。！？]+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 2]
```

---

### Bug-A2: `_DESU_MASU_RE` が取りこぼすです・ます終止パターン

**場所**: `metrics.py` / `_DESU_MASU_RE` 正規表現

**症状**: 以下のパターンがdesu_masu文としてカウントされない。

| パターン | 例文 | 原因 |
|---|---|---|
| `でしょうか。` | 「なぜそうなるのでしょうか。」 | `か` が`[。？！]`の前に介在 |
| `ます（補足）。` | 「確認できます（詳細は後述）。」 | `ます`の直後が`（`で句点でない |
| 体言止め | 「これが核心。」 | そもそも対象外（仕様とも取れる） |
| バッククォート後の句点 | `` `metrics.py` です。`` | バッククォートが終端に挟まる |

**現在のパターン**:
```python
_DESU_MASU_RE = re.compile(
    r'(です|ます|でした|ました|ません|でしょう)[。？！\?\!]?\s*$',
    re.MULTILINE
)
```

**修正方針**:
```python
_DESU_MASU_RE = re.compile(
    r'(です|ます|でした|ました|ません|でしょう|でしょうか)'
    r'[^。]*[。？！\?\!]',  # 終止符までの間に他文字を許容
    re.MULTILINE
)
```

---

### Bug-A3: `fix_consecutive_length()` が句点境界の連続同長問題を解消できない

**場所**: `metrics.py` / `fix_consecutive_length()` 関数

**症状**: 関数を5回適用しても `consecutive_same_length` が変化しない。

**根本原因**: 構造的ミスマッチ
- `_extract_sentences()` は `。` で文を分割（1行に複数文が含まれる）
- `fix_consecutive_length()` は改行（`\n`）で行を分割してマージ処理
- → 同一行内の `。` 区切り連続文には一切効かない

**実測**: E2E実行でConslidator後に `consecutive=9` が発生したが、`fix_consecutive_length()` では0改善。手動でターゲット文を直接編集することで解消した。

**修正方針**: `fix_consecutive_length()` を廃止してWriterプロンプトで根本防止するアプローチが現実的。代替案として `_extract_sentences()` の結果を直接操作してマージするが、Markdownの文構造を壊すリスクがある。

---

### Bug-B1: `advance_after_consolidate()` がConsolidator後スコアを`best_article_score`に反映しない

**場所**: `checkpoint.py` / `advance_after_consolidate()` 関数

**症状**: `report.json` の `score` と `best_article_score` がConsolidator前の値のまま。

**実測値**:
- Consolidatorが再レビューで `0.82` を取得
- `report.json` は `{"score": 0.80, "best_article_score": 0.80}` のまま

**現在のコード（問題箇所）**:
```python
def advance_after_consolidate(state: dict) -> dict:
    state["next_action"] = "finalize"
    state["last_updated"] = _now()
    return state  # best_article_score を更新していない
```

**修正方針**:
```python
def advance_after_consolidate(state: dict, consolidated_score: float) -> dict:
    state["next_action"] = "finalize"
    if consolidated_score > state.get("best_article_score", 0.0):
        state["best_article_score"] = consolidated_score
        state["best_article_iter"] = state.get("article_iter", 0)
    state["last_updated"] = _now()
    return state
```

---

### Bug-C1: Article PDCA Step 6のdeath_patterns抽出でdict型に`in`演算子誤用

**場所**: `zenn-article-pdca/INSTRUCTIONS.md` / Step 6 エージェントメモリ更新

**症状**: `death_patterns` が常に空リストになり、エージェントメモリに死亡パターンが蓄積されない。

**現在の指示**:
```python
death_patterns = [f for f in review["feedback"] if "過多" in f or "NG" in f]
```

**問題**: `review["feedback"]` の各要素 `f` は `{"axis": ..., "severity": ..., "text": ...}` のdictオブジェクト。dictへの `in` 演算子はキー名を検索するため、`"過多"` や `"NG"` は永久にマッチしない。

**修正方針**:
```python
death_patterns = [
    f["text"] for f in review["feedback"]
    if "過多" in f.get("text", "") or "NG" in f.get("text", "")
]
```

---

### Bug-C2: Consolidator実行後のHARDFAILチェックがINSTRUCTIONSに存在しない

**場所**: `zenn-orchestrator/INSTRUCTIONS.md` / `consolidate` アクション処理

**症状**: Consolidatorが生成した記事にHARDFAIL条件が新たに発生しても検知されず、そのままfinalizeに進む。

**E2E実測**: Consolidator実行後に `consecutive_same_length=9` が発生したが、システムは検知せずfinalize手続きへ進んだ（手動介入で回避）。

**現在のINSTRUCTIONS記述（consolidateアクション）**:
```
1. Consolidatorを実行
2. ArticleReviewerを再スポーン
3. スコアを確定
4. advance_after_consolidate() を呼び出し
5. next_action=finalize へ
```

**修正方針**: Step 3 と Step 4 の間に以下を追加:
```
3b. apply_hard_fail(consolidated_article_path) を実行
    - HARDFAILが検出された場合: Writerに修正指示を出し、記事を更新してStep 2へ戻る（最大2回）
    - HARDFAILなし: Step 4へ進む
```

---

### Bug-D1: ArticleReviewer JSONスキーマキー名揺れ

**場所**: `agents/article_reviewer.md` スキーマ定義 / `zenn-article-pdca/INSTRUCTIONS.md` スコア読み取り

**症状**: ArticleReviewerが稀に `weighted_average_raw` キーを使用し、`weighted_average` が存在しないreview.jsonを出力する。スコア読み取りで `KeyError` リスクがある。

**E2E実測**: iter 2のreview.jsonに `"weighted_average_raw": 0.74` が含まれ、`"weighted_average"` キーが欠落していた。

**修正方針**:
1. `article_reviewer.md` のスキーマ定義でキー名を `weighted_average` に統一し、エージェントへの指示を強化
2. スコア読み取り側を防御的実装に変更:
```python
score = review.get('weighted_average', review.get('weighted_average_raw', 0.0))
```

---

### Bug-E1: HARDFAILキャップ値とMATERIAL_FALLBACK閾値の論理的矛盾

**場所**: `metrics.py` `DEFAULT_HARD_FAIL` / `checkpoint.py` MATERIAL_FALLBACK条件

**症状**: desu_masu HARDFAILキャップ（0.55）がMATERIAL_FALLBACK閾値（0.70）を下回るため、Bug-A1〜A2が存在する環境では「記事品質は十分だがメトリクスバイアスでHARDFAILが繰り返し発動→スコアが0.55に固定→article_iter>=3でMATERIAL_FALLBACKが誘発」という意図しないフォールバックループが発生しうる。

**対処優先順位**: Bug-A1〜A3（metrics構造バグ）の修正を優先し、メトリクス計算が正確になってからこのリスクを再評価する。

---

*TECH_SPEC.md 終了 — Zenn記事生成 v5.1 スキルベースシステム*
