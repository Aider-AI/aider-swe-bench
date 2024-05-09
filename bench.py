#!/usr/bin/env python

import sys

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

dataset = load_dataset("princeton-nlp/SWE-bench_Lite_oracle")
