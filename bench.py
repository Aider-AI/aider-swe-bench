#!/usr/bin/env python

import time
import os
import sys

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

from aider.coders import Coder
from aider.models import Model
from aider import utils


REPOS_DNAME = 'repos'

import subprocess


def files_in_patch(patch):
    """
    Extract the list of modified files from a unified diff patch string.
    """
    files = []
    for line in patch.split('\n'):
        if line.startswith('--- a/') or line.startswith('+++ b/'):
            fname = line.split('/', 1)[1]
            if fname not in files:
                files.append(fname)
    return files

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

github_url = 'https://github.com/'
repo_url = github_url + entry['repo']
commit = entry['base_commit']

gold_patch = entry['patch']
gold_files = files_in_patch(gold_patch)

git_dname = checkout_repo(repo_url, commit)

os.chdir(git_dname)

subprocess.run("git stash".split(), check=True)

uniq_branch = f"bench-{time.time()}"
subprocess.run(f"git checkout -b {uniq_branch}".split(), check=True)

model = Model("deepseek/deepseek-chat")

# Create a coder object
coder = Coder.create(
    main_model=model,
    fnames=gold_files,
)

dump(coder.abs_fnames)
dump(coder.repo)
#messages = coder.format_messages()
#utils.show_messages(messages)

sys.exit()
problem = entry["problem_statement"]
coder.run(problem)

# Get the diff between the current state and the original commit
cmd = f"git diff {commit}"
diff_output = subprocess.check_output(cmd.split()).decode()

print(f"\nDiff between current state and commit {commit}:")
print(diff_output)
