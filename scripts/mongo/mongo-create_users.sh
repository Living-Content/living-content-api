#!/bin/bash
set -e

log() {
  echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $1"
}

get_secret() {
  local secret_name=$1
  
  # Check if the secret is available as a Docker secret file
  if [[ -f "./secrets/$secret_name" ]]; then
    cat "./secrets/$secret_name"
  else
    # Fallback to environment variable if the file does not exist
    eval echo "\$$secret_name"
  fi
}

MONGO_ROOT_PASSWORD=$(get_secret "mongo_root_password")
MONGO_RW_PASSWORD=$(get_secret "mongo_rw_password")
MONGO_ROOT_USERNAME=$(get_secret "mongo_root_username")
MONGO_RW_USERNAME=$(get_secret "mongo_rw_username")
MONGO_HOST="${MONGO_HOST}"
MONGO_PORT="${MONGO_PORT}"
MONGO_DB_NAME="${MONGO_DB_NAME}"
SSL_CA_CRT="${SSL_CA_CRT}"
SHARED_SSL_PEM="${SHARED_SSL_PEM}"

log "Creating MongoDB users..."

# Confirm SSL certificate files are present
if [[ ! -f "${SSL_CA_CRT}" ]]; then
  log "SSL CA file ${SSL_CA_CRT} is missing. Exiting..."
  exit 1
fi

if [[ ! -f "${SHARED_SSL_PEM}" ]]; then
  log "SSL Certificate key file ${SHARED_SSL_PEM} is missing. Exiting..."
  exit 1
fi

# Create the MongoDB root user
mongosh --tls \
  --tlsCAFile "$SSL_CA_CRT" \
  --tlsCertificateKeyFile "$SHARED_SSL_PEM" \
  --host $MONGO_HOST \
  --port $MONGO_PORT \
  <<EOF
use admin;
db.createUser({
  user: '$MONGO_ROOT_USERNAME',
  pwd: '$MONGO_ROOT_PASSWORD',
  roles: [{ role: 'root', db: 'admin' }]
});

use $MONGO_DB_NAME;
db.createUser({
  user: '$MONGO_RW_USERNAME',
  pwd: '$MONGO_RW_PASSWORD',
  roles: [{ role: 'readWrite', db: '$MONGO_DB_NAME' }]
});
EOF

log "MongoDB user created."
