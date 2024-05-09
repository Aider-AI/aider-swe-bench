#!/usr/bin/env python

import sys

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

REPOS_DNAME = 'repos'

def clone_repo(url, dname):
    """
    Clone the repository from the given URL into the specified directory.
    """
    cmd = f"git clone {url} {dname}"
    subprocess.run(cmd.split(), check=True)

def checkout_commit(dname, commit):
    """
    Checkout the specified commit in the given directory.
    """
    cmd = f"git -C {dname} checkout {commit}"
    subprocess.run(cmd.split(), check=True)

def checkout_repo(url, commit):
    # if needed, clone url into a subdir of REPOS_DNAME
    # checkout the given commit

import subprocess

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
