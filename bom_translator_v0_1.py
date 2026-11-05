"""BOM translator v0.1

Reads a top-level BOM (as exported from a SolidWorks BOM table to CSV) and
translates each line into a module code from the module vocabulary.

Matching rule: a line matches an alias when every word of the alias appears
in the line's description. The longest alias wins, so "explosion proof
control panel" maps to the XP panel, not the standard one. If two different
modules tie, the line is flagged as ambiguous. Nothing is ever guessed.

Usage:
    python bom_translator_v0_1.py bom_synthetic_example_v0_1.csv
"""
import csv
import json
import re
import sys
from collections import OrderedDict

REQUIRED_COLUMNS = ("ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY.")


def words(text: str) -> frozenset:
    """Lowercase words. Punctuation becomes a space, except '&' (as in S&T)."""
    return frozenset(re.sub(r"[^a-z0-9&]+", " ", (text or "").lower()).split())


def build_alias_index(vocab):
    """List of (alias words, module code), plus each code's own words."""
    index = []
    for m in vocab["modules"]:
        for alias in m["aliases"]:
            index.append((words(alias), m["code"]))
    return index


def translate_line(description, alias_index):
    """Return ('matched', code), ('ambiguous', [codes]) or ('unmapped', None)."""
    line = words(description)
    best_per_code = {}
    for alias_words, code in alias_index:
        if alias_words and alias_words <= line:  # every alias word is in the line
            best_per_code[code] = max(best_per_code.get(code, 0), len(alias_words))
    if not best_per_code:
        return "unmapped", None
    top = max(best_per_code.values())
    winners = sorted(c for c, n in best_per_code.items() if n == top)
    if len(winners) > 1:
        return "ambiguous", winners
    return "matched", winners[0]


def read_bom(path):
    # utf-8-sig drops the invisible marker Excel and SolidWorks often add.
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns {missing}. Found {reader.fieldnames}")
        rows = []
        for n, row in enumerate(reader, start=2):
            try:
                qty = int(row["QTY."])
            except ValueError:
                raise ValueError(f"{path} line {n}: quantity '{row['QTY.']}' is not a whole number")
            if qty < 1:
                raise ValueError(f"{path} line {n}: quantity must be at least 1")
            rows.append({**row, "QTY.": qty})
        return rows


def translate_bom(rows, vocab):
    """Return modules found (code -> total qty), plus lines needing a human."""
    index = build_alias_index(vocab)
    modules = OrderedDict()
    unmapped, ambiguous = [], []
    for row in rows:
        status, result = translate_line(row["DESCRIPTION"], index)
        if status == "matched":
            modules[result] = modules.get(result, 0) + row["QTY."]
        elif status == "ambiguous":
            ambiguous.append({**row, "candidates": result})
        else:
            unmapped.append(row)
    return {"modules": modules, "unmapped": unmapped, "ambiguous": ambiguous}


def draft_card_modules(modules):
    """Modules block for a job card. new_design can't be read from a BOM,
    so it is left as None for a person to fill in."""
    return [{"code": c, "qty": q, "new_design": None} for c, q in modules.items()]


def main(bom_path, vocab_path="module_vocabulary_v0.1.json"):
    vocab = json.load(open(vocab_path, encoding="utf-8"))
    rows = read_bom(bom_path)
    result = translate_bom(rows, vocab)

    print(f"BOM: {bom_path}  ({len(rows)} lines)\n")
    print("Translated to modules:")
    for code, qty in result["modules"].items():
        print(f"  {code:<16} x{qty}")
    if result["ambiguous"]:
        print("\nAmbiguous (matches more than one module, needs a person):")
        for r in result["ambiguous"]:
            print(f"  line {r['ITEM NO.']}: '{r['DESCRIPTION']}' -> {' or '.join(r['candidates'])}")
    if result["unmapped"]:
        print("\nNot recognized (hardware, or a missing alias):")
        for r in result["unmapped"]:
            print(f"  line {r['ITEM NO.']}: '{r['DESCRIPTION']}' ({r['PART NUMBER']})")
    print("\nDraft job card modules (new_design to be filled in by a person):")
    print(json.dumps(draft_card_modules(result["modules"]), indent=2))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
