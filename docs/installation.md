# Installation Guide

## First Run

### Clone The Repository

```bash
git clone <repository_url>
cd <repository_directory>
```

### Create & Activate A Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### Install requirements

Obtain EQTY credentials from <hello@livingcontent.co>.

```bash
pip install --no-cache-dir -r requirements/requirements.txt \
  --extra-index-url http://{EQTY_TRUSTED_HOST_USERNAME}:{EQTY_TRUSTED_HOST_PASSWORD}@{EQTY_TRUSTED_HOST_DOMAIN}/simple/ \
  --trusted-host {EQTY_TRUSTED_HOST_DOMAIN} \
```

### Configure The Application

Configuration is handled by YAML files for development, production, and staging environments.

1. Initialize the project:

   ```bash
   ./lc.sh init:all
   ```

2. Edit configuration files:
   - Update `.yaml` files in `/config`
   - Configure `ingress.yaml` with environment URLs
   - Set `api_host_url` for each environment

**Note:** Use `init:all --force` to reset configuration to defaults.

### Create Secrets

1. Edit `secrets.yaml` files in `/secrets`
2. Generate encrypted secrets:

```bash
./lc.sh secrets:generate
```

### Set Your Environment

Your development environment should be: `development`, `staging`, or `production`.

Generate your `.env` file:

```bash
./lc.sh env:set --env=<environment>
```

### SSL Certificate Setup

1. Generate certificates:

   ```bash
   ./lc.sh ssl:generate
   ```

2. Install Certificate Authority:

   #### macOS

   1. Open Keychain Access
   2. Drop `./ssl/ca/ca.crt` into "System" keychain
   3. Set trust to "Always Trust"

   #### Windows

   1. Open MMC (Win + R, type "mmc")
   2. Add Certificates snap-in
   3. Import CA to "Trusted Root Certification Authorities"

   #### Linux

   Follow distribution-specific instructions for trusted certificates.
