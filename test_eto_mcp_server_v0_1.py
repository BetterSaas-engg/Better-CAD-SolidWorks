"""Tests for eto_mcp_server_v0_1. Run: python test_eto_mcp_server_v0_1.py

The last test starts the server for real and talks to it over MCP, the same
way Claude Code does.
"""
import asyncio
import json
import sys
from pathlib import Path

from eto_mcp_server_v0_1 import find_similar_jobs, get_job_card, list_modules

COATINGS = dict(
    industry="coatings", solvents=["toluene", "xylene"], mode="batch",
    throughput_value=350, throughput_unit="litres_per_batch",
    hazardous_area="class1_div1", contaminants="resins, heavy sludge",
    target_purity_pct=97,
)


def test_coatings_enquiry_ranks_and_picks_reference():
    result = find_similar_jobs(**COATINGS)
    assert result["matches"][0]["job_id"] == "SYN-2022-114"
    assert result["price_reference"]["job_id"] == "SYN-2023-207"
    assert result["data_is_synthetic"] is True


def test_inflated_job_shows_reused_designs():
    top = find_similar_jobs(**COATINGS)["matches"][0]
    assert "SYN-2023-207" in top["designs_since_reused_on"]["SLUDGE-PUMP"]


def test_bad_input_fails_loudly():
    try:
        find_similar_jobs(**{**COATINGS, "throughput_value": 0})
    except ValueError:
        return
    raise AssertionError("zero throughput was accepted")


def test_unknown_job_fails_loudly():
    try:
        get_job_card("SYN-9999-000")
    except ValueError:
        return
    raise AssertionError("unknown job id was accepted")


def test_vocabulary_is_exposed():
    codes = {m["code"] for m in list_modules()}
    assert {"STILL-400", "SLUDGE-PUMP", "XP-PURGE"} <= codes


def test_server_speaks_mcp():
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    server_file = Path(__file__).resolve().parent / "eto_mcp_server_v0_1.py"
    params = StdioServerParameters(command=sys.executable, args=[str(server_file)])

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {t.name for t in (await session.list_tools()).tools}
                assert tools == {"find_similar_jobs", "get_job_card", "list_modules"}, tools
                result = await session.call_tool("find_similar_jobs", COATINGS)
                assert not result.is_error, result
                text = "".join(c.text for c in result.content if getattr(c, "text", None))
                assert json.loads(text)["price_reference"]["job_id"] == "SYN-2023-207"

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
