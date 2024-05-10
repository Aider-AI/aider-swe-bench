#!/usr/bin/env python

import json
import time
import os
import sys

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

from aider.io import InputOutput
from aider.coders import Coder
from aider.models import Model
from aider import utils
from aider.utils import ChdirTemporaryDirectory

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


DATASET = "princeton-nlp/SWE-bench_Lite"
def get_dataset():
    dataset = load_dataset(DATASET)

    res = dict()
    for entry in dataset['test']:
        res[entry['instance_id']] = entry

    return res

def dump_dataset():
    dataset = load_dataset(DATASET)

    entries = list(dataset['test'])
    for entry in entries:
        entry['FAIL_TO_PASS'] = json.loads(entry['FAIL_TO_PASS'])
        entry['PASS_TO_PASS'] = json.loads(entry['PASS_TO_PASS'])

    with open("dataset.json", "w") as f:
        json.dump(entries, f, indent=4)

    sys.exit()

#dump_dataset()

def show_problems():
    for inst,entry in dataset.items():
        problem = entry['problem_statement'].splitlines()[0]
        print(f"{inst}: {problem}")


def doit(dataset, model, instance_id):

    entry = dataset[instance_id]
    #dump(entry.keys())

    github_url = 'https://github.com/'
    repo_url = github_url + entry['repo']
    commit = entry['base_commit']

    gold_patch = entry['patch']
    gold_files = files_in_patch(gold_patch)

    git_dname = checkout_repo(repo_url, commit)

    subprocess.run(f"git -C {git_dname} stash".split(), check=True)
    uniq_branch = time.strftime(f"bench-%Y-%m-%d-%H-%M-%S.%f")
    subprocess.run(f"git -C {git_dname} checkout -b {uniq_branch}".split(), check=True)

    for fname in ".aider.chat.history.md .aider.input.history".split():
        fname = Path(fname)
        if fname.exists():
            fname.unlink()

    gold_files = [git_dname / fname for fname in gold_files]

    model = Model(model)
    io = InputOutput(
        pretty=True,
        yes=True,
        chat_history_file="/dev/null",
        input_history_file="/dev/null",
    )
    coder = Coder.create(
        main_model=model,
        io=io,
        git_dname=git_dname,
        fnames=gold_files,
        #map_tokens = 8192,
    )
    coder.show_announcements()

    dump(coder.repo)
    messages = coder.format_messages()
    #utils.show_messages(messages)

    problem = entry["problem_statement"]
    #problem = "Don't do any coding! Just tell me which files should I look at to solve this?\n\n" + problem

    coder.run(problem)

    # Get the diff between the current state and the original commit
    cmd = f"git  -C {git_dname} diff {commit}"
    diff_output = subprocess.check_output(cmd.split()).decode()

    print(f"\nDiff between current state and commit {commit}:")
    print(diff_output)

    model_name_or_path = f"aider--{model}"
    model_name_or_path = model_name_or_path.replace("/", "--")

    res = dict(
        model_name_or_path=model_name_or_path,
        instance_id=instance_id,
        model_patch=diff_output,
    )

    return res



def main():

    dataset = get_dataset()

    #instance_id = 'django__django-12983'
    instance_id = sys.argv[1]

    #model = "gpt-3.5-turbo"
    model = "deepseek/deepseek-chat"
    #model = "openrouter/anthropic/claude-3-opus"

    #with ChdirTemporaryDirectory():
    res = doit(dataset, model, instance_id)

    out_fname = Path("tmp.jsonl")
    out_fname.write_text(json.dumps(res) + "\n")

if __name__ == '__main__':
    status = main()
    sys.exit(status)
