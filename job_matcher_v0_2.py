"""ETO job matcher v0.2

Given a new enquiry (customer requirements), rank past job cards by how
similar their requirements are, and show what those jobs actually cost.

v0.2 adds the price reference: the most similar job is not always the best
guide to cost. If a job included first-time design work that later jobs
reused, its engineering cost is inflated for today's purposes. The matcher
flags that and picks a better reference.

Deterministic on purpose: every score is explainable. An LLM can explain
the result later; it does not decide the ranking.

Usage:
    python job_matcher_v0_2.py enquiry_example_v0_1.json eto_job_cards_synthetic_v0.1.json
"""
import json
import re
import sys

# How much each requirement counts towards the total score (sums to 1.0).
WEIGHTS = {
    "solvents": 0.25,
    "mode": 0.15,
    "throughput": 0.15,
    "hazardous_area": 0.15,
    "industry": 0.10,
    "contaminants": 0.10,
    "purity": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "weights must sum to 1"

# Hazardous-area ratings ordered by severity, so near ratings score partially.
# A past job must match at least this well to be used as a price reference.
MIN_REFERENCE_SCORE = 0.6

HAZARD_LEVEL = {"none": 0, "class1_div2": 1, "atex_zone2": 1, "class1_div1": 2, "atex_zone1": 2}


def _jaccard(a: set, b: set) -> float:
    """Overlap of two sets, 0 (nothing shared) to 1 (identical)."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _words(text: str) -> set:
    return set(re.findall(r"[a-z]+", (text or "").lower()))


def score_solvents(new, old):
    a = {s["name"].lower() for s in new["solvents"]}
    b = {s["name"].lower() for s in old["solvents"]}
    return _jaccard(a, b)


def score_mode(new, old):
    return 1.0 if new["mode"] == old["mode"] else 0.0


def score_throughput(new, old):
    # Different units (per batch vs per hour) are different kinds of machine.
    if new["throughput"]["unit"] != old["throughput"]["unit"]:
        return 0.0
    x, y = new["throughput"]["value"], old["throughput"]["value"]
    return min(x, y) / max(x, y)


def score_hazard(new, old):
    gap = abs(HAZARD_LEVEL[new["hazardous_area"]] - HAZARD_LEVEL[old["hazardous_area"]])
    return 1.0 - gap / 2


def score_contaminants(new, old):
    return _jaccard(_words(new.get("contaminants")), _words(old.get("contaminants")))


def score_purity(new, old):
    p, q = new.get("target_purity_pct"), old.get("target_purity_pct")
    if p is None or q is None:
        return 0.5  # unknown: neither reward nor punish fully
    return max(0.0, 1.0 - abs(p - q) / 5)  # 5 points apart or more scores 0


def score_job(enquiry, card):
    """Return (total score 0-1, per-factor breakdown)."""
    new, old = enquiry["requirements"], card["requirements"]
    parts = {
        "solvents": score_solvents(new, old),
        "mode": score_mode(new, old),
        "throughput": score_throughput(new, old),
        "hazardous_area": score_hazard(new, old),
        "industry": 1.0 if enquiry["industry"] == card["customer"]["industry"] else 0.0,
        "contaminants": score_contaminants(new, old),
        "purity": score_purity(new, old),
    }
    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    return total, parts


def cost_summary(card):
    """Quoted vs actual, straight from the card. No calculation beyond a ratio."""
    c = card["commercials"]
    est, act = c.get("estimated_cost"), c.get("actual_cost")
    if not act:
        return f"{c['currency']} {c['quoted_price']:,} quoted, no actual cost ({card['status']})"
    overrun = (act["total"] - est["total"]) / est["total"] * 100 if est else None
    line = f"{c['currency']} {c['quoted_price']:,} quoted, actual cost {act['total']:,}"
    if overrun is not None:
        line += f" ({overrun:+.0f}% vs estimate)"
    if est and "engineering" in est and "engineering" in act:
        eng = (act["engineering"] - est["engineering"]) / est["engineering"] * 100
        line += f", engineering {eng:+.0f}%"
    return line


def rank(enquiry, cards, top=3):
    if any(c.get("synthetic") for c in cards) and not all(c.get("synthetic") for c in cards):
        raise ValueError("Never mix synthetic and real job cards in one match.")
    scored = [(score_job(enquiry, c), c) for c in cards]
    scored.sort(key=lambda x: x[0][0], reverse=True)
    return scored[:top]


def design_reuse(cards):
    """For each job, which of its first-time designs were reused on later jobs.

    Returns {job_id: {module_code: [later job_ids]}}. Jobs without a quote date
    are skipped, because "later" can't be decided for them.
    """
    dated = [c for c in cards if c["commercials"].get("quote_date")]
    reuse = {}
    for job in dated:
        job_date = job["commercials"]["quote_date"]
        new_codes = {m["code"] for m in job["solution"]["modules"] if m["new_design"]}
        found = {}
        for code in sorted(new_codes):
            later = [
                c["job_id"] for c in dated
                if c["commercials"]["quote_date"] > job_date
                and any(m["code"] == code and not m["new_design"] for m in c["solution"]["modules"])
            ]
            if later:
                found[code] = later
        reuse[job["job_id"]] = found
    return reuse


def price_reference(ranked, reuse):
    """Best job to price from: a strong match, with an actual cost, whose
    engineering wasn't inflated by designs that now already exist.
    Returns the card, or None if no match is strong enough."""
    for (total, _), card in ranked:
        if total < MIN_REFERENCE_SCORE or not card["commercials"].get("actual_cost"):
            continue
        if not reuse.get(card["job_id"]):
            return card
    return None


def main(enquiry_path, cards_path):
    enquiry = json.load(open(enquiry_path, encoding="utf-8"))
    cards = json.load(open(cards_path, encoding="utf-8"))
    print(f"Enquiry: {enquiry['summary']}\n")
    ranked = rank(enquiry, cards)
    reuse = design_reuse(cards)
    for i, ((total, parts), card) in enumerate(ranked, 1):
        print(f"{i}. {card['job_id']}  {card['customer']['name']}  match {total:.0%}")
        strong = [k for k, v in parts.items() if v >= 0.8]
        weak = [k for k, v in parts.items() if v < 0.5]
        print(f"   Matches on: {', '.join(strong) or '-'}   Differs on: {', '.join(weak) or '-'}")
        print(f"   Cost: {cost_summary(card)}")
        new_mods = [m["code"] for m in card["solution"]["modules"] if m["new_design"]]
        if new_mods:
            print(f"   New design on that job: {', '.join(new_mods)}")
        for code, later in reuse.get(card["job_id"], {}).items():
            print(f"   ! {code} has since been reused on {', '.join(later)}: this job's engineering cost is high for today")
        print(f"   Lesson: {card.get('lessons', '-')}\n")

    ref = price_reference(ranked, reuse)
    if ref:
        print(f"Best price reference: {ref['job_id']} ({ref['customer']['name']}), {cost_summary(ref)}")
    else:
        print("Best price reference: none. No past job is close enough; treat this as a new design.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
