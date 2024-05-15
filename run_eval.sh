#!/bin/bash

# exit when any command fails
set -e

source .venv/bin/activate

BASE=/Users/gauthier/Projects/swe-bench

cd $BASE/SWE-bench-docker

PREDS_DIR=${1%/}

LOGDIR=`basename $PREDS_DIR`
echo $LOGDIR

JSONL=$BASE/${1}.jsonl
cp /dev/null $JSONL
echo $JSONL

for file in `ls -1tr $BASE/$PREDS_DIR/*.json`; do
    #echo $file
    cat $file | python3 -m json.tool --no-indent >> $JSONL
done

python ./run_evaluation.py \
       --log_dir $BASE/logs \
       --swe_bench_tasks $BASE/princeton-nlp--SWE-bench_Lite.json \
       --skip_existing \
       --predictions_path $JSONL \
       || true

cd $BASE

./report.py $JSONL | tee tmp.evalreport.txt

rsync -az tmp.evalreport.txt chunder.net:www/chunder.net/tmp.evalreport.txt

