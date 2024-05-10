#!/bin/bash

set -e

docker build \
       --file Dockerfile \
       -t swe-bench \
       .
