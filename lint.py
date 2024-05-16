#!/usr/bin/env python

import sys
import json
import asyncio
import py_compile
import tempfile
import subprocess
import random
import traceback

from pathlib import Path
from collections import defaultdict, Counter

from dump import dump

from swebench_docker.utils import get_instances, get_test_directives
from swebench_docker.run_docker import run_docker_evaluation
from swebench_docker.constants import MAP_REPO_TO_TEST_FRAMEWORK

from harness import get_dataset, files_in_patch, checkout_repo
from report import load_predictions

from flake8.api import legacy as flake8

def lint_pycompile(fname):
    try:
        py_compile.compile(fname, doraise=True)
        return
    except py_compile.PyCompileError as err:
        return err.msg

def lint_flake8(fname):
    style_guide = flake8.get_style_guide()
    report = style_guide.check_files([fname])
    
    errors = []
    for error in report.get_statistics('E'):
        line_number = int(error.split(':')[1])
        with open(fname, 'r') as file:
            lines = file.readlines()
            error_line = lines[line_number - 1].strip()
            surrounding_lines = lines[max(0, line_number - 3):min(len(lines), line_number + 2)]
            formatted_error = f"Error on line {line_number}:\n"
            formatted_error += "\n".join([f"{i+1}: {line.strip()}" for i, line in enumerate(surrounding_lines)])
            errors.append(formatted_error)
    return "\n\n".join(errors)

foo()

dnames = sys.argv[1:]
preds = load_predictions(dnames)

dataset = get_dataset()

items = list(preds.items())
random.shuffle(items)

num = 0
before_errors = 0
after_errors = 0

for inst,pred in items:
    entry = dataset[inst]
    git_tempdir = checkout_repo(entry)
    model_patch = pred['model_patch']
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

    #commit = entry['base_commit']
    #diff_cmd = f"git -C {git_tempdir} diff {commit}"
    #diff_output = subprocess.check_output(diff_cmd.split()).decode()

    dump(num)
    dump(before_errors)
    dump(after_errors)

    pct_after_errors = after_errors / num * 100
    dump(pct_after_errors)
