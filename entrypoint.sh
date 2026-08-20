#!/bin/sh
set -e

python <<'PYEOF'
import time
from sqlalchemy.exc import OperationalError
from app import app, db

with app.app_context():
    for attempt in range(30):
        try:
            db.create_all()
            break
        except OperationalError:
            time.sleep(1)
    else:
        raise SystemExit("Database never became available")
PYEOF

exec "$@"
