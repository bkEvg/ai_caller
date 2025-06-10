#!/bin/sh
echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting app..."
exec python3 -m app.main