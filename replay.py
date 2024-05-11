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


def main():
    fnames = sys.argv[1:]
    for fname in fnames:
        doit(fname)

def doit(fname):
    text = Path(fname).read_text()
    if 'InvalidEditBlock' not in text:
        return

    dump(fname)
    messages = utils.split_chat_history_markdown(text, include_tool=True)
    utils.show_messages(messages)


if __name__ == '__main__':
    status = main()
    sys.exit(status)
