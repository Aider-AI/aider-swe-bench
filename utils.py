import json
from pathlib import Path

from datasets import load_dataset

from dump import dump  # noqa: F401

# DATASET = "princeton-nlp/SWE-bench_Lite"
DATASET = "princeton-nlp/SWE-bench"

DATASET_FNAME = DATASET.replace("/", "--") + ".json"


def dump_dataset(dataset):
    """
    Save the dataset to json.
    """
    entries = list(dataset)
    for entry in entries:
        entry["FAIL_TO_PASS"] = json.loads(entry["FAIL_TO_PASS"])
        entry["PASS_TO_PASS"] = json.loads(entry["PASS_TO_PASS"])

    with open(DATASET_FNAME, "w") as f:
        json.dump(entries, f, indent=4)


def get_dataset():
    """
    Load the `DATASET` from hugging face, and turn it into a dict
    keyed on `instance_id`.
    Cache the dict locally in a json file.
    """

    fname = Path(DATASET_FNAME)
    if fname.exists():
        dataset = json.loads(fname.read_text())
    else:
        dataset = load_dataset(DATASET)
        dataset = dataset["test"]
        dump_dataset(dataset)

    res = dict()
    for entry in dataset:
        res[entry["instance_id"]] = entry

    return res


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
        if "instance_id" not in pred:
            print("Skipping json without instance_id", fname)
            continue

        inst = pred["instance_id"]
        pred["json_fname"] = str(fname)
        predictions[inst] = pred

    ###
    predictions = filter_preds_by_devin(predictions)

    return predictions


def is_plausible(pred):
    attrs = "model_patch edit_outcome lint_outcome test_outcome".split()
    for attr in attrs:
        if not pred[attr]:
            return
    return True


def get_plausible(preds):
    return set(inst for inst, pred in preds.items() if is_plausible(pred))


def check_criteria(pred, criteria):
    attrs = criteria.split()
    for attr in attrs:
        if not pred[attr]:
            return False
    return True


def pick_winner(results):
    """
    Given that we didn't obtain a result with all good outcomes,
    try a series of weaker outcome sets to find the strongest result.
    """
    priority = (
        "model_patch edit_outcome lint_outcome test_outcome",  # all good!
        "model_patch edit_outcome lint_outcome",  # all good but test_outcome
        "model_patch lint_outcome",  # a patch that lints?
        "model_patch edit_outcome",  # a patch that had no edit errors?
        "model_patch",  # anything with an actual patch!
    )

    # choose the best result available
    for criteria in priority:
        for res in results:
            if check_criteria(res, criteria):
                return res

    # choose the first result as a last resort
    if results:
        return results[0]


def get_devin_instance_ids():
    dname = Path("devin-swebench-results/output_diffs")

    ids = [fname for fname in dname.glob("*/*.txt")]

    suffix = "-diff.txt"
    for iid in ids:
        assert iid.name.endswith(suffix)

    ids = set(iid.name[: -len(suffix)] for iid in ids)

    print("devin ids", len(ids))
    return ids


def filter_preds_by_devin(predictions):
    devin_insts = get_devin_instance_ids()
    predictions = dict((inst, pred) for (inst, pred) in predictions.items() if inst in devin_insts)
    return predictions
