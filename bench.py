#!/usr/bin/env python

import sys

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

REPOS_DNAME = 'repos'

import subprocess

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
    # Extract repo name from URL
    repo_name = url.split("/")[-1].split(".")[0]
    
    # Create directory path for repo
    repo_dir = Path(REPOS_DNAME) / repo_name
    
    # If repo directory doesn't exist, clone the repo
    if not repo_dir.exists():
        clone_repo(url, repo_dir)
    
    # Checkout the specified commit
    checkout_commit(repo_dir, commit)
    
    return repo_dir


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
