#!/bin/bash

# exit when any command fails
set -e

# strip the trailing /
PREDS_DIR=${1%/}

./report.py $PREDS_DIR | tee tmp.evalreport.txt

rsync -az tmp.evalreport.txt chunder.net:www/chunder.net/tmp.evalreport.txt

