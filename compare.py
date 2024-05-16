#!/usr/bin/env python

import sys
import json
import asyncio

from pathlib import Path
from collections import defaultdict, Counter

from dump import dump

from swebench_docker.utils import get_instances, get_test_directives
from swebench_docker.run_docker import run_docker_evaluation
from swebench_docker.constants import MAP_REPO_TO_TEST_FRAMEWORK

from harness import get_dataset
from report import load_predictions


dnames = sys.argv[1:]

all_preds = dict()
all_insts = set()

for dname in dnames:
    dump(dname)
    preds = load_predictions([dname])
    all_preds[dname] = preds

    dump(sum(pred['resolved'] for pred in preds.values()))

    all_insts.update(preds.keys())

dump(len(all_insts))

resolvers = []
for inst in all_insts:
    who_resolved = tuple(sorted(
        dname for dname,preds in all_preds.items()
        if preds.get(inst, dict()).get('resolved', False)
    ))
    resolvers.append(who_resolved)
    if len(who_resolved) == 1:
        pred = all_preds[dname][inst]
        #dump(pred)


counts = Counter(resolvers)
for who,cnt in counts.items():
    dump(who, cnt)
