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

NOOP_PATCH = '''diff --git a/empty.file.{nonce}.ignore b/empty.file.{nonce}.ignore
new file mode 100644
index 0000000..e69de29
'''



def test_prediction(prediction):
    instance_id = prediction["instance_id"]
    dump(instance_id)

    dataset = get_dataset()

    task = dataset[instance_id]

    test_type = MAP_REPO_TO_TEST_FRAMEWORK[task["repo"]]
    test_directives = get_test_directives(task)
    test_cmd = f"{test_type} {' '.join(test_directives)}"

    #test_cmd = './tests/runtests.py --verbosity 3 test_utils.tests'
    dump(test_cmd)

    task_instance = {
        "repo": task["repo"],
        "version": task["version"],
        "base_commit": task["base_commit"],
        "instance_id": prediction["instance_id"],
        "model_name_or_path": prediction["model_name_or_path"],
        "model_patch": NOOP_PATCH.format(nonce="model_patch"), # prediction["model_patch"],
        "test_patch": NOOP_PATCH.format(nonce="test_patch"), # task['test_patch']
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

    model = prediction["model_name_or_path"]
    log_fname = Path(log_dir) / f'{instance_id}.{model}.eval.log'

    dump(log_fname)

    log_text = log_fname.read_text()
    log_lines = log_text.splitlines()
    log_lines = [l for l in log_lines if l.startswith(">>>>")]
    print('\n'.join(log_lines))



pred_path = "predictions/oracle-openrouter--anthropic--claude-3-opus.jsonl"
predictions = [json.loads(line) for line in open(pred_path)]

#iid = "sympy__sympy-12236"
#prediction = [p for p in predictions if p['instance_id'] == iid][0]
#assert prediction['model_patch']

iid = 'sphinx-doc__sphinx-8474'
for prediction in predictions:
    #if iid and prediction['instance_id'] != iid:
    #    continue
    if prediction['model_patch']:
        test_prediction(prediction)
