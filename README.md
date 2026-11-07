# Better CAD: SolidWorks job memory

Small engineered-to-order (ETO) manufacturers have years of knowledge locked in SolidWorks files, ERP records and old quotes. When a new enquiry comes in, someone senior has to remember "we built something like this before", dig it out by hand, and work out the price.

This project is a translation layer between that engineering data and AI. It turns each past job into a structured **job card** (what the customer needed, what was built, what was quoted, what it actually cost) so a matcher can find similar past jobs, and Claude can explain the result in plain English.

```
Messy BOM  →  BOM translator  →  Job cards  →  Matcher  →  Price reference  →  Claude explains
                   v0.1             v0.1          v0.2          v0.2           MCP server v0.2
```

> **All data in this repo is synthetic.** Customers, jobs, specs and costs are invented for testing. No real company's data is stored here. Real data goes in `real_data/`, which is git-ignored.

## What's here

| File | What it is |
|---|---|
| `eto_job_card_schema_v0.1.json` | JSON Schema for a job card |
| `eto_job_cards_synthetic_v0.1.json` | Five synthetic job cards |
| `module_vocabulary_v0.1.json` | Equipment module codes, families, descriptions and the messy names (aliases) they appear as in BOMs |
| `bom_translator_v0_1.py` | Turns a messy BOM export into module codes; flags anything ambiguous or unknown instead of guessing |
| `bom_synthetic_example_v0_1.csv` | A deliberately messy synthetic BOM |
| `job_matcher_v0_2.py` | Ranks past jobs against an enquiry and picks the best price reference |
| `enquiry_example_v0_1.json` | An example new enquiry |
| `eto_mcp_server_v0_2.py` | MCP server that lets Claude query the job memory |
| `test_*.py` | Tests for each piece (28 in total) |

## Run it

Python 3.10+. The scripts have no dependencies; the MCP server needs the `mcp` package.

```
python job_matcher_v0_2.py enquiry_example_v0_1.json eto_job_cards_synthetic_v0.1.json
python bom_translator_v0_1.py bom_synthetic_example_v0_1.csv
```

Run the tests:

```
python test_job_matcher_v0_2.py
python test_module_vocabulary_v0_1.py
python test_bom_translator_v0_1.py
python test_eto_mcp_server_v0_2.py
```

## Ask Claude

Install the MCP library and register the server with Claude Code, from this folder:

```
python -m pip install "mcp>=2.3,<3"
claude mcp add eto-jobs -- python "<full path to>/eto_mcp_server_v0_2.py"
```

Then start `claude` in this folder and ask, for example:

> We've got an enquiry from a coatings plant: toluene and xylene waste with resins and heavy sludge, about 350 litres per batch, Class I Div 1 area, they want 97% purity. Have we built anything like this before, and which past job should we price from?

Claude Code starts the server itself. The server gives Claude three read-only tools: `find_similar_jobs`, `get_job_card` and `list_modules`.

## How it works

- **Similarity** is scored on requirements: solvents, batch or continuous, throughput, hazardous area, industry, contaminants and purity. Every factor is returned with its weight, score and a verdict (match, partial or differs).
- **Price reference** is a separate decision. The most similar job isn't always the best guide to cost: if it included first-time design work that later jobs reused, its engineering cost is inflated for today. The matcher flags that and points to a better reference, or says there isn't one.
- **BOM translation** matches each line against the vocabulary's aliases. The longest alias wins; ties are flagged as ambiguous. Whether a module was a new design can't be read from a BOM, so a person fills that in.
- **No AI in the ranking.** Scores, costs and percentages are all computed in code. Claude is instructed to quote only tool results, never to convert currencies or add up costs, and to say the data is synthetic.

**Known limit:** the guardrails stop wrong numbers, not wrong reasoning about them. Claude can still draw a conclusion the data doesn't support, so a person approves anything that becomes a quote.

## Status

Working end to end on synthetic data. Next: real job data, building full job cards from quotes, ERP and accounting records, and handling mixed currencies.
