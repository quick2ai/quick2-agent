from __future__ import annotations

import os
import yaml
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

RATING_MAP = {"A": "Could teach it", "B": "Solid grasp", "C": "Rough idea", "D": "Unknown"}
RATING_SCORES = {"A": 1.0, "B": 0.7, "C": 0.35, "D": 0.0}


def load_questions() -> list[dict]:
    """Load all questions from questions.yaml, flattened with domain metadata."""
    with open(DATA_DIR / "questions.yaml", "r") as f:
        data = yaml.safe_load(f)

    questions = []
    for domain in data["domains"]:
        for q in domain["questions"]:
            questions.append({
                "id": q["id"],
                "text": q["text"],
                "difficulty": q["difficulty"],
                "domain": domain["name"],
                "domain_weight": domain["weight"],
            })
    return questions


def get_question_by_index(index: int) -> dict | None:
    """Get a specific question by its index in the flat list."""
    questions = load_questions()
    if 0 <= index < len(questions):
        return questions[index]
    return None


def get_total_questions() -> int:
    return len(load_questions())


def get_domains() -> list[dict]:
    """Get domain names and weights."""
    with open(DATA_DIR / "questions.yaml", "r") as f:
        data = yaml.safe_load(f)
    return [{"name": d["name"], "weight": d["weight"]} for d in data["domains"]]
