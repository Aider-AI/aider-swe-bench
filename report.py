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

counts = dict( (k,len(v)) for k,v in report.items() )

dump(counts)

total = counts['generated'] + counts['no_generation']
dump(total)
missing_logs = total - counts['with_logs']
dump(missing_logs)

need_to_be_run = missing_logs - counts['no_generation']
dump(need_to_be_run)

should_count = total - need_to_be_run

percent = counts['resolved'] * 100 / (counts['generated'] + counts['no_generation'])
print(f"{percent=:.1f}")

dump(should_count)
percent_of_should_count = counts['resolved'] * 100 / should_count
print(f"{percent_of_should_count=:.1f}")


#dump(report['resolved'])
