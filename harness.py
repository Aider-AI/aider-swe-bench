#!/usr/bin/env python

import json
import json
import random
import sys
import tempfile
from pathlib import Path

import lox
from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from datasets import load_dataset

from dump import dump

REPOS_DNAME = Path("repos")
CHAT_LOGS_DNAME = Path("chat-logs")
PREDS_DNAME = Path("predictions")

import subprocess


def diff_versus_commit(git_dname, commit):
    diff_cmd = f"git -C {git_dname} diff {commit}"
    diff_output = subprocess.check_output(diff_cmd.split()).decode()
    return diff_output


def files_in_patch(patch):
    """
    Extract the list of modified files from a unified diff patch string.
    """
    files = []
    for line in patch.split("\n"):
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            fname = line.split("/", 1)[1]
            if fname not in files:
                files.append(fname)
    return files


def checkout_repo(entry, dname=None):
    github_url = "https://github.com/"
    repo_url = github_url + entry["repo"]
    commit = entry["base_commit"]

    print(repo_url, commit)

    git_tempdir = checkout_repo_url_commit(repo_url, commit, dname)

    return git_tempdir


def checkout_repo_url_commit(url, commit, dname):
    # Extract repo name from URL
    repo_name = url.split("/")[-1].split(".")[0]
    repo_name += ".git"

    # dump(repo_name)
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

    # IGNORE = '*test*\n'
    # ignore = Path(repo_dname) / '.aiderignore'
    # ignore.write_text(IGNORE)

    return repo_dname


DATASET = "princeton-nlp/SWE-bench_Lite"
DATASET_JSON = DATASET.replace("/", "--") + ".json"


def get_dataset():
    fname = Path(DATASET_JSON)
    if fname.exists():
        dataset = json.loads(fname.read_text())
    else:
        dataset = load_dataset(DATASET)
        dataset = dataset["test"]
        dump_dataset(dataset)

    res = dict()
    for entry in dataset:
        res[entry["instance_id"]] = entry

    return res


def dump_dataset(dataset):
    entries = list(dataset)
    for entry in entries:
        entry["FAIL_TO_PASS"] = json.loads(entry["FAIL_TO_PASS"])
        entry["PASS_TO_PASS"] = json.loads(entry["PASS_TO_PASS"])

    with open(DATASET_JSON, "w") as f:
        json.dump(entries, f, indent=4)


def show_problems(dataset):
    for inst, entry in dataset.items():
        problem = entry["problem_statement"].splitlines()[0]
        print(f"{inst}: {problem}")


def get_coder(
    model, temp, git_dname, instance_id, base_commit, chat_history_file, oracle_files=None
):
    if oracle_files and git_dname:
        oracle_files = [Path(git_dname) / fname for fname in oracle_files]

    model = Model(model)
    io = InputOutput(
        pretty=True,
        yes=True,
        chat_history_file=chat_history_file,
        input_history_file="/dev/null",
    )

    test_cmd = f"python run_pre_existing_tests.py {instance_id} {base_commit} {git_dname}"

    coder = Coder.create(
        main_model=model,
        io=io,
        git_dname=git_dname,
        map_tokens=2048,
        stream=False,
        auto_commits=False,
        fnames=oracle_files,
        test_cmd=test_cmd,
        # verbose=True,
    )
    coder.temperature = temp

    coder.show_announcements()

    # messages = coder.format_messages()
    # utils.show_messages(messages)

    return coder


def process_one_instance(entry, model, out_dname):
    oracle = False

    instance_id = entry["instance_id"]
    base_commit = entry["base_commit"]

    print("=" * 60)
    dump(instance_id)
    print("=" * 60)
    problem = entry["problem_statement"]
    print(problem)

    gold_files = files_in_patch(entry["patch"])
    if oracle:
        oracle_files = gold_files
    else:
        oracle_files = None

    chat_history_file = out_dname / (instance_id + ".md")

    results = []
    tries = 0
    temp = 0.0
    cost = 0
    winner = None
    while tries < 3:
        tries += 1
        dump(tries, temp)

        git_tempdir = checkout_repo(entry)
        coder = get_coder(
            model,
            temp,
            instance_id,
            base_commit,
            git_tempdir,
            chat_history_file,
            oracle_files,
        )
        temp += 0.25

        dump(gold_files)
        coder.run(problem)
        added_files = coder.get_inchat_relative_files()
        dump(gold_files)
        dump(added_files)
        dump(instance_id)

        cost += coder.total_cost

        # Get the diff between the current state and the original commit
        model_patch = diff_versus_commit(git_tempdir, base_commit)
        dump(model_patch)

        result = dict(
            temperature=temp,
            model_patch=model_patch,
            added_files=added_files,
            gold_files=gold_files,
            edited_files=files_in_patch(model_patch),
            edit_outcome=coder.edit_outcome,
            lint_outcome=coder.lint_outcome,
            test_outcome=coder.test_outcome,
        )
        result["try"] = tries
        results.append(result)

        dump(result)

        if model_patch and coder.edit_outcome and coder.lint_outcome and coder.test_outcome:
            winner = result
            break

    if not winner:
        # Look for one that passed everything but tests
        for res in results:
            if res["model_patch"] and res["edit_outcome"] and res["lint_outcome"]:
                winner = res
                break
    if not winner:
        # Look for one that compiles!
        for res in results:
            if res["model_patch"] and res["lint_outcome"]:
                winner = res
                break
    if not winner:
        # Take anything that has a patch!!
        for res in results:
            if res["model_patch"]:
                winner = res
                break

    print("\n\nFinal diff:\n")
    print(winner["model_patch"])

    winner.update(
        dict(
            instance_id=instance_id,
            model_name_or_path=out_dname.name,
            cost=cost,
            tries=tries,
            all_results=results,
        )
    )

    out_fname = out_dname / (instance_id + ".json")
    out_fname.write_text(json.dumps(winner, indent=4))


def main():
    dataset = get_dataset()

    # model = "gemini/gemini-1.5-pro-latest"
    # model = "gpt-3.5-turbo"
    # model = "gpt-4-1106-preview"
    # model = "gold"

    # model = "deepseek/deepseek-chat"
    model = "gpt-4o"
    # model = "openrouter/anthropic/claude-3-opus"

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
        done_instances.add(rec["instance_id"])

    all_instances = [Path(fn).with_suffix("").name for fn in sys.argv[1:]]
    if not all_instances:
        all_instances = dataset.keys()

    all_instances = list(all_instances)
    random.shuffle(all_instances)

    chat_history_dname = CHAT_LOGS_DNAME / model_slug
    chat_history_dname.mkdir(exist_ok=True)

    THREADS = 10
    if THREADS > 1:
        process_one_instance_func = lox.thread(THREADS)(process_one_instance).scatter
    else:
        process_one_instance_func = process_one_instance

    for instance_id in all_instances:
        if instance_id in done_instances:
            print("skipping", instance_id)
            continue

        process_one_instance_func(
            dataset[instance_id],
            model,
            out_dname,
        )

        print("#" * 60)
        # input()

    if THREADS > 1:
        process_one_instance.gather()


if __name__ == "__main__":
    status = main()
    sys.exit(status)
