from .quiz import load_questions, RATING_SCORES


def calculate_scores(responses: list[dict]) -> dict:
    """
    Calculate weighted domain scores and overall placement.

    Each response dict: {question_id, domain, rating, override_rating, difficulty, ...}
    """
    questions = load_questions()
    q_map = {q["id"]: q for q in questions}

    # Aggregate scores per domain
    domain_totals = {}  # {domain: {earned, possible, weight}}
    for resp in responses:
        qid = resp.get("question_id", "")
        q = q_map.get(qid)
        if not q:
            continue

        domain = q["domain"]
        difficulty = q["difficulty"]

        # Use override rating if Claude adjusted it, otherwise self-rating
        rating = resp.get("override_rating") or resp.get("rating", "D")
        score = RATING_SCORES.get(rating, 0.0)

        # Weight by difficulty (1-3 scale)
        weighted_score = score * difficulty
        max_score = 1.0 * difficulty

        if domain not in domain_totals:
            domain_totals[domain] = {"earned": 0, "possible": 0, "weight": q["domain_weight"]}
        domain_totals[domain]["earned"] += weighted_score
        domain_totals[domain]["possible"] += max_score

    # Calculate domain percentages
    domain_scores = {}
    for domain, totals in domain_totals.items():
        if totals["possible"] > 0:
            domain_scores[domain] = round(totals["earned"] / totals["possible"] * 100, 1)
        else:
            domain_scores[domain] = 0.0

    # Weighted overall score
    overall = 0.0
    total_weight = 0.0
    for domain, pct in domain_scores.items():
        w = domain_totals[domain]["weight"]
        overall += pct * w
        total_weight += w
    if total_weight > 0:
        overall = round(overall / total_weight, 1)

    # Level placement
    level = determine_level(overall)

    # Strengths and gaps (sorted by score)
    sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
    strengths = [d[0] for d in sorted_domains[:3]]
    gaps = [d[0] for d in sorted_domains[-3:]]

    return {
        "domain_scores": domain_scores,
        "overall_score": overall,
        "level": level,
        "strengths": strengths,
        "gaps": gaps,
    }


def determine_level(score: float) -> str:
    """Map overall weighted score to level placement."""
    if score >= 85:
        return "Innovator"
    elif score >= 65:
        return "Builder"
    elif score >= 40:
        return "Practitioner"
    else:
        return "Foundations"


def get_level_description(level: str) -> str:
    descriptions = {
        "Foundations": "Building core understanding. Focus on fundamentals before advancing to applied topics.",
        "Practitioner": "Solid working knowledge. Ready to deepen in specific areas and build more complex systems.",
        "Builder": "Strong applied skills. Focus on architecture decisions, evaluation, and production patterns.",
        "Innovator": "Deep expertise. Push into frontier research, novel architectures, and thought leadership.",
    }
    return descriptions.get(level, "")
