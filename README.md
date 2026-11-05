# Better CAD: SolidWorks job memory

Small engineered-to-order (ETO) manufacturers have years of knowledge locked in SolidWorks files, ERP records and old quotes. When a new enquiry comes in, someone senior has to remember "we built something like this before", dig it out by hand, and work out the price.

This project is a translation layer between that engineering data and AI. It turns each past job into a structured **job card** (what the customer needed, what was built, what was quoted, what it actually cost) so a matcher, and later an LLM, can reason over it.

```
Engineering files + job records  →  Job cards  →  Matcher  →  LLM explains
     (extractor: not built yet)       v0.1          v0.2       (not built yet)
```

> **All data in this repo is synthetic.** Customers, jobs, specs and costs are invented for testing. No real company's data is stored here. Real data goes in `real_data/`, which is git-ignored.

## What's here

| File | What it is |
|---|---|
| `eto_job_card_schema_v0.1.json` | JSON Schema for a job card |
| `eto_job_cards_synthetic_v0.1.json` | Five synthetic job cards that exercise the schema |
| `enquiry_example_v0_1.json` | An example new enquiry |
| `job_matcher_v0_2.py` | Ranks past jobs against an enquiry and picks the best price reference |
| `test_job_matcher_v0_2.py` | Tests |

## Run it

Python 3.10+, no dependencies.

```
python test_job_matcher_v0_2.py
python job_matcher_v0_2.py enquiry_example_v0_1.json eto_job_cards_synthetic_v0.1.json
```

## How matching works

- **Similarity** is scored on requirements only: solvents, batch or continuous, throughput, hazardous area, industry, contaminants and purity. Each factor is weighted and the output shows why a job matched.
- **Price reference** is a separate decision. The most similar job isn't always the best guide to cost: if it included first-time design work that later jobs reused, its engineering cost is inflated for today. The matcher flags that and points to a better reference, or says there isn't one.
- **No AI in the ranking.** Every score is deterministic and explainable. Amounts come from the job cards, never calculated by a model.

## Status

Early prototype on synthetic data. Next: a module vocabulary, currency handling, and an extractor for real SolidWorks BOM exports.
