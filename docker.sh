#!/bin/bash

docker run \
       -it --rm \
       -v `pwd`:/app \
       -v `pwd`/repos/.:/repos \
       -e HISTFILE=/app/.bash_history \
       swe-bench \
       bash
