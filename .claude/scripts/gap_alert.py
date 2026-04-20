"""Gap alert formatting for PDCA loops.

Called when stagnation_check.should_trigger_gap_alert() returns True.
Deterministic logic only — no LLM judgment.
"""

from __future__ import annotations

from collections import Counter
from typing import List


def compute_gap(current_score: float, threshold: float) -> float:
    """Returns threshold - current_score, rounded to 4 decimal places."""
    return round(threshold - current_score, 4)


def extract_recurring_issues(feedback_history: List[dict], top_n: int = 3) -> List[str]:
    """Extract most frequently mentioned issue keywords from feedback entries.

    Args:
        feedback_history: List of dicts with "feedback" or "description" key.
        top_n: Number of top issues to return.
    """
    all_text = " ".join(
        e.get("feedback", e.get("description", ""))
        for e in feedback_history
    )
    words = [w.strip("。、,.!！?？()（）「」") for w in all_text.split() if len(w) > 3]
    counter = Counter(words)
    return [word for word, _ in counter.most_common(top_n)]


def format_gap_alert(
    current_score: float,
    threshold: float,
    feedback_history: List[dict],
) -> str:
    """Format a gap alert message for inclusion in the next iteration prompt.

    Args:
        current_score: Latest iteration score.
        threshold: Target threshold (0.85 for material, 0.80 for article).
        feedback_history: Previous iteration feedback entries.
    """
    gap = compute_gap(current_score, threshold)
    issues = extract_recurring_issues(feedback_history)
    issues_str = "\n".join(f"  - {issue}" for issue in issues) if issues else "  (特定できず)"
    return (
        f"[GAP ALERT] スコア停滞を検出しました\n"
        f"  現在スコア : {current_score:.2f}\n"
        f"  目標スコア : {threshold:.2f}\n"
        f"  ギャップ   : {gap:.2f}\n"
        f"  頻出未解決課題:\n{issues_str}\n"
        f"  → 次のイテレーションではこれらの課題に集中してください。"
    )
