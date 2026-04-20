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
      "enum": ["layer1", "material_pdca", "article_pdca", "done"],
      "description": "現在のフェーズ。layer1=戦略・評価設計、material_pdca=素材PDCA、article_pdca=記事PDCA、done=完了"
    },
    "next_action": {
      "type": "string",
      "enum": [
        "run_strategist",
        "run_eval_designer",
        "run_material_iter",
        "run_article_iter",
        "material_fallback",
        "finalize",
        "done"
      ],
      "description": "次に実行するアクション識別子"
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
| `layer1` | `run_eval_designer` | 常に | `material_pdca` | `run_material_iter` |
| `material_pdca` | `run_material_iter` | score >= 0.85 OR material_iter == 5 | `article_pdca` | `run_article_iter` |
| `material_pdca` | `run_material_iter` | score < 0.85 AND material_iter < 5 | `material_pdca` | `run_material_iter` |
| `article_pdca` | `run_article_iter` | score >= 0.80 | `article_pdca` | `finalize` |
| `article_pdca` | `run_article_iter` | article_iter >= 3 AND score < 0.70 AND material_fallback_count < 2 | `material_pdca` | `material_fallback` |
| `article_pdca` | `run_article_iter` | article_iter == 10 | `article_pdca` | `finalize` |
| `article_pdca` | `run_article_iter` | 上記以外 | `article_pdca` | `run_article_iter` |
| `material_pdca` | `material_fallback` | 常に（material_fallback_count++ / material_iter=0 リセット） | `material_pdca` | `run_material_iter` |
| `article_pdca` | `finalize` | 常に | `done` | `done` |
| `done` | `done` | — | `done` | `done` |

**有効な `next_action` の phase別制約:**

| phase | 有効な next_action 値 |
|---|---|
| `layer1` | `run_strategist`, `run_eval_designer` |
| `material_pdca` | `run_material_iter`, `material_fallback` |
| `article_pdca` | `run_article_iter`, `finalize` |
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

```json
{
  "phase": "material_pdca",
  "next_action": "run_material_iter",
  "material_iter": 0,
  "article_iter": 3,
  "material_fallback_count": 1,
  "best_material_score": 0.80,
  "best_article_score": 0.62,
  "best_material_iter": 3,
  "best_article_iter": 2,
  "last_updated": "2026-04-20T12:45:00+09:00"
}
```

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
def compute_article_metrics(article_text: str) -> dict:
    """
    記事テキストから定量メトリクスを計算する。

    Args:
        article_text: 評価対象の記事テキスト（Markdown形式）

    Returns:
        dict:
            - code_ratio (float): コードブロック文字数 / 全文字数（0.0〜1.0）
            - desu_masu_ratio (float): です・ます体の文末比率（0.0〜1.0）
            - consecutive_same_length (int): 同一文字数の段落が連続する最大連続数
            - char_count (int): 記事全体の文字数（スペース・改行含む）
    """
    ...


def check_hard_fail(metrics: dict) -> tuple[bool, str, float]:
    """
    ハードフェイル条件を判定する。

    ハードフェイル条件:
        1. desu_masu_ratio < 0.80 → スコア上限 0.60
        2. char_count < 3000 → スコア上限 0.50
        3. consecutive_same_length >= 4 → スコア上限 0.70

    Args:
        metrics: compute_article_metrics() の返り値

    Returns:
        tuple:
            - is_hard_fail (bool): いずれかのハードフェイル条件に該当する場合 True
            - reason (str): 該当した条件の説明（複数の場合は最初にヒットした条件）
            - score_cap (float): 適用されるスコア上限値（ハードフェイルなしの場合 1.0）
    """
    ...


def apply_hard_fail(score: float, metrics: dict) -> float:
    """
    ハードフェイルキャップを適用したスコアを返す。

    Args:
        score: 評価エージェントが算出した生スコア（0.0〜1.0）
        metrics: compute_article_metrics() の返り値

    Returns:
        float: ハードフェイルキャップ適用後のスコア（score と score_cap の小さい方）
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
def load_fb_log(path: Path) -> dict:
    """
    フィードバックログファイルを読み込む。

    Args:
        path: fb_log.json のパス（Paths.FB_LOG）

    Returns:
        dict:
            - entries (list): フィードバックエントリのリスト
            - diffs (list): イテレーション間スコア差分のリスト
        ファイルが存在しない場合: {"entries": [], "diffs": []}
    """
    ...


def save_fb_log(path: Path, entries: list, diffs: list) -> None:
    """
    フィードバックログをファイルに保存する。

    【v5.1修正】diffs には必ず compute_fb_diff(entries) の結果を渡すこと。
    空リスト [] を渡すと差分追跡が機能しなくなる（v5.0バグ再現）。

    Args:
        path: 書き込み先パス（Paths.FB_LOG）
        entries: record_fb() で構築したエントリリスト
        diffs: compute_fb_diff() が返す差分リスト

    Returns:
        None
    """
    ...


def record_fb(entries: list, iter_num: int, score: float, feedback: str) -> list:
    """
    新しいフィードバックエントリをリストに追加する。

    Args:
        entries: 既存のエントリリスト（load_fb_log()["entries"]）
        iter_num: イテレーション番号（checkpoint の article_iter または material_iter）
        score: 当該イテレーションのスコア（0.0〜1.0）
        feedback: レビューエージェントが生成したフィードバックテキスト

    Returns:
        list: 新エントリを追加した updated entries リスト

    エントリ構造:
        {"iter": int, "score": float, "feedback": str, "timestamp": "ISO8601"}
    """
    ...


def compute_fb_diff(entries: list) -> list:
    """
    イテレーション間のスコア差分を計算する。

    Args:
        entries: record_fb() で構築したエントリリスト

    Returns:
        list of dict:
            - iter (int): イテレーション番号（N番目の差分はN-1→Nの変化）
            - score_delta (float): 前イテレーションからのスコア変化量（正=改善、負=悪化）
            - resolved (bool): score_delta > 0.0 の場合 True（改善したと見なす）

    注意: entries が1件以下の場合は空リストを返す
    """
    ...


def check_fb_stagnation(entries: list, window: int = 3) -> bool:
    """
    直近 `window` イテレーションでスコアが停滞しているか判定する。

    停滞判定: 直近 window 件のスコアの最大値と最小値の差が 0.01 以下

    Args:
        entries: フィードバックエントリリスト
        window: 判定対象の直近イテレーション数（デフォルト: 3）

    Returns:
        bool: 停滞している場合 True、entries が window 件未満の場合 False
    """
    ...
```

---

### 3.4 stagnation_check.py（NEW）

停滞検出の専用モジュール。`fb_log.py` の `check_fb_stagnation` より詳細な分析を提供します。

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
    チェックポイントから次のアクション識別子を返す。

    状態の整合性検証を行い、不正な状態の場合は ValueError を送出する。

    検証項目:
        - phase と next_action の組み合わせが状態遷移テーブルに従っているか
        - material_iter が 0〜5 の範囲内か
        - article_iter が 0〜10 の範囲内か
        - material_fallback_count が 0〜2 の範囲内か

    Args:
        checkpoint: read_checkpoint() が返す状態 dict

    Returns:
        str: checkpoint["next_action"] の値

    Raises:
        ValueError: 状態が不正（遷移テーブル違反、範囲外の値）の場合
    """
    ...


def is_complete(checkpoint: dict) -> bool:
    """
    チェックポイントが完了状態かを判定する。

    Args:
        checkpoint: チェックポイント状態 dict

    Returns:
        bool: phase == "done" の場合 True
    """
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

*TECH_SPEC.md 終了 — Zenn記事生成 v5.1 スキルベースシステム*
