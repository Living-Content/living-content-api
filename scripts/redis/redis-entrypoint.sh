#!/bin/bash

log() {
  echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOGFILE
}

log "$(pwd)"

# Confirm SSL certificate files are present
if [[ ! -f "${SSL_CA_CRT}" ]]; then
  log "SSL CA file ${SSL_CA_CRT} is missing. Exiting..."
  exit 1
fi

if [[ ! -f "${SHARED_SSL_CRT}" ]]; then
  log "SSL Certificate key file ${SHARED_SSL_CRT} is missing. Exiting..."
  exit 1
fi

if [[ ! -f "${SHARED_SSL_KEY}" ]]; then
  log "SSL Certificate key file ${SHARED_SSL_KEY} is missing. Exiting..."
  exit 1
fi

# Load the Redis password from secrets
REDIS_PASSWORD=$(cat ./secrets/redis_password)

# Run redis-server with SSL enabled
exec redis-server \
    --requirepass "$REDIS_PASSWORD" \
    --tls-cert-file $SHARED_SSL_CRT \
    --tls-key-file $SHARED_SSL_KEY \
    --tls-ca-cert-file $SSL_CA_CRT \
    --tls-port 6379 \
    --port 0