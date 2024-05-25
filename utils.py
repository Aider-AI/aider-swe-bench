import json
from pathlib import Path

from datasets import load_dataset

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

    return predictions


def is_plausible(pred):
    attrs = "model_patch edit_outcome lint_outcome test_outcome".split()
    for attr in attrs:
        if not pred[attr]:
            return
    return True


def get_plausible(preds):
    return set(inst for inst, pred in preds.items() if is_plausible(pred))
