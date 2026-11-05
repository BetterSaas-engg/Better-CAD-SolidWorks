"""Tests for job_matcher_v0_2. Run: python test_job_matcher_v0_2.py"""
import json
from job_matcher_v0_2 import rank, score_job, design_reuse, price_reference

CARDS = json.load(open("eto_job_cards_synthetic_v0.1.json", encoding="utf-8"))
ENQUIRY = json.load(open("enquiry_example_v0_1.json", encoding="utf-8"))


# --- similarity (unchanged from v0.1) ---

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


# --- v0.2: design reuse and price reference ---

def test_sludge_pump_designed_on_114_is_reused_on_207():
    reuse = design_reuse(CARDS)
    assert "SYN-2023-207" in reuse["SYN-2022-114"]["SLUDGE-PUMP"], reuse["SYN-2022-114"]


def test_designs_never_reused_are_not_flagged():
    # The battery job's new designs appear on no later job.
    assert design_reuse(CARDS)["SYN-2024-052"] == {}


def test_price_reference_skips_inflated_job():
    ranked = rank(ENQUIRY, CARDS)
    ref = price_reference(ranked, design_reuse(CARDS))
    assert ranked[0][1]["job_id"] == "SYN-2022-114"  # most similar...
    assert ref["job_id"] == "SYN-2023-207"            # ...but not the best price guide


def test_no_reference_when_nothing_is_close():
    far = {
        "summary": "Semiconductor fab, IPA, continuous",
        "industry": "semiconductor",
        "requirements": {
            "solvents": [{"name": "IPA"}],
            "mode": "continuous",
            "throughput": {"value": 50, "unit": "litres_per_hour"},
            "target_purity_pct": 99.99,
            "hazardous_area": "none",
        },
    }
    assert price_reference(rank(far, CARDS), design_reuse(CARDS)) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
