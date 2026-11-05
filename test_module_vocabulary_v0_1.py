"""Checks the module vocabulary and that job cards only use known module codes.

Run: python test_module_vocabulary_v0_1.py
"""
import json

VOCAB = json.load(open("module_vocabulary_v0.1.json", encoding="utf-8"))
CARDS = json.load(open("eto_job_cards_synthetic_v0.1.json", encoding="utf-8"))
MODULES = VOCAB["modules"]


def test_codes_are_unique():
    codes = [m["code"] for m in MODULES]
    assert len(codes) == len(set(codes)), "duplicate module codes"


def test_every_module_has_required_fields():
    for m in MODULES:
        for field in ("code", "family", "category", "name", "description", "aliases"):
            assert m.get(field), f"{m.get('code')} is missing {field}"


def test_categories_are_defined():
    for m in MODULES:
        assert m["category"] in VOCAB["categories"], f"{m['code']}: unknown category {m['category']}"


def test_no_alias_points_to_two_modules():
    # If one alias maps to two codes, a messy BOM line can't be translated reliably.
    seen = {}
    for m in MODULES:
        for alias in m["aliases"]:
            key = alias.lower()
            assert key not in seen, f"alias '{alias}' used by {seen[key]} and {m['code']}"
            seen[key] = m["code"]


def test_job_cards_use_only_known_codes():
    known = {m["code"] for m in MODULES}
    for card in CARDS:
        for mod in card["solution"]["modules"]:
            assert mod["code"] in known, f"{card['job_id']} uses unknown module {mod['code']}"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
