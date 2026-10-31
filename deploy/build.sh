#!/usr/bin/env bash
set -euo pipefail
export FASTEMBED_CACHE_PATH="$PWD/.cache/fastembed"
python -m pip install -r requirements-deploy.txt
python webapp/manage.py collectstatic --noinput
# Cache the existing evidence model in the build, avoiding runtime downloads.
python -c 'from rag.index import embedder; embedder()'
