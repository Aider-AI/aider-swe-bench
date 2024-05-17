#!/usr/bin/env python

import random
import json
import time
import os
import sys
import tempfile
import re
import lox

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

from aider.io import InputOutput
from aider.coders import Coder
from aider.models import Model
from aider import utils

from tests import run_tests

REPOS_DNAME = Path('repos')
CHAT_LOGS_DNAME = Path("chat-logs")
PREDS_DNAME = Path("predictions")

import subprocess

def lint(fname):
    fatal = 'E9,F821,F823,F831,F406,F407,F701,F702,F704,F706'
    cmd = f"flake8 --select={fatal} --show-source --exit-zero {fname}"
    errors = subprocess.check_output(cmd.split()).decode()
    return errors


def diff_versus_commit(git_dname, commit):
    diff_cmd = f"git -C {git_dname} diff {commit}"
    diff_output = subprocess.check_output(diff_cmd.split()).decode()
    return diff_output


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



def get_coder(model, git_dname, chat_history_file, oracle_files=None):

    if oracle_files:
        oracle_files = [Path(git_tempdir) / fname for fname in oracle_files]

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
        git_dname=git_dname,
        map_tokens = 2048,
        stream=False,
        auto_commits=False,
        #verbose=True,
        fnames = oracle_files,
    )

    coder.show_announcements()
    coder.max_apply_update_errors = 2

    #messages = coder.format_messages()
    #utils.show_messages(messages)
    return coder

THREADS = 10

@lox.thread(THREADS)
def process_one_instance(entry, model, out_dname):

    oracle = False

    instance_id = entry['instance_id']

    print("="*60)
    dump(instance_id)
    print("="*60)
    problem = entry["problem_statement"]
    print(problem)

    gold_files = files_in_patch(entry['patch'])
    if oracle:
        oracle_files = gold_files
    else:
        oracle_files = None

    chat_history_file = out_dname / (instance_id + '.md')

    passed_tests_before = None
    results = []
    tries = 0
    temp = 0.
    cost = 0
    while tries < 3:

        tries += 1
        dump(tries, temp)

        git_tempdir = checkout_repo(entry)
        coder = get_coder(model, git_tempdir, chat_history_file, oracle_files)

        coder.temperature = temp
        temp += 0.25

        dump(gold_files)
        coder.run(problem)
        added_files = coder.get_inchat_relative_files()
        dump(gold_files)
        dump(added_files)
        dump(instance_id)

        cost += coder.total_cost

        # Get the diff between the current state and the original commit
        diff = diff_versus_commit(git_tempdir, entry['base_commit'])
        dump(diff)

        result = dict(
            model_patch=diff,
            added_files=added_files,
            gold_files=gold_files,
            edited_files=files_in_patch(diff),
        )
        results.append(result)

        if not diff:
            continue

        lint_errors = ''
        for fname in files_in_patch(diff):
            lint_errors += lint(Path(git_tempdir) / fname)

        if lint_errors:
            dump(lint_errors)
            continue

        if passed_tests_before is None:
            passed_tests_before,_output = run_tests(entry)
            dump(passed_tests_before)

        if passed_tests_before:
            passed_with_patch,_output = run_tests(entry, model_patch=diff)
            dump(passed_with_patch)
            if not passed_with_patch:
                continue

        results = [result]
        break

    for result in results:
        if result['model_patch']:
            break

    if not result['model_patch']:
        result = result[0]


    print(f"\n\nFinal diff:\n")
    print(diff)

    result.update(dict(
        instance_id=instance_id,
        model_name_or_path=out_dname.name,
        cost=cost,
        tries=tries,
    ))

    out_fname = out_dname / (instance_id + ".json")
    out_fname.write_text(json.dumps(result, indent=4))


def main():

    dataset = get_dataset()

    #model = "gemini/gemini-1.5-pro-latest"
    #model = "gpt-3.5-turbo"
    #model = "gpt-4-1106-preview"
    #model = "gold"

    #model = "deepseek/deepseek-chat"
    model = "gpt-4o"
    #model = "openrouter/anthropic/claude-3-opus"

    prefix = "tries-"

    model_slug = prefix + model.replace("/", "--")
    out_dname = PREDS_DNAME / model_slug
    if not out_dname.exists():
        out_dname.mkdir()

    done_instances = set()
    for fname in out_dname.glob("*.json"):
        text = fname.read_text()
        if not text:
            continue
        rec = json.loads(fname.read_text())
        done_instances.add(rec['instance_id'])

    all_instances = [
        Path(fn).with_suffix("").name
        for fn in sys.argv[1:]
    ]
    if not all_instances:
        all_instances = dataset.keys()

    all_instances = list(all_instances)
    random.shuffle(all_instances)

    chat_history_dname = CHAT_LOGS_DNAME / model_slug
    chat_history_dname.mkdir(exist_ok=True)

    if THREADS > 1:
        process_one_instance_func = process_one_instance.scatter
    else:
        process_one_instance_func = process_one_instance

    for instance_id in all_instances:
        if instance_id in done_instances:
            print('skipping', instance_id)
            continue

        process_one_instance_func(
            dataset[instance_id],
            model,
            out_dname,
        )

        print('#'*60)
        #input()

    if THREADS > 1:
        process_one_instance.gather()


if __name__ == '__main__':
    status = main()
    sys.exit(status)
