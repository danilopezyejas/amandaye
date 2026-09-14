#!/bin/sh
set -eu

# Schema migrations require an explicit operator command and a backup.
# WhiteNoise collects assets only when starting the production WSGI server.
if [ "${1:-}" = "gunicorn" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
