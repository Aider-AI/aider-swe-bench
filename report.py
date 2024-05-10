#!/usr/bin/env python

import json
import time
import os
import sys

from pathlib import Path
from collections import defaultdict

from dump import dump

from swebench.metrics.report import get_model_report

model = sys.argv[1]

predictions_path = f"{model}.jsonl"
swe_bench_tasks = "dataset.json"
log_dir = "/tmp/logs/" + model

report = get_model_report(model, predictions_path, swe_bench_tasks, log_dir, verbose=True)

#for k, v in report.items():
#    print(f"- {k}: {len(v)}")


dump(report)
