"""Tests for job_matcher_v0_1. Run: python test_job_matcher_v0_1.py"""
import json
from job_matcher_v0_1 import rank, score_job

CARDS = json.load(open("eto_job_cards_synthetic_v0.1.json", encoding="utf-8"))
ENQUIRY = json.load(open("enquiry_example_v0_1.json", encoding="utf-8"))


def test_coatings_twins_rank_top_two():
    top_ids = {c["job_id"] for _, c in rank(ENQUIRY, CARDS, top=2)}
    assert top_ids == {"SYN-2022-114", "SYN-2023-207"}, top_ids


def test_battery_job_ranks_last():
    ranked = rank(ENQUIRY, CARDS, top=len(CARDS))
    assert ranked[-1][1]["job_id"] == "SYN-2024-052"


def test_identical_requirements_score_one():
    card = CARDS[0]
    enquiry = {"industry": card["customer"]["industry"], "requirements": card["requirements"]}
    total, _ = score_job(enquiry, card)
    assert abs(total - 1.0) < 1e-9, total


def test_refuses_mixed_synthetic_and_real():
    real = dict(CARDS[0], synthetic=False)
    try:
        rank(ENQUIRY, CARDS + [real])
    except ValueError:
        return
    raise AssertionError("mixed synthetic and real cards were accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
