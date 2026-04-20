"""checkpoint.json read/write for session-break recovery.

next_action field routes Lead without re-doing completed work.
Each skill reads checkpoint first; write after each step completes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

FRESH_STATE: Dict = {
    "phase": "layer1",
    "next_action": "run_strategist",
    "material_iter": 0,
    "article_iter": 0,
    "material_fallback_count": 0,
    "best_material_score": 0.0,
    "best_article_score": 0.0,
    "best_material_iter": None,
    "best_article_iter": None,
    "last_updated": None,
}

# Valid next_action values per phase
VALID_TRANSITIONS: Dict[str, list] = {
    "layer1": ["run_strategist", "run_eval_designer"],
    "material_pdca": ["run_material_iter", "material_fallback"],
    "article_pdca": ["run_article_iter", "material_fallback", "finalize"],
    "done": ["done"],
}


def read_checkpoint(path: Path) -> Dict:
    """If not exists, returns fresh start state (layer1 / run_strategist)."""
    if not path.exists():
        return dict(FRESH_STATE)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_checkpoint(path: Path, state: Dict) -> None:
    """Write checkpoint with current UTC timestamp."""
    state = dict(state)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def route_next_action(checkpoint: Dict) -> str:
    """Returns next_action from checkpoint."""
    return checkpoint.get("next_action", "run_strategist")


def is_complete(checkpoint: Dict) -> bool:
    """Returns True if phase == done."""
    return checkpoint.get("phase") == "done"


def advance_layer1(checkpoint: Dict, completed_step: str) -> Dict:
    """Advance layer1 state after Strategist or EvalDesigner completes."""
    cp = dict(checkpoint)
    if completed_step == "strategist":
        cp["next_action"] = "run_eval_designer"
    elif completed_step == "eval_designer":
        cp["phase"] = "material_pdca"
        cp["next_action"] = "run_material_iter"
    return cp


def advance_material_iter(
    checkpoint: Dict,
    score: float,
    threshold: float = 0.85,
    max_iter: int = 5,
) -> Dict:
    """Update checkpoint after a material PDCA iteration."""
    cp = dict(checkpoint)
    cp["material_iter"] += 1
    if score > cp["best_material_score"]:
        cp["best_material_score"] = score
        cp["best_material_iter"] = cp["material_iter"]

    if score >= threshold or cp["material_iter"] >= max_iter:
        cp["phase"] = "article_pdca"
        cp["next_action"] = "run_article_iter"
    else:
        cp["next_action"] = "run_material_iter"
    return cp


def advance_article_iter(
    checkpoint: Dict,
    score: float,
    threshold: float = 0.80,
    max_iter: int = 10,
    fallback_max: int = 2,
) -> Dict:
    """Update checkpoint after an article PDCA iteration."""
    cp = dict(checkpoint)
    cp["article_iter"] += 1
    if score > cp["best_article_score"]:
        cp["best_article_score"] = score
        cp["best_article_iter"] = cp["article_iter"]

    if score >= threshold:
        cp["next_action"] = "finalize"
    elif (
        cp["article_iter"] >= 3
        and score < 0.70
        and cp["material_fallback_count"] < fallback_max
    ):
        cp["next_action"] = "material_fallback"
    elif cp["article_iter"] >= max_iter:
        cp["next_action"] = "finalize"
    else:
        cp["next_action"] = "run_article_iter"
    return cp


def trigger_material_fallback(checkpoint: Dict) -> Dict:
    """Backtrack to material PDCA. Resets article_iter."""
    cp = dict(checkpoint)
    cp["phase"] = "material_pdca"
    cp["next_action"] = "run_material_iter"
    cp["material_fallback_count"] += 1
    cp["article_iter"] = 0
    return cp


def mark_done(checkpoint: Dict) -> Dict:
    """Mark execution as complete."""
    cp = dict(checkpoint)
    cp["phase"] = "done"
    cp["next_action"] = "done"
    return cp
