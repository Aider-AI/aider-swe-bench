#!/bin/bash

# exit when any command fails
set -e

cd /Users/gauthier/Projects/swe-bench/SWE-bench-docker

source .venv/bin/activate

DIR=/Users/gauthier/Projects/swe-bench


python ./run_evaluation.py \
       --log_dir $DIR/logs \
       --swe_bench_tasks $DIR/dataset.json \
       --skip_existing \
       --predictions_path $DIR/$1

