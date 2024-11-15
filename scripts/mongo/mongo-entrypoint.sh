#!/bin/bash
set -e

LOG_DIR="/living-content-mongo/logs"
MONGO_DB_SETUP_SCRIPT="/living-content-mongo/mongo-db_setup.py"
MONGO_CREATE_USERS_SCRIPT="/living-content-mongo/mongo-create_users.sh"
MONGOSH_LOGFILE="$LOG_DIR/mongosh_output.log"

LOGFILE="$LOG_DIR/entrypoint.log"

log() {
  echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOGFILE
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

# Start MongoDB and capture all output to the log file
mongod \
  --bind_ip_all \
  --port 27017 \
  --tlsCAFile "${SSL_CA_CRT}" \
  --tlsCertificateKeyFile "${SHARED_SSL_PEM}" \
  --tlsMode requireTLS \
  --dbpath /data/db \
  --logpath "$LOG_DIR/mongod.log" \
  --logappend \
  > $LOGFILE 2>&1 &
mongod_pid=$!

log "Starting User Creation..."

# Ensure the mongosh output log file is created if not already present
if [[ ! -f "$MONGOSH_LOGFILE" ]]; then
  touch "$MONGOSH_LOGFILE"
  log "Created mongosh output log file at $MONGOSH_LOGFILE."
fi

log "Waiting for MongoDB to complete startup..."
sleep 10

# Wait for MongoDB to start
for i in {1..10}; do
  if mongosh --tls \
      --tlsCAFile "${SSL_CA_CRT}" \
      --tlsCertificateKeyFile  "${SHARED_SSL_PEM}" \
      --eval "print(\"Attempting test connection via mongosh.\")" > $MONGOSH_LOGFILE 2>&1; then
    log "MongoDB is up. Proceeding with user creation..."
    # Run user creation script
    if bash "$MONGO_CREATE_USERS_SCRIPT" >> $LOGFILE 2>&1; then
      log "User creation script completed successfully."
      break
    else
      log "User creation script failed. Details:"
      cat "$LOGFILE"
      exit 1
    fi
  else
    cat "$MONGOSH_LOGFILE"
  fi

  if [ $i -eq 10 ]; then
    log "MongoDB did not start after 10 attempts. Exiting..."
    exit 1
  fi
done

log "Running the initialization script..."
if python3 -u "$MONGO_DB_SETUP_SCRIPT" 2>&1 | tee -a $LOGFILE; then
  log "Initialization script completed successfully."
else
  log "Initialization script failed:"
  cat "$LOGFILE"
  exit 1
fi

log "MongoDB is ready."

# Keep the container running
wait $mongod_pid