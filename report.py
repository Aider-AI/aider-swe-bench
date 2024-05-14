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

try:
    report = get_model_report(model, pred_path, swe_bench_tasks, log_dir, verbose=True)
except KeyError:
    report = dict()

#for k, v in report.items():
#    print(f"- {k}: {len(v)}")

#dump(report)

all_instances = set(report.get('generated', []))
all_instances.update(set(report.get('no_generation', [])))

dump(len(all_instances))

counts = defaultdict(int, [(k,len(v)) for k,v in report.items()])

dump(counts)

total = counts['generated'] + counts['no_generation']
dump(total)
missing_logs = total - counts['with_logs']
dump(missing_logs)

if total:
    percent = counts['resolved'] * 100 / total
    print(f"{percent= :.1f}%")

    plus_one_percent = (counts['resolved'] + 1)* 100 / (total+1)
    print(f"{plus_one_percent= :.1f}%")

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

total_with_gold_attr = 0
total_added_gold = 0
gold_resolved = 0

added_timeline = ''
repomap_timeline = ''
timeline = ''
for data in predictions:
    gold_files = set(data.get('gold_files', []))
    added_files = set(data.get('added_files', []))

    resolved = (data['instance_id'] in report.get('resolved', []))
    added_gold = (added_files.intersection(gold_files) == gold_files) and gold_files

    if added_files:
        added_timeline += str(len(added_files))
    else:
        added_timeline += '_'

    if gold_files:
        total_with_gold_attr += 1
    if added_gold:
        total_added_gold += 1

    if not gold_files and not resolved:
        timeline += '.'
    elif added_gold and resolved:
        timeline += 'R'
        gold_resolved += 1
    elif added_gold and not resolved:
        timeline += 'g'
    elif not added_gold and not resolved:
        timeline += '_'
    elif not added_gold and resolved:
        timeline += '!'
        #print(data['instance_id'])

    if data.get('initial_map_has_gold_file') or data.get('map_has_gold_file'):
        repomap_timeline += 'M'
    else:
        repomap_timeline += '_'

pct_maps_with_gold_file = len(repomap_timeline.replace('_', '')) / len(repomap_timeline) * 100
dump(pct_maps_with_gold_file)

dump(total_with_gold_attr)
dump(total_added_gold)
if total_with_gold_attr:
    pct_added = total_added_gold / total_with_gold_attr * 100
    print(f"pct_added_gold: {pct_added:.1f}%")


    pct_added_gold_resolved = gold_resolved / total_added_gold * 100
    print(f"pct_added_gold_resolved: {pct_added_gold_resolved:.1f}%")

    print()

print(timeline)
print(added_timeline)
print(repomap_timeline)
