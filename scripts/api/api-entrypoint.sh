#!/bin/sh

# Base command to run gunicorn
CMD="./venv/bin/gunicorn main:app \
  --workers $WORKERS \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --worker-tmp-dir /tmp"

# Conditionally append SSL options if ENV is 'development'
if [ "$ENV" = "development" ]; then
  echo "Running in development mode: Using self-signed SSL..."
  CMD="$CMD --keyfile $API_SSL_KEY --certfile $API_SSL_PEM"
else
  echo "Running in $ENV mode: SSL is handled externally."
fi

# Echo the full command for debugging purposes
echo "Running command: $CMD"

# Execute the command
exec $CMD