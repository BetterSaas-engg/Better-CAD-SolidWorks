"""ETO job memory: MCP server v0.2

Lets Claude (Claude Code, Claude Desktop) ask the job matcher questions in
plain English. Claude calls these tools for the facts and explains them.
The tools do every calculation; Claude never invents or computes numbers.

v0.2: every similarity factor is returned with its score and a verdict
(match, partial or differs), so Claude has no gaps to fill in.

Run by Claude, not by hand. Register it once with Claude Code:
    claude mcp add eto-jobs -- python <full path to this file>
"""
import json
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from job_matcher_v0_2 import WEIGHTS, cost_summary, design_reuse, price_reference, rank

# Data files sit next to this script. Resolve from here, not the current
# folder, because Claude may start the server from anywhere.
HERE = Path(__file__).resolve().parent
CARDS = json.loads((HERE / "eto_job_cards_synthetic_v0.1.json").read_text(encoding="utf-8"))
VOCAB = json.loads((HERE / "module_vocabulary_v0.1.json").read_text(encoding="utf-8"))
REUSE = design_reuse(CARDS)
CARDS_BY_ID = {c["job_id"]: c for c in CARDS}

Industry = Literal["printing", "coatings", "automotive", "aerospace", "battery",
                   "semiconductor", "pharma", "cannabis_hemp", "chemicals", "other"]
Hazard = Literal["none", "class1_div2", "class1_div1", "atex_zone2", "atex_zone1"]
ThroughputUnit = Literal["litres_per_batch", "litres_per_hour", "litres_per_day"]

# Verdict thresholds. The same cut-offs the matcher's command-line output uses.
MATCH_AT = 0.8
DIFFERS_BELOW = 0.5

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

server = MCPServer(
    name="eto-jobs",
    instructions=(
        "Memory of past engineered-to-order solvent recovery jobs. "
        "Use find_similar_jobs when someone describes a new enquiry. "
        "Every number you report must come from a tool result: never estimate, "
        "round into new figures, convert currencies or add up costs yourself. "
        "Amounts can be in different currencies; say which. "
        "Report each factor's verdict exactly as returned: a partial match is "
        "neither a match nor a difference. "
        "The current data is synthetic test data: always tell the user so."
    ),
)


def factor_report(parts):
    """Every factor with its weight, score and verdict. Nothing left implicit."""
    def verdict(v):
        if v >= MATCH_AT:
            return "match"
        return "differs" if v < DIFFERS_BELOW else "partial"
    return {
        name: {"weight_pct": round(WEIGHTS[name] * 100), "score_pct": round(v * 100), "verdict": verdict(v)}
        for name, v in parts.items()
    }


@server.tool(annotations=READ_ONLY)
def find_similar_jobs(
    industry: Industry,
    solvents: list[str],
    mode: Literal["batch", "continuous"],
    throughput_value: float,
    throughput_unit: ThroughputUnit,
    hazardous_area: Hazard,
    contaminants: str = "",
    target_purity_pct: float | None = None,
    top: int = 3,
) -> dict:
    """Find past jobs most similar to a new enquiry, and the best one to price from.

    Returns ranked matches (every factor with its score and verdict, quoted price and actual cost,
    first-time designs, lessons) and a price reference. The most similar job
    is not always the best price reference: if its new designs were reused on
    later jobs, its engineering cost is too high for today.
    """
    if throughput_value <= 0:
        raise ValueError("throughput_value must be greater than 0")
    if not solvents:
        raise ValueError("give at least one solvent")
    enquiry = {
        "industry": industry,
        "requirements": {
            "solvents": [{"name": s} for s in solvents],
            "contaminants": contaminants,
            "mode": mode,
            "throughput": {"value": throughput_value, "unit": throughput_unit},
            "target_purity_pct": target_purity_pct,
            "hazardous_area": hazardous_area,
        },
    }
    ranked = rank(enquiry, CARDS, top=max(1, min(top, len(CARDS))))
    matches = []
    for (total, parts), card in ranked:
        matches.append({
            "job_id": card["job_id"],
            "customer": card["customer"]["name"],
            "industry": card["customer"]["industry"],
            "status": card["status"],
            "match_pct": round(total * 100),
            "factors": factor_report(parts),
            "cost": cost_summary(card),
            "new_designs_on_this_job": [m["code"] for m in card["solution"]["modules"] if m["new_design"]],
            "designs_since_reused_on": REUSE.get(card["job_id"], {}),
            "lesson": card.get("lessons", ""),
        })
    ref = price_reference(ranked, REUSE)
    return {
        "data_is_synthetic": all(c.get("synthetic") for c in CARDS),
        "matches": matches,
        "price_reference": (
            {"job_id": ref["job_id"], "customer": ref["customer"]["name"], "cost": cost_summary(ref)}
            if ref else None
        ),
        "price_reference_note": (
            "Strong match with actual costs and no inflated first-time design work."
            if ref else "No past job is close enough. Treat this as a new design."
        ),
    }


@server.tool(annotations=READ_ONLY)
def get_job_card(job_id: str) -> dict:
    """Full job card for one past job: requirements, modules built, quote, costs, lessons."""
    if job_id not in CARDS_BY_ID:
        raise ValueError(f"No job {job_id}. Known jobs: {', '.join(sorted(CARDS_BY_ID))}")
    return CARDS_BY_ID[job_id]


@server.tool(annotations=READ_ONLY)
def list_modules() -> list[dict]:
    """The module vocabulary: every equipment module code with a plain-English description."""
    return [
        {k: m[k] for k in ("code", "family", "category", "name", "description")}
        for m in VOCAB["modules"]
    ]


if __name__ == "__main__":
    server.run()  # stdio: Claude talks to it over standard input/output
