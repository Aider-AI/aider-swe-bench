#!/bin/bash

# exit when any command fails
set -e

source .venv/bin/activate

DIR=/Users/gauthier/Projects/swe-bench

cd $DIR/SWE-bench-docker

python ./run_evaluation.py \
       --log_dir $DIR/logs \
       --swe_bench_tasks $DIR/princeton-nlp--SWE-bench_Lite.json \
       --skip_existing \
       --predictions_path $DIR/$1

cd $DIR

./report.py $DIR/$1 | tee tmp.evalreport.txt

rsync -az tmp.evalreport.txt chunder.net:www/chunder.net/tmp.evalreport.txt

