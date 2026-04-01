"""
Math puzzle generator for the safe.

Generates daily math problems seeded by date so codes change every day.
Supports configurable difficulty levels and problem counts.
"""

import hashlib
import random
from dataclasses import dataclass
from datetime import date


@dataclass
class MathProblem:
    id: int
    question: str
    answer: int  # The numerical code for this bar
    difficulty: str


def _daily_seed(day: date, salt: str = "math-safe-2024") -> int:
    """Deterministic seed from date so the same day always gives the same problems."""
    raw = f"{salt}-{day.isoformat()}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def _make_problem(rng: random.Random, difficulty: str, problem_id: int) -> MathProblem:
    """Generate a single math problem at the given difficulty."""
    if difficulty == "easy":
        return _easy_problem(rng, problem_id)
    elif difficulty == "medium":
        return _medium_problem(rng, problem_id)
    else:
        return _hard_problem(rng, problem_id)


def _easy_problem(rng: random.Random, pid: int) -> MathProblem:
    """Addition and subtraction with small numbers (ages 5-7)."""
    op = rng.choice(["+", "-"])
    if op == "+":
        a = rng.randint(1, 20)
        b = rng.randint(1, 20)
        return MathProblem(pid, f"{a} + {b}", a + b, "easy")
    else:
        a = rng.randint(5, 30)
        b = rng.randint(1, a)  # ensure non-negative result
        return MathProblem(pid, f"{a} - {b}", a - b, "easy")


def _medium_problem(rng: random.Random, pid: int) -> MathProblem:
    """Multiplication, division, and mixed operations (ages 8-10)."""
    kind = rng.choice(["multiply", "divide", "mixed"])
    if kind == "multiply":
        a = rng.randint(2, 12)
        b = rng.randint(2, 12)
        return MathProblem(pid, f"{a} x {b}", a * b, "medium")
    elif kind == "divide":
        b = rng.randint(2, 10)
        answer = rng.randint(2, 12)
        a = b * answer
        return MathProblem(pid, f"{a} / {b}", answer, "medium")
    else:
        a = rng.randint(10, 50)
        b = rng.randint(1, 20)
        c = rng.randint(1, 10)
        result = a + b - c
        return MathProblem(pid, f"{a} + {b} - {c}", result, "medium")


def _hard_problem(rng: random.Random, pid: int) -> MathProblem:
    """Order of operations, exponents, multi-step (ages 11+)."""
    kind = rng.choice(["order_of_ops", "square", "multi_step"])
    if kind == "order_of_ops":
        a = rng.randint(2, 10)
        b = rng.randint(2, 8)
        c = rng.randint(1, 15)
        result = a * b + c
        return MathProblem(pid, f"{a} x {b} + {c}", result, "hard")
    elif kind == "square":
        a = rng.randint(2, 12)
        return MathProblem(pid, f"{a} squared", a * a, "hard")
    else:
        a = rng.randint(10, 99)
        b = rng.randint(2, 9)
        c = rng.randint(2, 9)
        result = a - b * c
        return MathProblem(pid, f"{a} - {b} x {c}", result, "hard")


def generate_daily_problems(
    num_problems: int = 5,
    difficulty: str = "easy",
    day: date | None = None,
    custom_salt: str | None = None,
) -> list[MathProblem]:
    """
    Generate a set of math problems for the day.

    Args:
        num_problems: How many bars/problems (1-10)
        difficulty: "easy", "medium", or "hard"
        day: Which date to generate for (defaults to today)
        custom_salt: Optional extra salt so parents can set a unique safe code

    Returns:
        List of MathProblem objects with questions and answers
    """
    num_problems = max(1, min(10, num_problems))
    day = day or date.today()
    salt = f"math-safe-{custom_salt}" if custom_salt else "math-safe-2024"
    seed = _daily_seed(day, salt)
    rng = random.Random(seed)

    problems = []
    for i in range(num_problems):
        problems.append(_make_problem(rng, difficulty, i))
    return problems
