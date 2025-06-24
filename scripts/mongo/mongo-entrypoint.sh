#!/bin/bash
set -e

MONGO_DB_SETUP_SCRIPT="/living-content-mongo/mongo-db_setup.py"
MONGO_CREATE_USERS_SCRIPT="/living-content-mongo/mongo-create_users.sh"

log() {
  echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting MongoDB entrypoint script..."

# Confirm SSL certificate files are present
if [[ ! -f "${SSL_CA_CRT}" ]]; then
  log "SSL CA file ${SSL_CA_CRT} is missing. Exiting..."
  exit 1
fi

if [[ ! -f "${SHARED_SSL_PEM}" ]]; then
  log "SSL Certificate key file ${SHARED_SSL_PEM} is missing. Exiting..."
  exit 1
fi

log "SSL certificates confirmed to be present."

log "Starting MongoDB..."

# Start MongoDB logging to stdout
mongod \
  --bind_ip_all \
  --port 27017 \
  --tlsCAFile "${SSL_CA_CRT}" \
  --tlsCertificateKeyFile "${SHARED_SSL_PEM}" \
  --tlsMode requireTLS \
  --dbpath /data/db &
mongod_pid=$!

log "Starting User Creation..."

log "Waiting for MongoDB to complete startup..."
sleep 10

# Wait for MongoDB to start
for i in {1..10}; do
  if mongosh --tls \
      --tlsCAFile "${SSL_CA_CRT}" \
      --tlsCertificateKeyFile  "${SHARED_SSL_PEM}" \
      --eval "print(\"Attempting test connection via mongosh.\")"; then
    log "MongoDB is up. Proceeding with user creation..."
    # Run user creation script
    if bash "$MONGO_CREATE_USERS_SCRIPT"; then
      log "User creation script completed successfully."
      break
    else
      log "User creation script failed."
      exit 1
    fi
  else
    log "Waiting for MongoDB connection..."
    sleep 5
  fi

  if [ $i -eq 10 ]; then
    log "MongoDB did not start after 10 attempts. Exiting..."
    exit 1
  fi
done

log "Running the initialization script..."
if python3 -u "$MONGO_DB_SETUP_SCRIPT"; then
  log "Initialization script completed successfully."
else
  log "Initialization script failed."
  exit 1
fi

log "MongoDB is ready."

# Keep the container running
wait $mongod_pid