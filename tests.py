#!/usr/bin/env python

import asyncio
import sys
import tempfile
from pathlib import Path

from dump import dump
from swebench_docker.constants import MAP_REPO_TO_TEST_FRAMEWORK, MAP_VERSION_TO_INSTALL
from swebench_docker.run_docker import run_docker_evaluation
from swebench_docker.utils import get_test_directives
from utils import get_dataset, get_devin_instance_ids, load_predictions


# clipped from `run_docker_evaluation()`
def get_docker_image(task_instance: dict, namespace: str = "aorwall"):
    repo_name = task_instance["repo"].replace("/", "_")

    specifications = MAP_VERSION_TO_INSTALL[task_instance["repo"]][task_instance["version"]]
    image_prefix = "swe-bench"

    if specifications.get("instance_image", False):
        docker_image = (
            f"{namespace}/{image_prefix}-{repo_name}-instance:{task_instance['instance_id']}"
        )
    else:
        docker_image = f"{namespace}/{image_prefix}-{repo_name}-testbed:{task_instance['version']}"

    return docker_image


# A no-op patch which creates an empty file is used to stand in for
# the `model_patch` and/or `test_patch` when running SWE Bench tests
# without one or both of those patches.
NOOP_PATCH = (
    "diff --git a/empty.file.{nonce}.ignore b/empty.file.{nonce}.ignore\n"
    "new file mode 100644\n"
    "index 0000000..e69de29\n"
)


def remove_patches_to_tests(model_patch):
    """
    Remove any changes to the tests directory from the provided patch.
    This is to ensure that the model_patch does not disturb the repo's
    tests when doing acceptance testing with the `test_patch`.
    """
    lines = model_patch.splitlines(keepends=True)
    filtered_lines = []
    is_tests = False

    for line in lines:
        if line.startswith("diff --git a/"):
            pieces = line.split()
            to = pieces[-1]
            if to.startswith("b/") and (
                "/test/" in to
                or "/tests/" in to
                or "/testing/" in to
                or "/test_" in to
                or "/tox.ini" in to
            ):
                is_tests = True
            else:
                is_tests = False

        if not is_tests:
            filtered_lines.append(line)

    return "".join(filtered_lines)


def run_tests(entry, model_patch=None, use_test_patch=False, model_name_or_path="none"):
    """
    Run tests for the SWE Bench `entry`, optionally applying a `model_patch` first.

    If `use_test_patch` is True, then also apply the `test_patch` to bring in
    the tests which determine if the issue is resolved. So False means
    only run the tests that existed at the `base_commit` and any new/changed
    tests contained in the `model_patch`.

    Optionally specify a `model_name_or_path`, which isn't really used since
    the log_dir for the tests is a temp dir which is discarded.
    """
    instance_id = entry["instance_id"]

    test_type = MAP_REPO_TO_TEST_FRAMEWORK[entry["repo"]]
    test_directives = get_test_directives(entry)
    test_cmd = f"{test_type} {' '.join(test_directives)}"

    # Use a no-op patch if no model_patch is provided
    if not model_patch:
        model_patch = NOOP_PATCH.format(nonce="model_patch")

    # Use a no-op patch if use_test_patch is False
    if use_test_patch:
        test_patch = entry["test_patch"]
    else:
        test_patch = NOOP_PATCH.format(nonce="test_patch")

    if model_patch and use_test_patch:
        # Make sure the model_patch does not disturb the repo's tests
        # when doing acceptance testing with the `test_patch`.
        print("=" * 30)
        print(model_patch)
        model_patch = remove_patches_to_tests(model_patch)
        print("=" * 30)
        print(model_patch)
        print("=" * 30)

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

    asyncio.run(run_docker_evaluation(entry_instance, namespace, log_dir, timeout, log_suffix))

    log_fname = Path(log_dir) / f"{instance_id}.{model_name_or_path}.eval.log"
    if not log_fname.exists():
        return None, ""

    log_text = log_fname.read_text()
    log_lines = log_text.splitlines()
    log_lines = [line for line in log_lines if line.startswith(">>>>")]
    print("\n".join(log_lines))

    passed = ">>>>> All Tests Passed" in log_text

    return passed, log_text


def main_devin():
    dataset = get_dataset()

    instances = get_devin_instance_ids()

    seen = set()
    num = 0
    num_passed = 0
    errors = []
    bad_dockers = []
    for instance_id in instances:
        entry = dataset[instance_id]

        docker_image = get_docker_image(entry)
        if docker_image in seen:
            continue
        seen.add(docker_image)

        dump(instance_id)
        dump(docker_image)

        try:
            passed, test_text = run_tests(
                entry,
                model_patch=None,
                use_test_patch=False,
            )
        except FileNotFoundError as err:
            bad_dockers.append(docker_image)
            errors.append(err)

        num += 1
        if passed:
            num_passed += 1

        dump(num_passed, num)

    for err in errors:
        dump(err)

    dump(bad_dockers)


def main_preds():
    dataset = get_dataset()

    dnames = sys.argv[1:]
    preds = load_predictions(dnames)

    num = 0
    num_passed = 0
    for instance_id, pred in preds.items():
        entry = dataset[instance_id]

        passed, test_text = run_tests(
            entry,
            model_patch=pred["model_patch"],
            use_test_patch=True,
        )

        num += 1
        if passed:
            num_passed += 1

        dump(num_passed, num)


if __name__ == "__main__":
    # status = main_devin()
    status = main_preds()
    sys.exit(status)
