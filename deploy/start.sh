#!/usr/bin/env bash
set -euo pipefail
export FASTEMBED_CACHE_PATH="$PWD/.cache/fastembed"
python webapp/manage.py bootstrap_demo
exec gunicorn --chdir webapp ibdsite.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 1 \
  --timeout 180 --access-logfile - --error-logfile -
