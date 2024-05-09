#!/usr/bin/env python

import sys

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

REPOS_DNAME = 'repos'

def checkout_repo(url, commit):
    # if needed, clone url into a subdir of REPOS_DNAME
    # checkout the given commit

dataset = load_dataset("princeton-nlp/SWE-bench_Lite")

instance_id = 'django__django-12983'

for entry in dataset['test']:
    if entry['instance_id'] == instance_id:
        break
    #print(entry['instance_id'])

print("-" * 40)  # Separator between entries
for attribute, value in entry.items():
    print(f"{attribute}")#: {value}")

repo_url = entry['repo']
commit = entry['base_commit']

dname = checkout_repo(repo_url, commit)
