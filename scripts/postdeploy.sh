#!/usr/bin/env bash
set -euo pipefail

# Run migrations and collectstatic after deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
