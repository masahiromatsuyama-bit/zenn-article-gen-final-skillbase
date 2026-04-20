# 本番テスト — 自己記事生成ラン

作業ディレクトリ: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/`

---

## このセッションの目的

**このシステム自体を題材にした Zenn 記事を、このシステムを使って生成する**。

「Claude Code スキルベースで Zenn 記事自動生成システムを試行錯誤しながら作った話」を
記事テーマとし、システムのコードを唯一の素材源として End-to-End ラン（Layer1 → Material PDCA → Article PDCA → Finalize）を完走させる。

**本番同様テスト**なので、品質基準・HARD FAIL チェック・checkpoint 耐性を含め、
実際に output/final_article.md と report.json が生成されることを確認する。

---

## 記事仕様

### タイトル案（Strategist が最終決定）
「Claude Code サブスク内で動く Zenn 記事自動生成システムを試行錯誤して作った話」

### 伝えたいこと（article_intent）

1. **きっかけと問題意識**: Anthropic API 直接呼び出し（$12-15/run）からコスト爆死し、Claude Code サブスク内で動かすアーキテクチャへ再設計した経緯
2. **設計上の工夫**: ネストした PDCA ループ（素材 × 記事）、checkpoint.json によるセッション断絶耐性、10KB ルールで SubAgent の context 汚染を防ぐ設計
3. **試行錯誤と失敗**: HARD FAIL 判定の仕様矛盾（ドキュメント 3 箇所でキャップ値が全部違う）、MATERIAL_FALLBACK の回数制限が 1 箇所だけ「1回」になっていたバグ、checkpoint 破損時のクラッシュバグ
4. **学んだこと**: 「LLM が自分のコードを書いたドキュメントを信用してはいけない」、spec-as-code（dry_run_validate.py で仕様を実行可能テストとして持つ）の価値
5. **数値で語る**: Material PDCA max 5 iter / Article PDCA max 10 iter / HARD FAIL cap 3 種類の具体的な閾値

### 読者像

- Claude Code を使いこなしたい中上級エンジニア
- LLM を使ったソフトウェア開発の設計論に興味がある人
- 「コストを抑えつつ AI エージェントを使い倒したい」という動機を持つ人

### 文体・スタイル

- です・ます体（80%以上）
- コードブロックは説明に必要な箇所のみ（20%未満）
- 体験記・一人称視点。技術論文ではなくエンジニアのブログ記事
- 文字数: 4000〜6000 字

---

## SystemAnalyst への指示（requires_system_analysis: true）

Strategist は `strategy.md` に以下を含めること:

```
requires_system_analysis: true
system_analysis_dirs:
  - .claude/scripts/
  - .claude/skills/zenn-orchestrator/
  - .claude/skills/zenn-material-pdca/
  - .claude/skills/zenn-article-pdca/
  - .claude/agents/
  - dry_run_validate.py
  - ARCHITECTURE.md
  - REQUIREMENTS.md
  - TECH_SPEC.md
```

SystemAnalyst は上記ファイル群を全読みし、
`output/knowledge/system_analysis.md` に記事素材ドキュメントを書き込む。
ThesisDesigner と Writer はこのファイルを trends.md / reader_pains.md と並列に参照する。

---

## 実行手順

```
1. output/ ディレクトリをクリーンな状態にする（前回ランの残骸を消す）
   rm -rf output/ && mkdir -p output/knowledge output/material_reviews output/iterations

2. `/zenn-orchestrator` を呼び出して実行開始
```

### 実行後に確認してほしいこと

| 確認項目 | 期待値 |
|---|---|
| `output/checkpoint.json` が各ステップ後に更新されているか | phase/next_action が正しく遷移する |
| `output/knowledge/system_analysis.md` が生成されているか | SystemAnalyst が呼ばれている |
| Material PDCA スコアが各 iter で変化しているか | 停滞なら gap_alert が発火 |
| Article PDCA の HARD FAIL チェックが機能しているか | code_ratio/desu_masu/consecutive |
| `output/final_article.md` が生成されるか | 4000 字以上の記事本文 |
| `output/report.json` の内容 | 最終スコア・iter 数・HARD FAIL 発動回数 |

---

## 完了後のフィードバック依頼

1. `output/final_article.md` の冒頭 500 字を見せて
2. `output/report.json` の全内容を見せて
3. 記事の出来について率直なフィードバックを頼む（読者目線で刺さるか、薄い箇所はどこか）
4. Material PDCA / Article PDCA のスコア推移グラフ（テキストで可）

---

## トラブルシュート用メモ

- checkpoint が壊れた場合: `rm output/checkpoint.json` して再実行（FRESH_STATE から再スタート）
- スコアが 0.70 以下で 3iter 続いた場合: MATERIAL_FALLBACK が発火し素材 PDCA に戻る（最大 2 回）
- HARD FAIL が連発する場合: `output/iterations/N/article.md` を直接確認してコード比率を見る
- セッション断絶した場合: このプロンプトをそのまま再実行すると checkpoint.json から再開する
