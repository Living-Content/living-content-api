# CLI Tool Documentation

## lc.sh - Command-Line Tool

### Docker Commands

- `docker:build`  
  Build Docker images.  
  **Usage:** `./lc.sh docker:build [--nocache]`

- `docker:down`  
  Stop and remove Docker containers.  
  **Usage:** `./lc.sh docker:down`

- `docker:logs`  
  View Docker logs.  
  **Usage:** `./lc.sh docker:logs`

- `docker:rebuild`  
  Rebuild and restart Docker containers.  
  **Usage:** `./lc.sh docker:rebuild`

- `docker:up`  
  Start Docker containers.  
  **Usage:** `./lc.sh docker:up`

### Environment Management

- `env:generate`  
  Generate `.env` from `config.yaml`.  
  **Usage:** `./lc.sh env:generate [--force]`

- `env:set`  
  Set the environment.  
  **Usage:** `./lc.sh env:set <development|staging|production>`

### Initialization Commands

- `init:all`  
  Run initial setup.  
  **Usage:** `./lc.sh init:all [--force]`

- `init:config`  
  Initialize configuration templates.  
  **Usage:** `./lc.sh init:config --env=<development|staging|production|all> [--force]`

- `init:deployment`  
  Initialize deployment templates.  
  **Usage:** `./lc.sh init:deployment --env=<staging|production|all> [--force]`

### Other Commands

- `secrets:generate`: Generate secrets
- `ssl:generate`: Generate SSL certificates
- `venv:activate`: Show virtual environment activation
- `venv:create`: Create virtual environment
- `install:dependencies`: Install project dependencies
- `log:clean`: Clean log file

### Global Options

- `--force`: Force overwrite
- `--log`: Enable logging
- `--verbose`: Verbose mode
- `--env=<environment>`: Override environment
- `--nocache`: Build without cache
  