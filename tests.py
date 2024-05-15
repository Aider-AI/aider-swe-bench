#!/usr/bin/env python

import sys
import json
import asyncio
import tempfile

from pathlib import Path
from collections import defaultdict

from dump import dump

from swebench_docker.utils import get_instances, get_test_directives
from swebench_docker.run_docker import run_docker_evaluation
from swebench_docker.constants import MAP_REPO_TO_TEST_FRAMEWORK

from harness import get_dataset

NOOP_PATCH = '''diff --git a/empty.file.{nonce}.ignore b/empty.file.{nonce}.ignore
new file mode 100644
index 0000000..e69de29
'''


def run_tests(entry, model_patch = None):
    instance_id = entry["instance_id"]
    dump(instance_id)

    dataset = get_dataset()

    task = dataset[instance_id]

    test_type = MAP_REPO_TO_TEST_FRAMEWORK[task["repo"]]
    test_directives = get_test_directives(task)
    test_cmd = f"{test_type} {' '.join(test_directives)}"

    dump(test_cmd)

    if not model_patch:
        model_patch = NOOP_PATCH.format(nonce="model_patch")

    model_name_or_path = "testing"

    task_instance = {
        "repo": task["repo"],
        "version": task["version"],
        "base_commit": task["base_commit"],
        "instance_id": entry["instance_id"],
        "model_name_or_path": model_name_or_path,
        "model_patch": model_patch,
        "test_patch": NOOP_PATCH.format(nonce="test_patch"), # task['test_patch']
        "test_directives": test_directives,
        "test_cmd": test_cmd
    }

    namespace = "aorwall"
    log_dir = tempfile.TemporaryDirectory(dir="/Users/gauthier/tmp").name
    timeout = 60
    log_suffix = ""

    dump(log_dir)

    asyncio.run(
        run_docker_evaluation(task_instance, namespace, log_dir, timeout, log_suffix)
    )

    log_fname = Path(log_dir) / f'{instance_id}.{model_name_or_path}.eval.log'

    log_text = log_fname.read_text()
    log_lines = log_text.splitlines()
    log_lines = [l for l in log_lines if l.startswith(">>>>")]
    print('\n'.join(log_lines))

    return log_text


dataset = get_dataset()

num = 0
num_passed = 0

for entry in dataset.values():
    test_text = run_tests(entry)
    passed = '>>>>> All Tests Passed' in test_text

    num += 1
    if passed:
        num_passed += 1

    dump(num_passed/num)
