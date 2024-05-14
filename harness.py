#!/usr/bin/env python

import random
import json
import time
import os
import sys
import tempfile
import re

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

def checkout_repo(entry, dname=None):
    github_url = 'https://github.com/'
    repo_url = github_url + entry['repo']
    commit = entry['base_commit']

    print(repo_url, commit)

    git_tempdir = checkout_repo_url_commit(repo_url, commit, dname)

    return git_tempdir


def checkout_repo_url_commit(url, commit, dname):
    # Extract repo name from URL
    repo_name = url.split("/")[-1].split(".")[0]
    repo_name += ".git"

    #dump(repo_name)
    bare_repo = REPOS_DNAME / repo_name

    if not bare_repo.exists():
        cmd = f"git clone --bare {url} {bare_repo}"
        subprocess.run(cmd.split(), check=True)

    if dname:
        Path(dname).mkdir()
        repo_dname = dname
    else:
        repo_dname = tempfile.TemporaryDirectory().name

    cmd = f"git clone {bare_repo} {repo_dname}"
    subprocess.run(cmd.split(), check=True)

    cmd = f"git -c advice.detachedHead=false -C {repo_dname} checkout {commit}"
    subprocess.run(cmd.split(), check=True)

    #IGNORE = '*test*\n'
    #ignore = Path(repo_dname) / '.aiderignore'
    #ignore.write_text(IGNORE)

    return repo_dname


DATASET = "princeton-nlp/SWE-bench_Lite"
DATASET_JSON = DATASET.replace('/', '--') + '.json'

def get_dataset():

    fname = Path(DATASET_JSON)
    if fname.exists():
        dataset = json.loads(fname.read_text())
    else:
        dataset = load_dataset(DATASET)
        dataset = dataset['test']
        dump_dataset(dataset)

    res = dict()
    for entry in dataset:
        res[entry['instance_id']] = entry

    return res

def dump_dataset(dataset):
    entries = list(dataset)
    for entry in entries:
        entry['FAIL_TO_PASS'] = json.loads(entry['FAIL_TO_PASS'])
        entry['PASS_TO_PASS'] = json.loads(entry['PASS_TO_PASS'])

    with open(DATASET_JSON, "w") as f:
        json.dump(entries, f, indent=4)


def show_problems(dataset):
    for inst,entry in dataset.items():
        problem = entry['problem_statement'].splitlines()[0]
        print(f"{inst}: {problem}")


def doit(model, entry, chat_history_file):
    instance_id = entry['instance_id']
    oracle = False

    git_tempdir = checkout_repo(entry)

    gold_patch = entry['patch']
    rel_gold_files = files_in_patch(gold_patch)
    gold_files = [Path(git_tempdir) / fname for fname in rel_gold_files]

    model = Model(model)
    io = InputOutput(
        pretty=True,
        yes=True,
        chat_history_file=chat_history_file,
        input_history_file="/dev/null",
    )
    kwargs = dict(
        main_model=model,
        io=io,
        git_dname=git_tempdir,
        map_tokens = 2048,
        stream=False,
        auto_commits=False,
        #verbose=True,
    )
    if oracle:
        kwargs['fnames'] = gold_files

    problem = entry["problem_statement"]
    print(problem)

    coder = Coder.create(**kwargs)

    coder.show_announcements()
    coder.max_apply_update_errors = 2

    if False:
        mentioned_files = coder.get_file_mentions(problem)
        mentioned_idents = coder.get_ident_mentions(problem)
        dump(mentioned_files)
        dump(mentioned_idents)

        abs_mentioned_files = set(coder.abs_root_path(f) for f in mentioned_files)
        repo_map = coder.repo_map.get_repo_map(
            set(), # chat files
            set(coder.get_all_abs_files()), # other files
            mentioned_fnames = abs_mentioned_files,
            mentioned_idents = mentioned_idents,
        ) or ""

        gold_file = rel_gold_files[0]
        dump(gold_file)
        map_has_gold_file = any(line.startswith(gold_file) for line in repo_map.splitlines())
        dump(map_has_gold_file)
        return dict(initial_map_has_gold_file=map_has_gold_file)

    #messages = coder.format_messages()
    #utils.show_messages(messages)

    problem_prefix = """Don't do any coding yet!
First, just tell me which files are the most likely to **need changes** to solve this?
Only include the 1-2 file or files that are most likely to actually need to be edited.
Don't include files that might contain relevant context, just files that will need to be changed.

Don't suggest test files or doc files, just the source code that needs to be changed.


"""

    #if not oracle:
    #    problem = problem_prefix + problem

    dump(rel_gold_files)

    coder.run(problem)

    added_files = coder.get_inchat_relative_files()
    dump(rel_gold_files)
    dump(added_files)
    dump(instance_id)

    # Get the diff between the current state and the original commit
    commit = entry['base_commit']
    cmd = f"git -C {git_tempdir} diff {commit}"
    diff_output = subprocess.check_output(cmd.split()).decode()

    if not diff_output:
        coder.run("Please try and fix the issue I provided! Let me know if you need to edit a different file.")
        diff_output = subprocess.check_output(cmd.split()).decode()

    print(f"\nDiff between current state and commit {commit}:")
    print(diff_output)

    res = dict(
        model_patch=diff_output,
        cost=coder.total_cost,
        added_files=added_files,
        gold_files=rel_gold_files,
        edited_files=files_in_patch(diff_output),
    )
    return res


def main():

    dataset = get_dataset()

    #model = "gpt-3.5-turbo"
    #model = "deepseek/deepseek-chat"
    #model = "openrouter/anthropic/claude-3-opus"
    #model = "gpt-4-1106-preview"
    #model = "gold"
    model = "openai/gpt-4o"

    #prefix = "oracle-"
    #prefix = "fixed-repomap-"

    #prefix = "mentions-"
    prefix = "mention-16x2-"

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

    all_instances = list(all_instances)
    random.shuffle(all_instances)

    chat_history_dname = CHAT_LOGS_DNAME / model_slug
    chat_history_dname.mkdir(exist_ok=True)

    for instance_id in all_instances:
        entry = dataset[instance_id]

        if instance_id in done_instances:
            print('skipping', instance_id)
            continue

        dump(instance_id)

        repo = entry['repo']
        version = entry['version']

        if model == "gold":
            res = dict(model_patch=entry['patch'])
        else:
            chat_history_file = chat_history_dname / (entry['instance_id'] + '.md')
            res = doit(model, entry, chat_history_file)

        result = dict(
            model_name_or_path=model_slug,
            instance_id=instance_id,
        )
        result.update(res)

        with open(out_fname, "a") as fh:
            fh.write(json.dumps(result) + "\n")

if __name__ == '__main__':
    status = main()
    sys.exit(status)
