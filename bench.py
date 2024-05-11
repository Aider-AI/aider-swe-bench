#!/usr/bin/env python

import random
import json
import time
import os
import sys
import tempfile

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

from aider.io import InputOutput
from aider.coders import Coder
from aider.models import Model
from aider import utils


REPOS_DNAME = Path('repos')
CHAT_LOGS_DNAME = Path("chat-logs")
PREDS_DNAME = Path("predictions")

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


IGNORE = '*test*\n'

def checkout_repo(url, commit):
    # Extract repo name from URL
    repo_name = url.split("/")[-1].split(".")[0]
    repo_name += ".git"

    dump(repo_name)
    bare_repo = REPOS_DNAME / repo_name

    if not bare_repo.exists():
        cmd = f"git clone --bare {url} {bare_repo}"
        subprocess.run(cmd.split(), check=True)

    repo_tempdir = tempfile.TemporaryDirectory()

    cmd = f"git clone {bare_repo} {repo_tempdir.name}"
    subprocess.run(cmd.split(), check=True)

    cmd = "git config --global advice.detachedHead false"
    subprocess.run(cmd.split(), check=True)

    cmd = f"git -C {repo_tempdir.name} checkout {commit}"
    subprocess.run(cmd.split(), check=True)

    #ignore = Path(repo_tempdir.name) / '.aiderignore'
    #ignore.write_text(IGNORE)

    return repo_tempdir


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


def doit(model, entry, chat_history_file):

    github_url = 'https://github.com/'
    repo_url = github_url + entry['repo']
    commit = entry['base_commit']

    gold_patch = entry['patch']
    rel_gold_files = files_in_patch(gold_patch)

    git_tempdir = checkout_repo(repo_url, commit)

    gold_files = [Path(git_tempdir.name) / fname for fname in rel_gold_files]

    model = Model(model)
    io = InputOutput(
        pretty=True,
        yes=True,
        chat_history_file=chat_history_file,
        input_history_file="/dev/null",
    )
    coder = Coder.create(
        main_model=model,
        io=io,
        git_dname=git_tempdir.name,
        #fnames=gold_files,
        map_tokens = 2048,
    )
    coder.show_announcements()

    messages = coder.format_messages()
    #utils.show_messages(messages)

    problem_prefix = """Don't do any coding yet!
First, just tell me **which files are the most likely to need changes to solve this**?
Be specific, don't mention irrelevant files.
But if you are unsure, give me a longer list of files.

Don't suggest test files or doc files, just the source code that needs to be changed.


"""

    problem = entry["problem_statement"]
    problem = problem_prefix + problem

    dump(rel_gold_files)

    coder.run(problem)

    dump(rel_gold_files)
    added_files = coder.get_inchat_relative_files()
    dump(added_files)

    # Get the diff between the current state and the original commit
    cmd = f"git  -C {git_tempdir.name} diff {commit}"
    diff_output = subprocess.check_output(cmd.split()).decode()

    print(f"\nDiff between current state and commit {commit}:")
    print(diff_output)
    return diff_output


def main():

    dataset = get_dataset()

    #model = "gpt-3.5-turbo"
    #model = "deepseek/deepseek-chat"
    model = "openrouter/anthropic/claude-3-opus"
    #model = "gpt-4-1106-preview"
    #model = "gold"

    prefix = "2k-context-"

    model_slug = prefix + model.replace("/", "--")
    out_fname = PREDS_DNAME / (model_slug + ".jsonl")
    dump(out_fname)

    done_instances = set()
    if Path(out_fname).exists():
        for line in open(out_fname):
            if not line.strip():
                continue
            rec = json.loads(line)
            done_instances.add(rec['instance_id'])

    all_instances = sys.argv[1:]
    if not all_instances:
        all_instances = dataset.keys()

    _all_instances = [
    "sympy__sympy-14774",
    "django__django-14915",
    "sympy__sympy-20590",
    "django__django-10914",
    "sympy__sympy-22714"
    ]

    all_instances = list(all_instances)
    random.shuffle(all_instances)

    chat_history_dname = CHAT_LOGS_DNAME / model_slug
    chat_history_dname.mkdir(exist_ok=True)

    for instance_id in all_instances:
        entry = dataset[instance_id]

        if instance_id in done_instances:
            print('skipping', instance_id)
            continue

        repo = entry['repo']
        version = entry['version']

        if model == "gold":
            diff = entry['patch']
        else:
            chat_history_file = chat_history_dname / (entry['instance_id'] + '.md')
            diff = doit(model, entry, chat_history_file)

        res = dict(
            model_name_or_path=model_slug,
            instance_id=instance_id,
            model_patch=diff,
        )

        with open(out_fname, "a") as fh:
            fh.write(json.dumps(res) + "\n")

if __name__ == '__main__':
    status = main()
    sys.exit(status)
