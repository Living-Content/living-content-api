#!/usr/bin/env bash

# lc.sh - A command-line tool to manage the Living Content project.

# This script provides commands to:
# - Create and manage Python virtual environments
# - Install project dependencies
# - Generate .env files from env.yaml
# - Build, start, stop, and rebuild Docker containers
# - Perform the initial setup of the project
# - View Docker logs
# - Clean log files
# - Set the environment
# - Start the main application along with necessary databases and scripts

LOGGING=false
FORCE=false
VERBOSE=false
NO_CACHE=""

# Load ENV from .env file if it exists
if [ -f .env ]; then
    ENV=$(awk -F '=' '/^ENV=/ {print $2}' .env)
fi
# If ENV is not set in .env, default to "production"
ENV=${ENV:-production}

# Define colors
LIGHT_BLUE='\033[1;34m'
DARK_BLUE='\033[38;5;33m'
DARK_GREY='\033[1;30m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Spinner function
spinner() {
    local pid=$1
    local delay=0.05
    local spinstr='|/-\'
    tput civis # hide cursor
    while kill -0 $pid 2>/dev/null; do
        for i in $(seq 0 $((${#spinstr}-1))); do
            printf "${WHITE}[ %c ]${NC}\b\b\b\b\b" "${spinstr:$i:1}"
            sleep $delay
        done
    done
    printf "      \b\b\b\b\b" # clear spinner
    tput cnorm # show cursor
}

# Convert ENV to lowercase
ENV=$(echo "$ENV" | tr '[:upper:]' '[:lower:]')

# Validate ENV
if [[ "$ENV" != "development" && "$ENV" != "production" && "$ENV" != "staging" ]]; then
    echo -e "${RED}Invalid ENV: $ENV. Defaulting to production.${NC}"
    ENV="production"
fi

run_orchestrator() {
    local cmd="python scripts/orchestrator.py $1"
    shift

    # Add global options
    if [ -n "$ENV" ]; then
        cmd="$cmd --env=$ENV"
    fi
    if $LOGGING; then
        cmd="$cmd --log"
    fi
    if $VERBOSE; then
        cmd="$cmd --verbose"
    fi
    if [ -n "$NO_CACHE" ]; then
        cmd="$cmd --nocache"
    fi
    if $FORCE; then
        cmd="$cmd --force"
    fi

    # Add remaining arguments
    for arg in "$@"; do
        cmd="$cmd $arg"
    done

    printf "\n${LIGHT_BLUE}Starting command: $cmd${NC}\n"

    # Spinner characters and initialization
    local spin_chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local spin_index=0
    local spinner_pid=""

    # Function to start the spinner
    start_spinner() {
        while true; do
            printf "\r[${spin_chars:spin_index:1}]"
            spin_index=$(( (spin_index + 1) % ${#spin_chars} ))
            sleep 0.1
        done
    }

    # Function to hide the spinner output
    hide_spinner() {
        if [ -n "$spinner_pid" ]; then
            kill -STOP "$spinner_pid" >/dev/null 2>&1
            printf "\r%*s\r" $((${#spin_chars} + 2)) ""  # Clear the spinner
        fi
    }

    # Function to show the spinner output
    show_spinner() {
        if [ -n "$spinner_pid" ]; then
            kill -CONT "$spinner_pid" >/dev/null 2>&1
        fi
    }

    # Function to stop the spinner and clear it
    stop_spinner() {
        if [ -n "$spinner_pid" ]; then
            kill "$spinner_pid" >/dev/null 2>&1
            wait "$spinner_pid" 2>/dev/null
            spinner_pid=""
            printf "\r%*s\r" $((${#spin_chars} + 2)) ""  # Clear the spinner
        fi
    }

    # Function to handle interrupt signal (Ctrl+C)
    interrupt_handler() {
        stop_spinner
        printf "\n${RED}[✗] $cmd interrupted by user.${NC}\n"
        exit 130
    }

    # Set up trap to handle interrupt signal
    trap 'interrupt_handler' INT

    # Start the spinner once
    start_spinner &
    spinner_pid=$!

    # Execute the command and capture both stdout and stderr
    eval $cmd 2>&1 | while IFS= read -r line; do
        # Hide the spinner to handle output
        hide_spinner
        if [[ "$line" == "Running command-line operation:"* ]] || [[ "$line" == "Running internal function:"* ]]; then
            printf "\n${WHITE}%s${NC}\n" "$line"
        elif [[ "$line" == *"%"* ]] && [[ "$line" == *"."* ]]; then
            # Progress output, skip printing
            continue
        elif [[ "$line" == "(Reading database "* ]]; then
            # Skip "Reading database ..." lines
            continue
        else
            printf "${DARK_GREY}%s${NC}\n" "$line"
        fi
        # Show the spinner again
        show_spinner
    done

    local exit_code=${PIPESTATUS[0]}

    # Stop the spinner at the end of the command
    stop_spinner

    if [ $exit_code -eq 2 ]; then
        printf "\n${YELLOW}[!] Warning: $cmd completed with warnings.${NC}\n"
    elif [ $exit_code -ne 0 ]; then
        printf "\n${RED}[✗] $cmd failed.${NC}\n"
    else
        printf "\n${GREEN}[✓] $cmd succeeded.${NC}\n"
    fi

    # Ensure all background processes are terminated
    trap - INT
    kill -9 $(jobs -p) >/dev/null 2>&1

    return $exit_code
}

# Define help function
show_help() {
    echo "lc.sh - A command-line tool to manage the Living Content project."
    echo
    echo "Usage: $0 {command} [options]"
    echo
    echo "Commands:"
    echo "  docker:build            Builds Docker images."
    echo "                          Usage: $0 docker:build [--nocache] [--service <service_name>] [--project_name <project_name>] [--google_artifact_registry <registry_url>]"
    echo
    echo "                          --nocache                  Disable the Docker build cache."
    echo "                          --service                  Specify the name of the service to build (default=all)."
    echo "                          --project_name             The project name for tagging Docker images (default=.env)."
    echo "                          --google_artifact_registry The Google Artifact Registry (default=.env)."
    echo
    echo "  docker:down             Stops and removes Docker containers."
    echo "                          Usage: $0 docker:down"
    echo
    echo "  docker:logs             Views logs of Docker containers."
    echo "                          Usage: $0 docker:logs"
    echo
    echo "  docker:rebuild          Rebuilds and restarts Docker containers."
    echo "                          Usage: $0 docker:rebuild"
    echo
    echo "  docker:up               Starts Docker containers in detached mode."
    echo "                          Usage: $0 docker:up"
    echo
    echo "  env:generate            Generates './.env' from config.yaml"
    echo "                          Usage: $0 env:generate [--force]"
    echo
    echo "  env:set                 Sets and persists the environment to development, staging, or production."
    echo "                          Usage: $0 env:set <development|staging|production>"
    echo
    echo "  help                    Shows this help message."
    echo "                          Usage: $0 help"
    echo
    echo "  init:all                Runs the initial setup, including creating a virtual environment,"
    echo "                          installing dependencies, generating .env file, setting up Docker containers,"
    echo "                          and generating SSL certificates."
    echo "                          Usage: $0 init:all"
    echo
    echo "  init:config             Initializes the configuration templates."
    echo "                          Usage: $0 init:config --env=<development|staging|production|all> [--force]"
    echo 
    echo "  init:deployment         Initializes the deployment templates."
    echo "                          Usage: $0 init:deployment --env=<staging|production|all [--force]>"
    echo
    echo "  install:dependencies    Installs project dependencies."
    echo "                          Usage: $0 install:dependencies"
    echo
    echo "  log:clean               Cleans the log file 'lc.log'."
    echo "                          Usage: $0 log:clean"
    echo
    echo "  ssl:generate            Generates self-signed SSL certificates."
    echo "                          Usage: $0 ssl:generate"
    echo
    echo "  secrets:generate        Generates secrets for the project."
    echo "                          Usage: $0 init:secrets"
    echo
    echo "  secrets:push            Pushes secrets to Kubernetes."
    echo "                          Usage: $0 secrets:push"
    echo 
    echo "  venv:activate           Shows instructions to activate the Python virtual environment."
    echo "                          Usage: $0 venv:activate"
    echo
    echo "  venv:create             Creates a Python virtual environment."
    echo "                          Usage: $0 venv:create"
    echo
    echo "Options:"
    echo "  --force                 Force overwrite of configuration files"
    echo "  --log                   Enables logging of output to lc.log."
    echo "  --verbose               Enables verbose mode to print extra details."
    echo "  --env=environment       Temporarily override environment; env=<development|staging|production>."
}

# Define short help function
show_short_help() {
    echo "lc.sh - A command-line tool to manage the Living Content project."
    echo
    echo "Available commands:"
    echo "  docker:build            Build Docker images"
    echo "  docker:down             Stop and remove Docker containers"
    echo "  docker:logs             View Docker logs"
    echo "  docker:rebuild          Rebuild and restart Docker containers"
    echo "  docker:up               Start Docker containers"
    echo "  env:generate            Generates './.env' from config.yaml"
    echo "  env:set                 Set the environment"
    echo "  init:all                Run initial setup"
    echo "  init:config             Initializes the configuration templates."
    echo "  init:deployment         Initializes the deployment templates."
    echo "  install:dependencies    Install project dependencies"
    echo "  log:clean               Clean the log file 'lc.log'"
    echo "  secrets:generate        Generates secrets for the project"
    echo "  secrets:push            Push secrets to Kubernetes"
    echo "  ssl:generate            Generate SSL certificates"
    echo "  venv:activate           Show how to activate the virtual environment"
    echo "  venv:create             Create a Python virtual environment"
    echo
    echo "Global Options:"
    echo "  --force                 Force overwrite of configuration files"
    echo "  --log                   Enables logging of output to lc.log"
    echo "  --verbose               Enables verbose mode to print extra details"
    echo "  --env=environment       Temporarily override environment; env=<development|staging|production>"
    echo "  --nocache               Build Docker images without using cache"
}

# Error handling function
handle_error() {
    echo "Error: $1"
    exit 1
}

# Ensure necessary files and directories exist
[ ! -d "scripts" ] && handle_error "scripts directory not found"
[ ! -f "scripts/orchestrator.py" ] && handle_error "scripts/orchestrator.py not found"
[ ! -d "config" ] && handle_error "config directory not found"

# Parse options
ARGS=()
for arg in "$@"; do
  case $arg in
    --log)
      LOGGING=true
      ;;
    --verbose)
      VERBOSE=true
      ;;
    --force)
      FORCE=true
      ;;
    --env=*)
      ENV="${arg#*=}"
      ;;
    --nocache)
      NO_CACHE="--no-cache"
      ;;
    *)
      ARGS+=("$arg")
      ;;
  esac
done

# Ensure at least one argument (the command) is provided
if [ ${#ARGS[@]} -eq 0 ]; then
    show_short_help
    exit 1
fi

COMMAND="${ARGS[0]}"
unset "ARGS[0]"
ARGS=("${ARGS[@]}")

case $COMMAND in
    docker:down)
        echo -e "${DARK_BLUE}Stopping Docker containers...${NC}"
        run_orchestrator docker:down "${ARGS[@]}"
        ;;
    docker:logs)
        echo -e "${DARK_BLUE}Viewing Docker logs...${NC}"
        run_orchestrator docker:logs "${ARGS[@]}"
        ;;
    docker:build)
        echo -e "${DARK_BLUE}Building Docker images...${NC}"
        run_orchestrator docker:build "${ARGS[@]}"
        ;;
    docker:rebuild)
        echo -e "${DARK_BLUE}Rebuilding and restarting Docker containers...${NC}"
        run_orchestrator docker:rebuild "${ARGS[@]}"
        ;;
    docker:up)
        echo -e "${DARK_BLUE}Starting Docker containers...${NC}"
        run_orchestrator docker:up "${ARGS[@]}"
        ;;
    env:set)
        echo -e "${DARK_BLUE}Establishing environment...${NC}"
        run_orchestrator env:set "${ARGS[@]}"
        ;;
    env:generate)
        echo -e "${DARK_BLUE}Generating .env file...${NC}"
        run_orchestrator env:generate "${ARGS[@]}"
        ;;
    help)
        show_help
        ;;
    install:dependencies)
        echo -e "${DARK_BLUE}Installing dependencies...${NC}"
        run_orchestrator install:dependencies "${ARGS[@]}"
        ;;
    log:clean)
        echo -e "${DARK_BLUE}Cleaning log file 'lc.log'...${NC}"
        run_orchestrator log:clean "${ARGS[@]}"
        ;;
    init:all)
        echo -e "${DARK_BLUE}Running initial setup...${NC}"
        run_orchestrator init:all "${ARGS[@]}"
        ;;
    init:config)
        echo -e "${DARK_BLUE}Initializing configuration files...${NC}"
        run_orchestrator init:config "${ARGS[@]}"
        ;;
    init:deployment)
        echo -e "${DARK_BLUE}Initializing deployment files...${NC}"
        run_orchestrator init:deployment "${ARGS[@]}"
        ;;
    secrets:generate)
        echo -e "${DARK_BLUE}Initializing secrets...${NC}"
        run_orchestrator secrets:generate "${ARGS[@]}"
        ;;
    secrets:push)
        echo -e "${DARK_BLUE}Pushing secrets to Kubernetes...${NC}"
        run_orchestrator secrets:push "${ARGS[@]}"
        ;;
    ssl:generate)
        echo -e "${DARK_BLUE}Setting up development SSL certificates...${NC}"
        run_orchestrator ssl:generate "${ARGS[@]}"
        ;;
    venv:create)
        echo -e "${DARK_BLUE}Creating virtual environment...${NC}"
        run_orchestrator venv:create "${ARGS[@]}"
        ;;
    venv:activate)
        echo -e "${DARK_BLUE}To activate the virtual environment, run:${NC}"
        echo "source venv/bin/activate"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_short_help
        exit 1
        ;;
esac