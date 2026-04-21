"""
Dry-run validation for zenn-article-gen-final-skillbase v5.1

What this checks:
  1. All 6 Python scripts import without errors
  2. checkpoint.py state machine walks correctly (fresh → layer1 → material_pdca → article_pdca → done)
  3. MATERIAL_FALLBACK transition works
  4. metrics.py HARD FAIL caps apply correctly
  5. fb_log.py diffs bug fix works (no empty diffs)
  6. stagnation_check.py + gap_alert.py behave correctly
  7. Prints full spawn plan (no actual agent calls)

Run: python3 dry_run_validate.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".claude", "scripts"))

PASS = "✅"
FAIL = "❌"
results = []

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((status, name, detail))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))

print("\n" + "="*60)
print("  Zenn Article Gen v5.1 — Dry Run Validation")
print("="*60)

# ─────────────────────────────────────────────
print("\n[1] Import checks")
# ─────────────────────────────────────────────
modules = {}
for mod_name in ["file_registry", "metrics", "fb_log", "stagnation_check", "gap_alert", "checkpoint"]:
    try:
        import importlib
        m = importlib.import_module(mod_name)
        modules[mod_name] = m
        check(f"import {mod_name}", True)
    except Exception as e:
        check(f"import {mod_name}", False, str(e))

# ─────────────────────────────────────────────
print("\n[2] checkpoint.py — state machine walk")
# ─────────────────────────────────────────────
cp_mod = modules.get("checkpoint")
if cp_mod:
    from pathlib import Path
    import tempfile, json

    with tempfile.TemporaryDirectory() as tmpdir:
        cp_path = Path(tmpdir) / "checkpoint.json"

        # Fresh start
        cp = cp_mod.read_checkpoint(cp_path)
        check("fresh start → layer1/run_strategist",
              cp["phase"] == "layer1" and cp["next_action"] == "run_strategist")

        # Layer 1: strategist → eval_designer
        cp = cp_mod.advance_layer1(cp, "strategist")
        check("layer1: strategist → run_eval_designer",
              cp["next_action"] == "run_eval_designer")

        # Layer 1: eval_designer → topic_selection
        cp = cp_mod.advance_layer1(cp, "eval_designer")
        check("layer1: eval_designer → topic_selection/run_topic_selector",
              cp["phase"] == "topic_selection" and cp["next_action"] == "run_topic_selector")

        # topic_selection → material_pdca
        cp = cp_mod.advance_topic_selection(cp)
        check("topic_selection: run_topic_selector → material_pdca/run_material_iter",
              cp["phase"] == "material_pdca" and cp["next_action"] == "run_material_iter")

        # Material PDCA: iter 1, score=0.72 (below threshold, continue)
        cp = cp_mod.advance_material_iter(cp, score=0.72)
        check("material iter 1 (0.72 < 0.85) → run_material_iter",
              cp["next_action"] == "run_material_iter" and cp["material_iter"] == 1)

        # Material PDCA: iter 2, score=0.80 (below threshold, continue)
        cp = cp_mod.advance_material_iter(cp, score=0.80)
        check("material iter 2 (0.80 < 0.85) → run_material_iter",
              cp["next_action"] == "run_material_iter")

        # Material PDCA: iter 3, score=0.87 (above threshold → article)
        cp = cp_mod.advance_material_iter(cp, score=0.87)
        check("material iter 3 (0.87 >= 0.85) → article_pdca",
              cp["phase"] == "article_pdca" and cp["next_action"] == "run_article_iter")
        check("best_material_score updated to 0.87",
              cp["best_material_score"] == 0.87)

        # Article PDCA: iter 1, score=0.68 (below, continue)
        cp = cp_mod.advance_article_iter(cp, score=0.68)
        check("article iter 1 (0.68) → run_article_iter",
              cp["next_action"] == "run_article_iter")

        # Article PDCA: iter 2, score=0.65 (below, continue)
        cp = cp_mod.advance_article_iter(cp, score=0.65)
        check("article iter 2 (0.65) → run_article_iter",
              cp["next_action"] == "run_article_iter")

        # Article PDCA: iter 3, score=0.63 (<0.70, fallback_count=0 → MATERIAL_FALLBACK)
        cp = cp_mod.advance_article_iter(cp, score=0.63)
        check("article iter 3 (0.63 < 0.70, fallbacks=0) → material_fallback",
              cp["next_action"] == "material_fallback")

        # Trigger fallback
        cp = cp_mod.trigger_material_fallback(cp)
        check("material_fallback → material_pdca, fallback_count=1, article_iter=0",
              cp["phase"] == "material_pdca"
              and cp["material_fallback_count"] == 1
              and cp["article_iter"] == 0)
        check("material_fallback → material_iter reset to 0 (A-1 fix)",
              cp["material_iter"] == 0)

        # Back to article, iter 3, score=0.62 (<0.70, fallback_count=1 → still can fallback)
        cp["phase"] = "article_pdca"
        cp["article_iter"] = 2
        cp = cp_mod.advance_article_iter(cp, score=0.62)
        check("article iter 3 again (fallback_count=1 < 2) → material_fallback again",
              cp["next_action"] == "material_fallback")

        # Now fallback_count = 2: no more fallback
        cp = cp_mod.trigger_material_fallback(cp)
        cp["phase"] = "article_pdca"
        cp["article_iter"] = 2
        cp = cp_mod.advance_article_iter(cp, score=0.61)
        check("article iter 3 (fallback_count=2 → no more fallback) → run_article_iter",
              cp["next_action"] == "run_article_iter")

        # Article: score >= threshold AT iter >= 3 → consolidate (FIX-6)
        cp = cp_mod.advance_article_iter(cp, score=0.82)
        check("article score >= 0.80 at iter >= 3 → consolidate (FIX-6)",
              cp["next_action"] == "consolidate")

        # consolidate → finalize (FIX-6)
        cp = cp_mod.advance_after_consolidate(cp, final_score=0.82)
        check("advance_after_consolidate → finalize (FIX-6)",
              cp["next_action"] == "finalize")

        # Mark done
        cp = cp_mod.mark_done(cp)
        check("mark_done → phase=done",
              cp_mod.is_complete(cp))

        # write/read roundtrip
        cp_mod.write_checkpoint(cp_path, cp)
        cp2 = cp_mod.read_checkpoint(cp_path)
        check("checkpoint write/read roundtrip",
              cp2["phase"] == "done" and "last_updated" in cp2 and cp2["last_updated"] is not None)

        # Max iter → finalize (no score threshold hit)
        cp_reset = cp_mod.read_checkpoint(Path(tmpdir) / "cp2.json")
        cp_reset = cp_mod.advance_layer1(cp_reset, "strategist")
        cp_reset = cp_mod.advance_layer1(cp_reset, "eval_designer")
        for _ in range(5):
            cp_reset = cp_mod.advance_material_iter(cp_reset, score=0.70)
        check("material max iter (5) → article_pdca",
              cp_reset["phase"] == "article_pdca" and cp_reset["material_iter"] == 5)
        for _ in range(10):
            cp_reset = cp_mod.advance_article_iter(cp_reset, score=0.70, fallback_max=0)
        check("article max iter (10) → consolidate (FIX-6)",
              cp_reset["next_action"] == "consolidate" and cp_reset["article_iter"] == 10)

# ─────────────────────────────────────────────
print("\n[3] metrics.py — HARD FAIL caps")
# ─────────────────────────────────────────────
met_mod = modules.get("metrics")
if met_mod:
    # code_ratio > 20% → HARD FAIL applied, score capped (may apply lowest of multiple caps)
    heavy_code = "\n".join(
        ["```python"] + ["x = 1"] * 25 + ["```"] + ["これはテキストです。"] * 5
    )
    m = met_mod.compute_article_metrics(heavy_code)
    hf = met_mod.check_hard_fail(m)
    score = met_mod.apply_hard_fail(0.85, hf)
    check("code_ratio > 20% → HARD FAIL applied, score < original 0.85",
          hf.applied and score < 0.85,
          f"code_ratio={m.code_ratio:.2f}, score={score:.2f} (capped from 0.85)")

    # desu_masu < 80% → cap 0.55
    da_text = "\n".join(["これは問題だ。" * 5, "これも問題である。" * 5, "なるほどです。"])
    m2 = met_mod.compute_article_metrics(da_text)
    hf2 = met_mod.check_hard_fail(m2)
    check("desu_masu < 80% → HARD FAIL applied",
          hf2.applied,
          f"desu_masu_ratio={m2.desu_masu_ratio:.2f}, applied={hf2.applied}")

    # Normal article → no HARD FAIL (varied sentences, enough desu/masu, little code)
    normal_lines = [
        "Claude Codeを使ってZenn記事を自動生成するシステムを作りました。",
        "最初は簡単だと思っていましたが、PDCAループの設計が意外と難しかったです。",
        "特にネストしたPDCAの状態管理には苦労しました。",
        "checkpoint.jsonを使ったセッション断絶耐性の実装が鍵になっています。",
        "この記事ではその試行錯誤の過程を共有します。",
        "結果として、サブスクリプション内で動作するシステムが完成しました。",
        "コストは月額固定のみで、追加のAPI費用は発生しません。",
        "ぜひ参考にしていただければと思います。",
    ]
    normal = "\n".join(normal_lines)
    m3 = met_mod.compute_article_metrics(normal)
    hf3 = met_mod.check_hard_fail(m3)
    check("varied normal article → no HARD FAIL",
          not hf3.applied,
          f"code_ratio={m3.code_ratio:.2f}, desu_masu={m3.desu_masu_ratio:.2f}, consec={m3.max_consecutive_same_length}")

# ─────────────────────────────────────────────
print("\n[4] fb_log.py — diffs bug fix")
# ─────────────────────────────────────────────
fb_mod = modules.get("fb_log")
if fb_mod:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "fb_log.json")
        # Create some entries
        entries = [
            fb_mod.FBEntry("FB-A-001", 1, "article", "構成", "major", "構成が悪い", "new", 1),
            fb_mod.FBEntry("FB-A-002", 1, "article", "文体", "minor", "文体が揺れている", "new", 1),
        ]
        # v5.0 bug: save_fb_log(path, entries, []) → now auto-computes diffs
        fb_mod.save_fb_log(path, entries, [])
        with open(path) as f:
            data = json.load(f)
        check("save_fb_log with empty diffs → auto-computes diffs (bug fix)",
              len(data["diffs"]) > 0,
              f"diffs count: {len(data['diffs'])}")

        # load_fb_log roundtrip
        loaded = fb_mod.load_fb_log(path)
        check("load_fb_log roundtrip",
              len(loaded) == 2 and loaded[0].id == "FB-A-001")

        # record_fb: iter 2, one feedback resolved, one persisted
        new_fbs = [{"axis": "文体", "severity": "minor", "text": "まだ揺れあり"}]
        updated = fb_mod.record_fb(entries, new_fbs, iteration=2, phase="article")
        resolved = [e for e in updated if e.status == "resolved"]
        persisted = [e for e in updated if e.status == "persisted"]
        check("record_fb: 構成=resolved, 文体=persisted",
              len(resolved) == 1 and len(persisted) == 1)

# ─────────────────────────────────────────────
print("\n[5] stagnation_check.py + gap_alert.py")
# ─────────────────────────────────────────────
stag_mod = modules.get("stagnation_check")
gap_mod = modules.get("gap_alert")
if stag_mod and gap_mod:
    # Stagnation: 3 consecutive same score
    entries_stag = [{"score": 0.72}, {"score": 0.72}, {"score": 0.73}]
    check("detect_stagnation (Δ=0.01 over window=3) → True",
          stag_mod.detect_stagnation(entries_stag, window=3))

    # No stagnation: clear improvement
    entries_ok = [{"score": 0.70}, {"score": 0.75}, {"score": 0.80}]
    check("detect_stagnation (improving scores) → False",
          not stag_mod.detect_stagnation(entries_ok, window=3))

    # gap_alert trigger
    check("should_trigger_gap_alert (stagnated, below threshold=0.80) → True",
          stag_mod.should_trigger_gap_alert(entries_stag, threshold=0.80))

    # No trigger when above threshold
    entries_above = [{"score": 0.82}, {"score": 0.82}, {"score": 0.83}]
    check("should_trigger_gap_alert (above threshold) → False",
          not stag_mod.should_trigger_gap_alert(entries_above, threshold=0.80))

    # gap_alert format
    fb_hist = [
        {"feedback": "冒頭フックが弱い 構成が弱い"},
        {"feedback": "冒頭フックが弱い 文体が揺れている"},
    ]
    alert = gap_mod.format_gap_alert(0.72, 0.80, fb_hist)
    check("format_gap_alert returns non-empty string with GAP ALERT",
          "GAP ALERT" in alert and "0.72" in alert,
          alert.split("\n")[0])

# ─────────────────────────────────────────────
print("\n[5b] Phase 1 FIX verification (FIX-1..6)")
# ─────────────────────────────────────────────

# T1: fix_code_ratio
if met_mod:
    dense_lines = ["普通の文章です。" for _ in range(6)] + ["```python"]
    dense_lines += ["# a comment line"] * 5
    dense_lines += [""] * 5
    dense_lines += ["x = 1"] * 20
    dense_lines += ["```"]
    dense = "\n".join(dense_lines)
    before_m = met_mod.compute_article_metrics(dense)
    fixed = met_mod.fix_code_ratio(dense, target_ratio=0.50)
    after_m = met_mod.compute_article_metrics(fixed)
    check("FIX-1 fix_code_ratio: ratio decreased after strip",
          after_m.code_ratio < before_m.code_ratio,
          f"before={before_m.code_ratio:.2f} after={after_m.code_ratio:.2f}")
    check("FIX-1 fix_code_ratio: no substantive code lost",
          fixed.count("x = 1") == 20)

# T2: apply_major_penalty
if met_mod:
    check("FIX-2 apply_major_penalty: major=0 passthrough",
          met_mod.apply_major_penalty(0.90, 0) == 0.90)
    check("FIX-2 apply_major_penalty: major=1 cap to 0.78",
          met_mod.apply_major_penalty(0.90, 1) == 0.78)
    check("FIX-2 apply_major_penalty: major=2 cap to 0.79",
          met_mod.apply_major_penalty(0.86, 2) == 0.79)
    check("FIX-2 apply_major_penalty: major=3 cap to 0.70",
          met_mod.apply_major_penalty(0.95, 3) == 0.70)
    check("FIX-2 apply_major_penalty: below cap not raised",
          met_mod.apply_major_penalty(0.50, 2) == 0.50)

# T3: fb_log duplicate stagnation removed
if fb_mod:
    check("FIX-3 check_fb_stagnation removed",
          not hasattr(fb_mod, "check_fb_stagnation"))
    check("FIX-3 StagnationResult removed",
          not hasattr(fb_mod, "StagnationResult"))

# T4: trigger_material_fallback resets best_article
if cp_mod:
    cp_fb = dict(cp_mod.FRESH_STATE)
    cp_fb.update({
        "phase": "article_pdca", "article_iter": 3,
        "best_article_iter": 2, "best_article_score": 0.75,
    })
    cp_after = cp_mod.trigger_material_fallback(cp_fb)
    check("FIX-4 fallback resets best_article_iter to None",
          cp_after["best_article_iter"] is None)
    check("FIX-4 fallback resets best_article_score to 0.0",
          cp_after["best_article_score"] == 0.0)
    check("FIX-4 fallback preserves material_fallback_count increment",
          cp_after["material_fallback_count"] == 1)

# T5, T6: advance_layer1 with requires_system_analysis
if cp_mod:
    cp_sa = dict(cp_mod.FRESH_STATE)
    cp_sa["next_action"] = "run_eval_designer"
    # requires=False → topic_selection
    cp_no_sa = cp_mod.advance_layer1(cp_sa, "eval_designer",
                                     requires_system_analysis=False)
    check("FIX-5 eval_designer (requires=False) → topic_selection/run_topic_selector",
          cp_no_sa["phase"] == "topic_selection"
          and cp_no_sa["next_action"] == "run_topic_selector")
    # requires=True → system_analyst
    cp_with_sa = cp_mod.advance_layer1(cp_sa, "eval_designer",
                                       requires_system_analysis=True)
    check("FIX-5 eval_designer (requires=True) → layer1/run_system_analyst",
          cp_with_sa["phase"] == "layer1"
          and cp_with_sa["next_action"] == "run_system_analyst")
    # system_analyst → topic_selection
    cp_after_sa = cp_mod.advance_layer1(cp_with_sa, "system_analyst")
    check("FIX-5 system_analyst done → topic_selection/run_topic_selector",
          cp_after_sa["phase"] == "topic_selection"
          and cp_after_sa["next_action"] == "run_topic_selector")
    # VALID_TRANSITIONS check
    check("FIX-5 VALID_TRANSITIONS[layer1] includes run_system_analyst",
          "run_system_analyst" in cp_mod.VALID_TRANSITIONS["layer1"])

# T7, T8: consolidate routing
if cp_mod:
    # iter 1 threshold pass → finalize (skip consolidator)
    cp_early = dict(cp_mod.FRESH_STATE)
    cp_early.update({"phase": "article_pdca", "article_iter": 0})
    cp_e1 = cp_mod.advance_article_iter(cp_early, score=0.82)
    check("FIX-6 iter 1 threshold pass → finalize (skip consolidate)",
          cp_e1["next_action"] == "finalize" and cp_e1["article_iter"] == 1)

    # iter 3 threshold pass → consolidate
    cp_mid = dict(cp_mod.FRESH_STATE)
    cp_mid.update({"phase": "article_pdca", "article_iter": 2,
                   "best_article_score": 0.70, "best_article_iter": 1})
    cp_m3 = cp_mod.advance_article_iter(cp_mid, score=0.83)
    check("FIX-6 iter 3 threshold pass → consolidate",
          cp_m3["next_action"] == "consolidate" and cp_m3["article_iter"] == 3)

    # advance_after_consolidate exists
    cp_post = cp_mod.advance_after_consolidate(cp_m3, final_score=0.83)
    check("FIX-6 advance_after_consolidate → finalize",
          cp_post["next_action"] == "finalize")

    # VALID_TRANSITIONS check
    check("FIX-6 VALID_TRANSITIONS[article_pdca] includes consolidate",
          "consolidate" in cp_mod.VALID_TRANSITIONS["article_pdca"])

# ─────────────────────────────────────────────
print("\n[6] Spawn plan walkthrough (no actual agents)")
# ─────────────────────────────────────────────
print("  Simulated execution path:")
plan = [
    ("layer1",       "run_strategist",    "→ Spawn: strategist     → writes output/strategy.md"),
    ("layer1",       "run_eval_designer", "→ Spawn: eval_designer  → writes output/eval_criteria.md"),
    ("material_pdca","run_material_iter", "→ Skill: zenn-material-pdca (iter 1)"),
    ("",             "  [iter 1]",        "  → [parallel] TrendResearcher → knowledge/trends.md"),
    ("",             "  [iter 1]",        "  → [parallel] PainExtractor   → knowledge/reader_pains.md"),
    ("",             "  [iter 1]",        "  → [serial]   ThesisDesigner  → thesis.md"),
    ("",             "  [iter 1]",        "  → [serial]   MaterialReviewer → material_reviews/1/review.json"),
    ("material_pdca","run_material_iter", "→ Skill: zenn-material-pdca (iter 2 ... if score < 0.85)"),
    ("article_pdca", "run_article_iter",  "→ Skill: zenn-article-pdca (iter 1)"),
    ("",             "  [iter 1]",        "  → [serial] Writer             → iterations/1/article.md"),
    ("",             "  [iter 1]",        "  → [python] HARD FAIL check    → apply_hard_fail()"),
    ("",             "  [iter 1]",        "  → [serial] StyleGuideUpdater  → style_memory/style_guide.md"),
    ("",             "  [iter 1]",        "  → [serial] ArticleReviewer    → iterations/1/review.json"),
    ("article_pdca", "run_article_iter",  "→ Skill: zenn-article-pdca (iter 5 + Consolidator)"),
    ("article_pdca", "finalize",          "→ Spawn: finalizer       → output/final_article.md"),
    ("done",         "done",              "→ stdout: report.json"),
]
for phase, action, desc in plan:
    prefix = f"  [{phase:<12}] {action:<20}" if phase else f"  {' '*34}"
    print(f"  {prefix} {desc}")

check("spawn plan printed without errors", True)

# ─────────────────────────────────────────────
print("\n" + "="*60)
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"  Results: {passed} passed / {failed} failed / {passed+failed} total")
print("="*60)
if failed > 0:
    print("\nFailed checks:")
    for s, name, detail in results:
        if s == FAIL:
            print(f"  {FAIL} {name}: {detail}")
    sys.exit(1)
else:
    print("\n  All checks passed. Ready for E2E test (P8).")
