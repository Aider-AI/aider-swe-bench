FROM python:3.11
RUN apt-get update
RUN apt-get install -y less git build-essential

# https://github.com/princeton-nlp/SWE-bench
COPY SWE-bench /app/SWE-bench
RUN conda env create -f /app/SWE-bench/environment.yml

WORKDIR /app
