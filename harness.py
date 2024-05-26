#!/usr/bin/env python

import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import lox
from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model

from dump import dump
from tests import run_tests
from utils import (
    get_dataset,
    get_devin_instance_ids,
    get_plausible,
    load_predictions,
    pick_winner,
)

REPOS_DNAME = Path("repos")
CHAT_LOGS_DNAME = Path("chat-logs")
PREDS_DNAME = Path("predictions")


def diff_versus_commit(git_dname, commit):
    """
    Take a diff of `git_dname` current contents versus the `commit`.
    """

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
    """
    Clone the SWE Bench entry's git `repo` into `dname` at the `base_commit`.
    Make a tempdir if no `dname` provided.
    """
    github_url = "https://github.com/"
    repo_url = github_url + entry["repo"]
    commit = entry["base_commit"]

    print(repo_url, commit)

    git_tempdir = checkout_repo_url_commit(repo_url, commit, dname)

    return git_tempdir


def checkout_repo_url_commit(url, commit, dname):
    """
    Clone the git `url` into `dname` at `commit`.
    Check a local cache of the bare repo to avoid pulling from github every time.
    """

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


def show_problems(dataset):
    """
    Print out all the instance_id and problem_descriptions.
    """
    for inst, entry in dataset.items():
        problem = entry["problem_statement"].splitlines()[0]
        print(f"{inst}: {problem}")


def run_pre_existing_tests(entry, git_dname):
    """Given the current contents of the `git_dname`, run the tests that
    were present in the entry's `repo` at the time of the
    `base_commit` or which have been added into the repo since.  This
    checks if the code in the `git_dname` has broken pre-existing
    tests or is failing any newly added tests.

    It does NOT attempt to run the tests in the `test_patch` which
    are used to evaluate whether the `model_patch` has resolved the
    `problem_statement`.

    Returns None if all the tests passed. Returns the text of the
    test run output if any failed.
    """

    model_patch = diff_versus_commit(git_dname, entry["base_commit"])
    passed, output = run_tests(
        entry,
        model_patch=model_patch,
        use_test_patch=False,
    )
    if passed:
        return

    # Just keep the output after the (no-op) test patch applied,
    # which is the actual output from the tests that were run.
    output = output.split(">>>>> Applied Patch (test)")[-1]

    return output


def get_coder(model, git_dname, chat_history_file, test_cmd, temperature, oracle_files=None):
    """
    Get an instance of aider to work with the given LLM `model` at `temperature`
    on the code in `git_dname`. Will store the markdown chat logs in
    the `chat_history_file`. Tells aider it can use the `test_cmd` to
    run tests after the LLM edits files.

    If `oracle_files` are provided, they are added to the aider chat automatically.
    """
    if oracle_files and git_dname:
        oracle_files = [Path(git_dname) / fname for fname in oracle_files]

    model = Model(model)
    io = InputOutput(
        yes=True,  # Say yes to every suggestion aider makes
        chat_history_file=chat_history_file,  # Log the chat here
        input_history_file="/dev/null",  # Don't log the "user input"
    )

    dump(git_dname)

    coder = Coder.create(
        main_model=model,
        io=io,
        git_dname=git_dname,
        map_tokens=2048,  # Use 2k tokens for the repo map
        stream=False,
        auto_commits=False,  # Don't bother git committing changes
        fnames=oracle_files,
        auto_test=True,  # Automatically run the test_cmd after making changes
        test_cmd=test_cmd,
        # verbose=True,
    )
    coder.temperature = temperature

    # Take at most 4 steps before giving up.
    # Usually set to 5, but this reduces API costs.
    coder.max_reflections = 4

    # Add announcement lines to the markdown chat log
    coder.show_announcements()

    # messages = coder.format_messages()
    # utils.show_messages(messages)

    return coder


def process_one_instance(entry, models, temperature, model_name_or_path, out_dname):
    """
    Process one `entry` from SWE Bench using the LLM `model`.
    Set `model_name_or_path` in the result json.
    Store the result json and the chat log into `out_dname`.
    """

    instance_id = entry["instance_id"]
    base_commit = entry["base_commit"]

    print("=" * 60)
    dump(instance_id)
    print("=" * 60)
    problem_statement = entry["problem_statement"]
    print(problem_statement)

    ###
    # DO NOT assist aider by telling it which files need to be modified!
    oracle = False
    gold_files = files_in_patch(entry["patch"])
    if oracle:
        oracle_files = gold_files
    else:
        oracle_files = None
    ###

    chat_history_file = out_dname / (instance_id + ".md")

    results = []
    cost = 0
    winner = None
    NUM_TRIES = 1

    for attempt in range(1, NUM_TRIES + 1):
        for model in models:
            dump(attempt, model)

            git_tempdir = checkout_repo(entry)
            dump(git_tempdir)

            # Prepare the test command which will run the pre-existing tests
            test_cmd = lambda: run_pre_existing_tests(entry, git_tempdir)  # noqa: E731

            # Get an instance of aider
            coder = get_coder(
                model,
                git_tempdir,
                chat_history_file,
                test_cmd,
                temperature,
                oracle_files,
            )

            dump(instance_id)
            dump(gold_files)

            # Tell aider to work on the `problem_statement`.
            # This is the same as if you pasted it into a fresh chat with aider
            # launched in the repo.
            try:
                coder.run(problem_statement)
            except Exception as coder_err:
                # swallow any exceptions during benchmarking
                dump(coder_err)
                continue

            # Take note of which files aider added to the chat
            added_files = coder.get_inchat_relative_files()

            dump(instance_id)
            dump(gold_files)
            dump(added_files)

            # Keep track of API costs
            cost += coder.total_cost

            # Get the diff between the current state and the original commit
            model_patch = diff_versus_commit(git_tempdir, base_commit)
            dump(model_patch)

            # Record the results for the logs
            result = dict(
                # Required args for running eval tests
                instance_id=instance_id,
                model_name_or_path=model_name_or_path,
                model_patch=model_patch,
                # For computing stats
                model=model,
                temperature=temperature,
                cost=coder.total_cost,
                added_files=added_files,
                gold_files=gold_files,
                edited_files=files_in_patch(model_patch),
                edit_outcome=coder.edit_outcome,
                lint_outcome=coder.lint_outcome,
                test_outcome=coder.test_outcome,
            )
            result["try"] = attempt  # `try` is a python keyword
            results.append(result)

            dump(result)

            # Did we get a successful edit, lint and test? If so, we're done!
            if model_patch and coder.edit_outcome and coder.lint_outcome and coder.test_outcome:
                winner = result

        # also break out of the attempts loop
        if winner:
            break

    # If there's no clear winner, look for the most viable result we got...
    if not winner:
        winner = pick_winner(results)

    if not winner:
        result = dict(
            # Required args for running eval tests
            instance_id=instance_id,
            model_name_or_path=model_name_or_path,
            model_patch=None,
        )

    dump(winner)

    print("\n\nFinal diff:\n")
    print(winner["model_patch"])

    # Avoid circular reference when we save to json
    winner = dict(winner)

    winner.update(
        dict(
            tries=attempt,
            all_results=results,  # Record all the results for later analysis
            cost=cost,  # total cost across all results
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
    # model = "gpt-4o"
    # model = "openrouter/anthropic/claude-3-opus"

    # models = ["openrouter/deepseek/deepseek-chat"]
    # models = ["gpt-4o", "openrouter/anthropic/claude-3-opus"]
    models = ["openrouter/anthropic/claude-3-opus"]
    # models = ["gpt-4o"]
    # models = ["gpt-4-1106-preview"]

    prefix = "full-"
    # prefix = "full025-"

    models_slug = "--".join(model.replace("/", "-") for model in models)
    model_name_or_path = "aider--" + models_slug
    models_slug = prefix + "--" + models_slug

    temperature = 0

    dump(models)
    dump(temperature)

    ###
    # models = ["gpt-4o"]
    # models_slug = "flake-isolated-gpt-4o"
    # model_name_or_path = "aider-gpt-4o"

    out_dname = PREDS_DNAME / models_slug
    if not out_dname.exists():
        out_dname.mkdir()

    dump(out_dname)

    done_preds = load_predictions([out_dname])
    done_instances = set(done_preds.keys())
    dump(len(done_instances))

    prior_dnames = sys.argv[1:]
    dump(prior_dnames)
    prior_preds = load_predictions(prior_dnames)
    dump(len(prior_preds))

    plausible_instances = get_plausible(prior_preds)
    dump(len(plausible_instances))

    if prior_preds:
        all_instances = set(prior_preds.keys())
    else:
        all_instances = set(dataset.keys())

    remaining_instances = set(all_instances)

    devin_insts = get_devin_instance_ids()
    remaining_instances = remaining_instances.intersection(devin_insts)

    remaining_instances -= done_instances
    remaining_instances -= plausible_instances

    remaining_instances = list(remaining_instances)
    random.shuffle(remaining_instances)

    dump(len(remaining_instances))

    print()
    print("press enter...")
    input()

    chat_history_dname = CHAT_LOGS_DNAME / models_slug
    chat_history_dname.mkdir(exist_ok=True)

    THREADS = 10
    if THREADS > 1:
        process_one_instance_lox = lox.thread(THREADS)(process_one_instance)
        process_one_instance_func = process_one_instance_lox.scatter
        gather = process_one_instance_lox.gather
    else:
        process_one_instance_func = process_one_instance
        gather = lambda: None  # noqa: E731

    for instance_id in remaining_instances:
        if instance_id in done_instances:
            print("skipping", instance_id)
            continue

        process_one_instance_func(
            dataset[instance_id],
            models,
            temperature,
            model_name_or_path,
            out_dname,
        )

        print("#" * 60)
        # input()

    if THREADS > 1:
        gather()


if __name__ == "__main__":
    status = main()
    sys.exit(status)
