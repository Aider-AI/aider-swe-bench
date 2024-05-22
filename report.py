#!/usr/bin/env python

import json
import os
import random
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from swebench.metrics.report import get_model_report

from dump import dump
from harness import get_dataset
from tests import run_tests


def run_evals(swe_bench_tasks, log_dir, predictions_jsonl):
    base = os.getcwd()

    run_evals_cmd = f"""
python {base}/SWE-bench-docker/run_evaluation.py
    --log_dir {base}/{log_dir}
    --swe_bench_tasks {base}/{swe_bench_tasks}
    --skip_existing
    --predictions_path {predictions_jsonl}
"""
    run_evals_cmd = " ".join([line.strip() for line in run_evals_cmd.split() if line.strip()])
    subprocess.run(run_evals_cmd.split(), check=True)


def get_report(swe_bench_tasks, log_dir, predictions_jsonl, model_name_or_path):
    try:
        report = get_model_report(
            model_name_or_path,
            predictions_jsonl,
            swe_bench_tasks,
            log_dir,
            verbose=True,
        )
    except KeyError:
        report = dict()

    # for k, v in report.items():
    #    print(f"- {k}: {len(v)}")

    # dump(report)

    generated = set(report["generated"])
    applied = set(report["applied"])
    missing = generated - applied
    dump(missing)

    return report


def update_pred_json(predictions, report):
    all_instances = set(report.get("generated", []))
    all_instances.update(set(report.get("no_generation", [])))

    for instance_id, pred in predictions.items():
        if "resolved" in pred:
            continue

        assert instance_id in all_instances, instance_id

        pred["resolved"] = instance_id in report["resolved"]
        save = dict(pred)
        del save["json_fname"]
        Path(pred["json_fname"]).write_text(json.dumps(save, indent=4))


def load_predictions(paths):
    prediction_paths = []
    for path in paths:
        path = Path(path)
        if path.is_file():
            prediction_paths.append(path)
        elif path.is_dir():
            prediction_paths += list(path.glob("*.json"))
        else:
            assert False, path

    prediction_paths.sort(key=lambda p: p.stat().st_mtime)

    predictions = dict()
    for fname in prediction_paths:
        pred = json.loads(fname.read_text())
        inst = pred["instance_id"]
        pred["json_fname"] = str(fname)
        predictions[inst] = pred

    return predictions


def main():
    dname = Path(sys.argv[1])
    predictions = load_predictions([dname])
    if not predictions:
        print("No predictions")
        return

    dump(len(predictions))

    predictions_jsonl = tempfile.NamedTemporaryFile(suffix=".jsonl").name
    with open(predictions_jsonl, "w") as fh:
        for inst, pred in predictions.items():
            fh.write(json.dumps(pred) + "\n")

    # use the last pred to get model_name_or_path
    model_name_or_path = pred["model_name_or_path"]
    swe_bench_tasks = "princeton-nlp--SWE-bench_Lite.json"
    log_dir = Path("logs") / dname.name
    log_dir.mkdir(exist_ok=True)
    dump(log_dir)

    any_need_evals = any("resolved" not in pred for pred in predictions.values())
    any_need_evals = True
    if any_need_evals:
        run_evals(swe_bench_tasks, str(log_dir), predictions_jsonl)

    report = get_report(swe_bench_tasks, str(log_dir), predictions_jsonl, model_name_or_path)

    if any_need_evals:
        update_pred_json(predictions, report)

    counts = defaultdict(int, [(k, len(v)) for k, v in report.items()])
    dump(counts)

    total = counts["generated"] + counts["no_generation"]
    dump(total)
    missing_logs = total - counts["with_logs"]
    dump(missing_logs)

    if total:
        percent = counts["resolved"] * 100 / total
        print(f"{percent= :.1f}%")

        plus_one_percent = (counts["resolved"] + 1) * 100 / (total + 1)
        print(f"{plus_one_percent= :.1f}%")

    print()

    # NEED TO BE RUN?
    need_to_be_run = missing_logs - counts["no_generation"]
    if need_to_be_run:
        dump(need_to_be_run)

        should_count = total - need_to_be_run
        dump(should_count)

        percent_of_should = counts["resolved"] * 100 / should_count
        print(f"{percent_of_should=:.1f}")

    # COSTS
    costs = []
    for data in predictions.values():
        cost = data.get("cost")
        if cost is not None and cost > 0:
            costs.append(cost)

    if len(costs):
        recent = costs[-5:]
        recent = [f"{c:.2f}" for c in recent]
        print("recent costs:", ", ".join(recent))
        avg_cost = sum(costs) / len(costs)
        print(f"avg_cost: ${avg_cost:.2f}/instance")

        spent = sum(costs)
        print(f"spent: ${spent:.2f}")

        num_instances = len(json.load(open(swe_bench_tasks)))
        expected_cost = num_instances * avg_cost
        print(f"expected_cost: ${expected_cost:.2f}")

        print()

    # added gold files?

    total_with_gold_attr = 0
    total_added_gold = 0
    gold_resolved = 0

    added_timeline = ""
    repomap_timeline = ""
    timeline = ""
    for instance_id, data in predictions.items():
        gold_files = set(data.get("gold_files", []))
        added_files = set(data.get("added_files", []))

        resolved = data["resolved"]
        added_gold = (added_files.intersection(gold_files) == gold_files) and gold_files

        if added_files:
            added_timeline += str(len(added_files))
        else:
            added_timeline += "_"

        if gold_files:
            total_with_gold_attr += 1
        if added_gold:
            total_added_gold += 1

        if not gold_files and not resolved:
            timeline += "."
        elif added_gold and resolved:
            timeline += "R"
            gold_resolved += 1
        elif added_gold and not resolved:
            timeline += "g"
        elif not added_gold and not resolved:
            timeline += "_"
        elif not added_gold and resolved:
            timeline += "!"
            # print(data['instance_id'])

        if data.get("initial_map_has_gold_file") or data.get("map_has_gold_file"):
            repomap_timeline += "M"
        else:
            repomap_timeline += "_"

    pct_maps_with_gold_file = len(repomap_timeline.replace("_", "")) / len(repomap_timeline) * 100
    dump(pct_maps_with_gold_file)

    dump(total_with_gold_attr)
    dump(total_added_gold)
    if total_with_gold_attr:
        pct_added = total_added_gold / total_with_gold_attr * 100
        print(f"pct_added_gold: {pct_added:.1f}%")

        pct_added_gold_resolved = gold_resolved / total_added_gold * 100
        print(f"pct_added_gold_resolved: {pct_added_gold_resolved:.1f}%")

        print()

    print(timeline)
    print(added_timeline)
    print(repomap_timeline)

    # stats_on_tests_before_and_after(report, predictions.values())


def stats_on_tests_before_and_after(report, predictions):
    num = 0
    num_before_pass = 0
    num_pass_to_fail = 0

    dataset = get_dataset()

    random.shuffle(predictions)

    outcomes = defaultdict(int)
    for pred in predictions:
        instance_id = pred["instance_id"]

        # if instance_id not in has_patch_not_resolved:
        #    continue

        num += 1

        entry = dataset[instance_id]
        before_passed, _ = run_tests(entry)
        if not before_passed:
            continue

        after_passed, _ = run_tests(entry, model_patch=pred["model_patch"])

        resolved = instance_id in report["resolved"]
        dump(before_passed, after_passed, resolved)
        outcome = (before_passed, after_passed, resolved)
        outcomes[outcome] += 1
        dump(sorted(outcomes.items()))

        if before_passed:
            num_before_pass += 1
        if before_passed and not after_passed:
            num_pass_to_fail += 1

        print()
        dump(num)
        dump(num_before_pass)
        dump(num_pass_to_fail)

        pct_before_pass = num_before_pass / num * 100
        dump(pct_before_pass)
        pct_pass_to_fail = num_pass_to_fail / num_before_pass * 100
        dump(pct_pass_to_fail)

        print()


if __name__ == "__main__":
    status = main()
    sys.exit(status)
