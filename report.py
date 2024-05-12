#!/usr/bin/env python

import json
import time
import os
import sys

from pathlib import Path
from collections import defaultdict

from dump import dump

from swebench.metrics.report import get_model_report

pred_path = sys.argv[1]

for line in open(pred_path):
    break
data = json.loads(line)

model = data['model_name_or_path']
swe_bench_tasks = "princeton-nlp--SWE-bench_Lite.json"
log_dir = "logs"

report = get_model_report(model, pred_path, swe_bench_tasks, log_dir, verbose=True)

#for k, v in report.items():
#    print(f"- {k}: {len(v)}")

#dump(report)

all_instances = set(report['generated'])
all_instances.update(set(report['no_generation']))

dump(len(all_instances))

counts = dict( (k,len(v)) for k,v in report.items() )

dump(counts)

total = counts['generated'] + counts['no_generation']
dump(total)
missing_logs = total - counts['with_logs']
dump(missing_logs)

percent = counts['resolved'] * 100 / (counts['generated'] + counts['no_generation'])
print(f"{percent= :.1f}%")

print()

# NEED TO BE RUN?
need_to_be_run = missing_logs - counts['no_generation']
if need_to_be_run:
    dump(need_to_be_run)

    should_count = total - need_to_be_run
    dump(should_count)

    percent_of_should = counts['resolved'] * 100 / should_count
    print(f"{percent_of_should=:.1f}")


# load predictions
predictions = [json.loads(line) for line in open(pred_path)]

# COSTS
costs = []
for data in predictions:
    cost = data.get('cost')
    if cost is not None and cost > 0:
        costs.append(cost)

if len(costs):
    recent = costs[-5:]
    recent = [f"{c:.2f}" for c in recent]
    print("recent costs:", ', '.join(recent))
    avg_cost = sum(costs) / len(costs)
    print(f"avg_cost: ${avg_cost:.2f}/instance")

    num_instances = len(json.load(open(swe_bench_tasks)))
    expected_cost = num_instances * avg_cost
    print(f"expected_cost: ${expected_cost:.2f}")

    print()

# added gold files?

total_gold = 0
total_added = 0
gold_resolved = 0

added_timeline = ''
timeline = ''
for data in predictions:
    gold_files = set(data.get('gold_files', []))
    added_files = set(data.get('added_files', []))

    resolved = (data['instance_id'] in report['resolved'])
    gold = (added_files.intersection(gold_files) == gold_files) and gold_files

    if added_files:
        added_timeline += str(len(added_files))
    else:
        added_timeline += '_'

    if gold_files:
        total_gold += 1
        if gold:
            total_added += 1

    if not gold_files and not resolved:
        timeline += '.'
    elif gold and resolved:
        timeline += 'R'
        gold_resolved += 1
    elif gold and not resolved:
        timeline += 'g'
    elif not gold and not resolved:
        timeline += '_'
    elif not gold and resolved:
        timeline += '!'
        #print(data['instance_id'])

#dump(total_gold)
#dump(total_added)
if total_gold:
    pct_added = total_added / total_gold * 100
    print(f"pct_gold_added: {pct_added:.1f}%")


    pct_gold_resolved = gold_resolved / total_gold * 100
    print(f"pct_gold_resolved: {pct_gold_resolved:.1f}%")

    print()

print(timeline)
print(added_timeline)
