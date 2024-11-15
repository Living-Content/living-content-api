# Deployment

## Local Development

### Environment Setup

```bash
./lc.sh env:set --env=development
```

### Build

```bash
./lc.sh docker:build
```

### Run

```bash
./lc.sh docker:up
```

## Docker Deployment

### Container Structure

- API (`api`)
- MongoDB (`mongo`)
- Redis (`redis`)

### Build Options

- Standard build: `./lc.sh docker:build`
- No cache: `./lc.sh docker:build --nocache`
- Verbose: `./lc.sh docker:build --verbose`

### Container Management

- Start: `./lc.sh docker:up`
- Stop: `./lc.sh docker:down`
- Logs: `./lc.sh docker:logs`
- Rebuild: `./lc.sh docker:rebuild`

## Environment-Specific Deployment

### Development

- Local machine deployment
- Self-signed SSL certificates
- Development-specific configuration

### Staging

- Pre-production environment
- Testing configuration
- Staging-specific settings

### Production

- Production environment
- Production SSL certificates
- Production-specific configuration
