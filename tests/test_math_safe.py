"""Tests for the Math Puzzle Safe."""

from datetime import date

from services.math_safe.puzzle_generator import generate_daily_problems


class TestPuzzleGenerator:
    def test_generates_correct_count(self):
        problems = generate_daily_problems(num_problems=5, day=date(2024, 6, 15))
        assert len(problems) == 5

    def test_max_10_problems(self):
        problems = generate_daily_problems(num_problems=15, day=date(2024, 6, 15))
        assert len(problems) == 10

    def test_min_1_problem(self):
        problems = generate_daily_problems(num_problems=0, day=date(2024, 6, 15))
        assert len(problems) == 1

    def test_deterministic_for_same_day(self):
        day = date(2024, 6, 15)
        a = generate_daily_problems(num_problems=5, day=day)
        b = generate_daily_problems(num_problems=5, day=day)
        assert [p.answer for p in a] == [p.answer for p in b]
        assert [p.question for p in a] == [p.question for p in b]

    def test_different_days_give_different_problems(self):
        a = generate_daily_problems(num_problems=5, day=date(2024, 6, 15))
        b = generate_daily_problems(num_problems=5, day=date(2024, 6, 16))
        # Extremely unlikely to be identical
        assert [p.answer for p in a] != [p.answer for p in b]

    def test_custom_salt_changes_problems(self):
        day = date(2024, 6, 15)
        a = generate_daily_problems(num_problems=5, day=day, custom_salt="family1")
        b = generate_daily_problems(num_problems=5, day=day, custom_salt="family2")
        assert [p.answer for p in a] != [p.answer for p in b]

    def test_easy_answers_are_nonnegative(self):
        for d in range(1, 31):
            problems = generate_daily_problems(
                num_problems=10, difficulty="easy", day=date(2024, 6, d)
            )
            for p in problems:
                assert p.answer >= 0, f"Negative answer {p.answer} for '{p.question}'"

    def test_all_difficulties(self):
        day = date(2024, 6, 15)
        for diff in ["easy", "medium", "hard"]:
            problems = generate_daily_problems(num_problems=5, difficulty=diff, day=day)
            assert len(problems) == 5
            for p in problems:
                assert p.difficulty == diff

    def test_answers_are_integers(self):
        day = date(2024, 6, 15)
        for diff in ["easy", "medium", "hard"]:
            problems = generate_daily_problems(num_problems=10, difficulty=diff, day=day)
            for p in problems:
                assert isinstance(p.answer, int)

    def test_ids_are_sequential(self):
        problems = generate_daily_problems(num_problems=7, day=date(2024, 6, 15))
        assert [p.id for p in problems] == list(range(7))
