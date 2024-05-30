# Raw benchmark results

This is supplementary data related to
[aider's SWE Bench Lite results](https://aider.chat/2024/05/22/swe-bench-lite.html).

This directory contains the raw benchmark results produced by
the `harness.py` and `report.py` scripts.
The
[tables comparing GPT-4o and Opus](https://aider.chat/2024/05/22/swe-bench-lite.html#aider-with-gpt-4o--opus)
were produced from this data like this:

```
$ python table.py predictions/multi-models--gpt-4o--openrouter-anthropic-claude-3-opus

| 1 | Aider with GPT-4o    | 208 | 69.3% | 61 | 77.2% | 20.3% |
| 2 | Aider with Opus      |  49 | 16.3% | 10 | 12.7% |  3.3% |
| 3 | Aider with GPT-4o    |  20 |  6.7% |  3 |  3.8% |  1.0% |
| 4 | Aider with Opus      |   9 |  3.0% |  2 |  2.5% |  0.7% |
| 5 | Aider with GPT-4o    |  11 |  3.7% |  2 |  2.5% |  0.7% |
| 6 | Aider with Opus      |   3 |  1.0% |  1 |  1.3% |  0.3% |
| **Total** | | **300** | **100%** | **79** | **100%** | **26.3%** |

| Aider with GPT-4o    | 239 | 66 |27.6% |
| Aider with Opus      |  61 | 13 |21.3% |
| **Total** | **300** | **79** |**26.3%** |
```

Note that in the article, the headers of the tables refer to
"plausible solutions" in an imprecise way.
It might be better to think of them as "proposed solutions",
because if no plausible solution was found then the least-bad/most-plausible
solution was used.

## Markdown and JSON files

Each of the 300 problems has data in 2 files:

- a markdown file with chat transcripts of aider working on solutions.
- a json file with data about 1-6 candidate solutions which were found for the problem.

The json file for each problem is a dict with the following fields.
These first 3 fields are the same as fields used in the standard `all_preds.jsonl`
file used by SWE Bench, and represent the solution found by aider to the problem.

- instance_id
- model_name_or_path
- model_patch

The remaining fields contain extra data that is useful for computing statistics
about the benchmark run:

- model - Which LLM was used to generate the `model_patch`.
- cost - Cost of the tokens used by aider to generate this solution.
- added_files - Which files did aider select to be added to the chat.
- gold_files - Which files were present in the "gold patch" (useful to compute stats about whether aider added the gold files or not).
- edited_files - Which files did aider edit.
- edit_outcome - Did aider report that it edited files without outstanding edit errors? True/False or None if no edits were attempted.
- lint_outcome - Did aider report that linting ended up clean without outstanding errors? True/False or None if no linting was performed.
- test_outcome - Did aider report that the pre-existing tests in the repo all passed? True/False or None if testing not performed.
- try - Attempt number (1..3) when this solution was generated. Attempts were made like this:
  - try=1 model=gpt-4o
  - try=1 model=openrouter/anthropic/claude-3-opus
  - try=2 model=gpt-4o
  - try=2 model=openrouter/anthropic/claude-3-opus
  - try=3 model=gpt-4o
  - try=3 model=openrouter/anthropic/claude-3-opus
- resolved - Is the solution correct? After aider finished working on the problem in the `harness.py` script, the `report.py` script backfilled the acceptance testing outcome into the json file.
- tries - Disregard. Intended to record how many loops through the models were made, but suffered from an off-by-one bug.
- all_results - A list of dicts for all 1-6 results produced by aider working on this problem, in the order produced. Each dict has all of the above fields except `resolved`, `tries`.

The result chosen by the harness is the top level dict of the json file.
This result will also appear in the `all_results` list.
The harness was designed to stop as soon as a plausible result was found
and select it.
If no plausible solution is found after all 6 attempts, then the harness
picks the "most plausible" solution as described in the article.


## Anomalies

There appears to have been a bug introduced late in the benchmarking process.
There was a missing `break` in the inside loop of the harness
(fixed [here](https://github.com/paul-gauthier/aider-swe-bench/commit/a9c21d2e235ef2ead5d49432343de479e8dcc937)).
If gpt-4o found a plausible solution, the inner loop continued and gave opus
1 more try. The result of this bug was that
if opus also found a plausible solution, it was selected;
if not, the gpt-4o plausible solution was selected.
This bug doesn't affect the integrity of the results, but simply
increased the cost to solve the affected problems.
The bug appears to have affected the following instances:

- sphinx-doc__sphinx-7975
- sphinx-doc__sphinx-11445
- sphinx-doc__sphinx-8282
- sphinx-doc__sphinx-8435
- sphinx-doc__sphinx-8627
- sphinx-doc__sphinx-8627
- sphinx-doc__sphinx-7738
- sphinx-doc__sphinx-10325

## all_preds.jsonl

This directory also contains `all_preds.jsonl`, which was distilled from the 300 json files
and [submitted to the official leaderboard](https://github.com/swe-bench/experiments/pull/7).
It is simply the top level `instance_id`, `model_name_or_path` and `model_patch`
from each json file concatenated into a jsonl file.
The `report.py` script produces this file.

