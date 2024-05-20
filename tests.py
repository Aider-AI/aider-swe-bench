#!/usr/bin/env python

import asyncio
import sys
import tempfile
from pathlib import Path

from dump import dump
from swebench_docker.constants import MAP_REPO_TO_TEST_FRAMEWORK
from swebench_docker.run_docker import run_docker_evaluation
from swebench_docker.utils import get_test_directives

NOOP_PATCH = (
    "diff --git a/empty.file.{nonce}.ignore b/empty.file.{nonce}.ignore\n"
    "new file mode 100644\n"
    "index 0000000..e69de29\n"
)


def run_tests(entry, model_patch=None, use_new_tests=False,
              model_name_or_path="none"):
    instance_id = entry["instance_id"]
    dump(instance_id)

    test_type = MAP_REPO_TO_TEST_FRAMEWORK[entry["repo"]]
    test_directives = get_test_directives(entry)
    test_cmd = f"{test_type} {' '.join(test_directives)}"

    dump(test_cmd)

    if not model_patch:
        model_patch = NOOP_PATCH.format(nonce="model_patch")

    if use_new_tests:
        test_patch = entry["test_patch"]
    else:
        test_patch = NOOP_PATCH.format(nonce="test_patch")

    entry_instance = {
        "repo": entry["repo"],
        "version": entry["version"],
        "base_commit": entry["base_commit"],
        "instance_id": entry["instance_id"],
        "model_name_or_path": model_name_or_path,
        "model_patch": model_patch,
        "test_patch": test_patch,
        "test_directives": test_directives,
        "test_cmd": test_cmd,
    }

    namespace = "aorwall"
    log_dir = tempfile.TemporaryDirectory(dir="/tmp").name
    timeout = 60
    log_suffix = ""

    dump(log_dir)

    asyncio.run(run_docker_evaluation(entry_instance, namespace, log_dir,
                                      timeout, log_suffix))

    log_fname = Path(log_dir) / f"{instance_id}.{model_name_or_path}.eval.log"

    log_text = log_fname.read_text()
    log_lines = log_text.splitlines()
    log_lines = [line for line in log_lines if line.startswith(">>>>")]
    print("\n".join(log_lines))

    passed = ">>>>> All Tests Passed" in log_text

    return passed, log_text


def main():
    from harness import get_dataset

    dataset = get_dataset()

    num = 0
    num_passed = 0

    instance_ids = sys.argv[1:]

    for entry in dataset.values():
        if instance_ids and entry["instance_id"] not in instance_ids:
            continue

        passed, test_text = run_tests(entry)

        num += 1
        if passed:
            num_passed += 1

        dump(num_passed / num)


if __name__ == "__main__":
    status = main()
    sys.exit(status)
