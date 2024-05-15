#!/bin/bash

# exit when any command fails
set -e

source .venv/bin/activate

DIR=/Users/gauthier/Projects/swe-bench

cd $DIR/SWE-bench-docker

LOGDIR=`basename $1`
echo $LOGDIR

JSONL=$DIR/${1}.jsonl
cp /dev/null $JSONL
echo $JSONL

for file in $DIR/$1/*.json; do
    echo $file
    cat $file | python3 -m json.tool --no-indent >> $JSONL
done

python ./run_evaluation.py \
       --log_dir $DIR/logs \
       --swe_bench_tasks $DIR/princeton-nlp--SWE-bench_Lite.json \
       --skip_existing \
       --predictions_path $JSONL \
       || true

cd $DIR

./report.py $JSONL | tee tmp.evalreport.txt

rsync -az tmp.evalreport.txt chunder.net:www/chunder.net/tmp.evalreport.txt

