"""Tests for bom_translator_v0_1. Run: python test_bom_translator_v0_1.py"""
import json
from bom_translator_v0_1 import build_alias_index, read_bom, translate_bom, translate_line

VOCAB = json.load(open("module_vocabulary_v0.1.json", encoding="utf-8"))
INDEX = build_alias_index(VOCAB)
RESULT = translate_bom(read_bom("bom_synthetic_example_v0_1.csv"), VOCAB)


def test_messy_abbreviation_is_recognized():
    assert translate_line("Cond. assy S&T 4in", INDEX) == ("matched", "COND-SHELL")


def test_size_picks_the_right_still():
    assert translate_line("Still, 400L, 316SS", INDEX) == ("matched", "STILL-400")


def test_longest_alias_wins():
    # "control panel" alone would mean the standard panel; the fuller match wins.
    assert translate_line("Explosion proof control panel", INDEX) == ("matched", "PLC-PANEL-XP")


def test_tie_is_flagged_not_guessed():
    status, candidates = translate_line("Vacuum pump / sludge pump skid", INDEX)
    assert status == "ambiguous" and candidates == ["SLUDGE-PUMP", "VAC-LR"], candidates


def test_hardware_is_left_unmapped():
    unmapped = {r["DESCRIPTION"] for r in RESULT["unmapped"]}
    assert unmapped == {"Nameplate SS", "Bolt kit, M12"}, unmapped


def test_quantities_add_up_across_lines():
    # Main condenser and vent condenser are both COND-SHELL.
    assert RESULT["modules"]["COND-SHELL"] == 2


def test_every_line_is_accounted_for():
    # 10 lines = 7 mapped + 1 ambiguous + 2 unmapped. The 7 mapped lines
    # collapse into 6 modules because two lines are both COND-SHELL.
    assert len(RESULT["ambiguous"]) == 1
    assert len(RESULT["unmapped"]) == 2
    assert len(RESULT["modules"]) == 6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
