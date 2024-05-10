FROM continuumio/anaconda3
RUN apt-get update
RUN apt-get install -y less git build-essential

# https://github.com/princeton-nlp/SWE-bench
COPY SWE-bench /SWE-bench
RUN conda env create -f /SWE-bench/environment.yml

WORKDIR /app
