#!/usr/bin/env python

import sys

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

cache_dir = Path.home() / '.cache' / 'huggingface' / 'datasets'
dataset = load_dataset("princeton-nlp/SWE-bench_Lite", cache_dir=cache_dir)

instance_id = 'django__django-12983'

for entry in dataset['test']:
    if entry['instance_id'] == instance_id:
        break
    print(entry['instance_id'])
    continue

print("-" * 40)  # Separator between entries
for attribute, value in entry.items():
    print(f"{attribute}: {value}")
