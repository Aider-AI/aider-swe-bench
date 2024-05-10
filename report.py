#!/usr/bin/env python

import json
import time
import os
import sys

from pathlib import Path
from collections import defaultdict

from dump import dump

from swebench.metrics.report import get_model_report

model = "aider_openrouter_anthropic_claude-3-opus"
predictions_path = "/app/tmp.jsonl"
swe_bench_tasks = "/app/dataset.json"
log_dir = "/logs/" + model

report = get_model_report(model, predictions_path, swe_bench_tasks, log_dir, verbose=True)

#for k, v in report.items():
#    print(f"- {k}: {len(v)}")


dump(report)
