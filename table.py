#!/usr/bin/env python

import random
import sys
from collections import Counter, defaultdict

from dump import dump
from report import load_predictions

dnames = sys.argv[1:]
preds = load_predictions(dnames)

# dataset = get_dataset()

items = list(preds.items())
random.shuffle(items)

dump(len(items))

name = {
    "gpt-4o": "Aider with GPT-4o",
    "openrouter/anthropic/claude-3-opus": "Aider with Opus",
    "n/a": "Aider with GPT-4o",
}

proposed = []
correct = []

model_proposed = defaultdict(int)
model_correct = defaultdict(int)

for inst, pred in items:
    resolved = pred["resolved"]
    model = pred.get("model", "n/a")
    attempt = pred["try"]

    model = name[model]

    key = (attempt, model)
    proposed.append(key)
    model_proposed[model] += 1
    if resolved:
        correct.append(key)
        model_correct[model] += 1


num_proposed = len(proposed)
dump(num_proposed)
num_correct = len(correct)
dump(num_correct)

counts_proposed = Counter(proposed)
counts_correct = Counter(correct)
num = 0
for key, count_p in sorted(counts_proposed.items()):
    count_c = counts_correct[key]
    num += 1
    attempt, model = key
    pct_p = count_p * 100 / num_proposed
    pct_c = count_c * 100 / num_correct
    pct_of_all = count_c / 3
    print(
        f"| {num} | {model:20} | {count_p:3d} | {pct_p:4.1f}% | {count_c:2d} | {pct_c:4.1f}% |"
        f" {pct_of_all:4.1f}% | "
    )

pct_of_all = num_correct / 3

print(
    f"| **Total** | | **{num_proposed}** | **100%** | **{num_correct}** | **100%** |"
    f" **{pct_of_all:4.1f}%** | "
)
print()

for model in sorted(model_proposed.keys()):
    count_p = model_proposed[model]
    count_c = model_correct[model]
    pct = count_c * 100 / count_p
    print(f"| {model:20} | {count_p:3d} | {count_c:2d} |{pct:4.1f}% |")

pct = num_correct * 100 / num_proposed
print(f"| **Total** | **{num_proposed}** | **{num_correct}** |**{pct:4.1f}%** |")
