import datetime
import json
from pathlib import Path

from datasets import load_dataset

from dump import dump  # noqa: F401

FULL_DATASET = "princeton-nlp/SWE-bench"
FULL_DATASET_FNAME = FULL_DATASET.replace("/", "--") + ".json"

LITE_DATASET = "princeton-nlp/SWE-bench_Lite"
LITE_DATASET_FNAME = LITE_DATASET.replace("/", "--") + ".json"


def dump_dataset(dataset, fname):
    """
    Save the dataset to json.
    """
    entries = list(dataset)
    for entry in entries:
        entry["FAIL_TO_PASS"] = json.loads(entry["FAIL_TO_PASS"])
        entry["PASS_TO_PASS"] = json.loads(entry["PASS_TO_PASS"])

    with open(fname, "w") as f:
        json.dump(entries, f, indent=4)


def get_full_dataset():
    return get_dataset(FULL_DATASET, FULL_DATASET_FNAME)


def get_lite_dataset():
    return get_dataset(LITE_DATASET, LITE_DATASET_FNAME)


def get_dataset(dataset, fname):
    """
    Load the `DATASET` from hugging face, and turn it into a dict
    keyed on `instance_id`.
    Cache the dict locally in a json file.
    """

    fname = Path(fname)
    if fname.exists():
        dataset = json.loads(fname.read_text())
    else:
        dataset = load_dataset(dataset)
        dataset = dataset["test"]
        dump_dataset(dataset, fname)

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


def old(fname):
    fname = Path(fname)
    assert fname.exists(), fname

    old_dname = fname.parent / "OLD"
    old_dname.mkdir(exist_ok=True)

    now = datetime.datetime.today()
    now = now.strftime("%y%m%d-%H%M%S")
    to = old_dname / f"{fname.name}.{now}"

    print(to, fname)

    fname.rename(to)
