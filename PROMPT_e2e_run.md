# E2Eテスト実行プロンプト

作業ディレクトリ: /Users/masahiromatsuyama/zenn-article-gen-final-skillbase/

## 指示

zenn-orchestratorスキルを使って、Zenn記事を1本生成してほしい。

### 記事テーマ
「Claude Code のスキルベースで Zenn 記事自動生成システムを作った話」
（Anthropic API直接呼び出し（$12-15/run）からClaude Codeサブスク内動作へのリアーキテクト体験記）

### 実行方法
`/zenn-orchestrator` を呼び出して開始する。
output/ ディレクトリに成果物が生成される。

### 確認してほしいこと
1. checkpoint.json が各ステップ後に正しく更新されているか
2. エージェントが output/ 以下の正しいパスにファイルを書いているか
3. Material PDCA / Article PDCA のスコアが各イテレーションで改善しているか
4. 最終的に output/final_article.md が生成されるか
5. report.json の内容（スコア・イテレーション数・HARD FAIL有無）

### 完了後
output/final_article.md の内容と report.json を見せて。
記事の出来について率直なフィードバックも頼む。
