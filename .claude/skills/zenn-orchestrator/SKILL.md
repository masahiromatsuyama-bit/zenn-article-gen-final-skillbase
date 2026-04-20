name: zenn-orchestrator
description: >
  Zenn技術記事自動生成システムのLead orchestrator。
  checkpoint.jsonを読んでフェーズを判断し、Layer1→Material PDCA→Article PDCAの
  順に実行する。セッション断絶後の再開にも対応。
triggers:
  - "Zenn記事を生成して"
  - "記事生成を開始して"
  - "記事生成を再開して"
  - "zenn-orchestrator"
  - "記事を書いて"
capabilities:
  - checkpoint.jsonに基づくフェーズルーティング
  - Layer1（Strategist・EvalDesigner）の実行
  - Material PDCAループ管理（max 5 iter, threshold 0.85）
  - Article PDCAループ管理（max 10 iter, threshold 0.80）
  - MATERIAL_FALLBACKによる素材PDCAへの差し戻し
  - セッション断絶後のcheckpoint.jsonからの再開
  - 完了時のreport.json出力
limitations:
  - 各PDCAイテレーションの詳細はzenn-material-pdca / zenn-article-pdcaに委譲
  - 並列spawn可能なのはPhase 0（TrendResearcher+PainExtractor）のみ
  - 1実行 = 1最終記事（複数記事の同時生成不可）
