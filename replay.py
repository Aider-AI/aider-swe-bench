#!/usr/bin/env python

import random
import json
import time
import os
import sys
import tempfile

from pathlib import Path
from collections import defaultdict

from datasets import load_dataset

from dump import dump

from aider.io import InputOutput
from aider.coders import Coder
from aider.models import Model
from aider import utils
import harness

def main():

    dataset = harness.get_dataset()

    fnames = sys.argv[1:]
    for fname in fnames:
        doit(dataset, fname)

def doit(dataset, fname):

    fname = Path(fname)
    text = fname.read_text()
    if 'InvalidEditBlock' not in text:
        return

    instance_id = fname.with_suffix("").name
    entry = dataset[instance_id]

    dump(fname)
    dump(instance_id)
    dump(entry)

    messages = utils.split_chat_history_markdown(text, include_tool=True)
    #utils.show_messages(messages)


if __name__ == '__main__':
    status = main()
    sys.exit(status)
