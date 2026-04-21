"""Canonical file path registry for v5.1 skillbase.

All generated file paths are centralized here. Hard-coding paths elsewhere
is prohibited. Agent Editor / workflow.json removed in v5.1.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Default output dir: repo_root/output/{ARTICLE_ID} if env var is set, else repo_root/output/
_BASE_OUTPUT = Path(__file__).parent.parent.parent / "output"
_ARTICLE_ID = os.environ.get("ARTICLE_ID", "").strip()
DEFAULT_OUTPUT_DIR = _BASE_OUTPUT / _ARTICLE_ID if _ARTICLE_ID else _BASE_OUTPUT


class Paths:
    """Registry of all generated file paths."""

    # Layer 1
    STRATEGY = "strategy.md"
    EVAL_CRITERIA = "eval_criteria.md"
    MATERIAL_EVAL_CRITERIA = "material_eval_criteria.md"

    # Phase 0
    KB_TRENDS = "knowledge/trends.md"
    KB_READER_PAINS = "knowledge/reader_pains.md"
    KB_EXPERIENCE_LOG = "knowledge/experience_log.md"
    KB_DRAMA_RAW = "knowledge/drama_raw.md"

    # Phase 1
    THESIS = "thesis.md"

    # Phase 2 (material PDCA)
    MAT_REVIEW = "material_reviews/{iter}/review.json"

    # Phase 3 (article PDCA)
    ARTICLE = "iterations/{N}/article.md"
    ARTICLE_REVIEW = "iterations/{N}/review.json"
    STYLE_GUIDE = "style_memory/style_guide.md"
    AGENT_MEMORY = "agent_memory/memory.json"

    # Shared
    FB_LOG = "fb_log.json"
    CHECKPOINT = "checkpoint.json"
    FINAL_ARTICLE = "final_article.md"
    REPORT = "report.json"


@dataclass
class FileSchema:
    """Validation rules for a generated file."""
    min_size: int
    format: str  # "markdown" | "json"
    required_patterns: list[str] = field(default_factory=list)
    json_schema: dict | None = None


REVIEW_SCHEMA: dict = {
    "type": "object",
    "required": ["axes", "weighted_average"],
    "properties": {
        "axes": {"type": "object"},
        "weighted_average": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

FB_LOG_SCHEMA: dict = {
    "type": "object",
    "required": ["entries", "diffs"],
    "properties": {
        "entries": {"type": "array"},
        "diffs": {"type": "array"},
    },
}

FILE_SCHEMAS: dict[str, FileSchema] = {
    "STRATEGY": FileSchema(
        min_size=500, format="markdown",
        required_patterns=[r"^#{1,3}.*戦略|Strategy|Tone|Core Message"],
    ),
    "EVAL_CRITERIA": FileSchema(
        min_size=500, format="markdown",
        required_patterns=[r"^#{1,3}.*(Axes|軸|評価)"],
    ),
    "THESIS": FileSchema(min_size=200, format="markdown"),
    "MAT_REVIEW": FileSchema(min_size=0, format="json", json_schema=REVIEW_SCHEMA),
    "ARTICLE": FileSchema(min_size=3000, format="markdown"),
    "ARTICLE_REVIEW": FileSchema(min_size=0, format="json", json_schema=REVIEW_SCHEMA),
    "STYLE_GUIDE": FileSchema(min_size=100, format="markdown"),
    "FB_LOG": FileSchema(min_size=0, format="json", json_schema=FB_LOG_SCHEMA),
}

PHASE_INPUTS: dict[str, list[str]] = {
    "layer1": [],
    "phase0": ["STRATEGY"],
    "phase1": ["STRATEGY", "KB_TRENDS", "KB_READER_PAINS"],
    "experience_authoring": ["STRATEGY", "KB_TRENDS", "EVAL_CRITERIA"],
    "material_pdca": ["THESIS", "EVAL_CRITERIA", "KB_EXPERIENCE_LOG"],
    "article_pdca": ["STYLE_GUIDE", "EVAL_CRITERIA", "AGENT_MEMORY"],
}

_REGISTRY: dict[str, str] = {
    name: value
    for name, value in vars(Paths).items()
    if not name.startswith("_")
}


def resolve_path(key: str, output_dir: str | Path | None = None, **kwargs: object) -> str:
    """Resolve a registry key to a file path.

    Args:
        key: Registry key (e.g. "ARTICLE").
        output_dir: Base directory. Defaults to DEFAULT_OUTPUT_DIR.
        **kwargs: Template variables (e.g. N=1, iter=2).
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    if key not in _REGISTRY:
        raise KeyError(f"Unknown registry key: {key}")
    relative = _REGISTRY[key].format(**kwargs)
    return os.path.join(str(output_dir), relative)
