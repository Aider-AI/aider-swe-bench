#!/usr/bin/env python

import asyncio
import json
import py_compile
import random
import subprocess
import sys
import tempfile
import traceback
from collections import Counter, defaultdict
from pathlib import Path

from flake8.api import legacy as flake8

from dump import dump
from harness import checkout_repo, files_in_patch, get_dataset, lint
from report import load_predictions
from swebench_docker.constants import MAP_REPO_TO_TEST_FRAMEWORK
from swebench_docker.run_docker import run_docker_evaluation
from swebench_docker.utils import get_instances, get_test_directives


def lint_pycompile(fname):
    try:
        py_compile.compile(fname, doraise=True)
        return
    except py_compile.PyCompileError as err:
        return err.msg


# lint("lint.py")
# sys.exit()

dnames = sys.argv[1:]
preds = load_predictions(dnames)

dataset = get_dataset()

items = list(preds.items())
random.shuffle(items)

num = 0
before_errors = 0
after_errors = 0

for inst, pred in items:
    entry = dataset[inst]
    git_tempdir = checkout_repo(entry)
    model_patch = pred["model_patch"]
    if not model_patch:
        continue

    fname = files_in_patch(model_patch)[0]
    dump(fname)

    fname = Path(git_tempdir) / fname

    num += 1

    errors = lint(fname)
    if errors:
        dump(errors)
        before_errors += 1

    patch_fname = tempfile.NamedTemporaryFile().name
    Path(patch_fname).write_text(model_patch)

    cmd = f"git -C {git_tempdir} apply {patch_fname}"
    subprocess.run(cmd.split(), check=True)

    errors = lint(fname)
    if errors:
        dump(errors)
        after_errors += 1

    dump(num)
    dump(before_errors)
    dump(after_errors)

    pct_after_errors = after_errors / num * 100
    dump(pct_after_errors)
