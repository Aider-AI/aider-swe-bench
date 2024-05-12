#!/usr/bin/env python

import sys
import json
import asyncio

from pathlib import Path
from collections import defaultdict

from dump import dump

from swebench_docker.utils import get_instances, get_test_directives
from swebench_docker.run_docker import run_docker_evaluation
from swebench_docker.constants import MAP_REPO_TO_TEST_FRAMEWORK

from harness import get_dataset



def test_prediction(prediction):
    instance_id = prediction["instance_id"]
    dump(instance_id)

    dataset = get_dataset()

    task = dataset[instance_id]

    test_type = MAP_REPO_TO_TEST_FRAMEWORK[task["repo"]]
    test_directives = get_test_directives(task)
    test_cmd = f"{test_type} {' '.join(test_directives)}"

    noop_test_patch = '''diff --git a/emptyfile2.txt b/emptyfile2.txt
new file mode 100644
index 0000000..e69de29
'''

    task_instance = {
        "repo": task["repo"],
        "version": task["version"],
        "base_commit": task["base_commit"],
        "instance_id": prediction["instance_id"],
        "model_name_or_path": prediction["model_name_or_path"],
        "model_patch": prediction["model_patch"],
        "test_patch": patch,
        "test_directives": test_directives,
        "test_cmd": test_cmd
    }

    namespace = "aorwall"
    log_dir = "/Users/gauthier/Projects/swe-bench/test-logs"
    timeout = 60
    log_suffix = ""

    asyncio.run(
        run_docker_evaluation(task_instance, namespace, log_dir, timeout, log_suffix)
    )



pred_path = "predictions/oracle-openrouter--anthropic--claude-3-opus.jsonl"
predictions = [json.loads(line) for line in open(pred_path)]

iid = "sympy__sympy-12236"

prediction = [p for p in predictions if p['instance_id'] == iid][0]

assert prediction['model_patch']

test_prediction(prediction)
