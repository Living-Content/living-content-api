# Living Content API

A Dockerized FastAPI application that enables interaction with various Living Content functions.

[Documentation](docs/README.md)

## Overview

### Features

- Configurable queries
- LLM-based function selection
- User management
- Session management
- Authorization management
- Direct API interaction
- Managed API interaction
- Fully Dockerized deployment

### Deployed Environments

- API (`api`)
- MongoDB (`mongo`) for long-term storage
- Redis (`redis`) for short-term storage

### Plugins

#### Generative Audio

- JENAI client for audio creation and song extension

#### Generative Imagery

- Midjourney via APIFRAME client

#### Plugins In Development

- LLAMA client for General Queries (via LivePeer)
- Flux.1 client for generative imagery (via LivePeer)

### Query Handlers

- OpenAI client

#### Query Handlers In Development

- LLAMA client (via LivePeer)

### Function Handlers

- OpenAI client

#### Function Handlers In Development

- LLAMA client (via LivePeer)

## Quick Start

A quick-start script will be implemented.

For detailed setup instructions, see the [Installation Guide](docs/installation.md).

## Contributing

Our Git workflow and contribution guidelines are as follows:

### Branch Structure

Our project uses the following branch structure:

- `main` - The primary branch containing production-ready code
- `develop` - The integration branch for features in development
- `feature/*` - Feature branches for new functionality
- `bugfix/*` - Branches for bug fixes
- `hotfix/*` - Emergency fixes for production issues
- `release/*` - Release preparation branches

### Git Workflow

1. **Fork the Repository**
   - Fork the repository to your GitHub account
   - Clone your fork locally: `git clone https://github.com/living-content/living-content-api`

2. **Create a Branch**
   - For new features:

     ```bash
     git checkout develop
     git checkout -b feature/your-feature-name
     ```

   - For bug fixes:

     ```bash
     git checkout develop
     git checkout -b bugfix/issue-description
     ```

   - For hotfixes:

     ```bash
     git checkout main
     git checkout -b hotfix/critical-fix
     ```

3. **Development Process**
   - Make your changes in the branch
   - Keep commits atomic and write meaningful commit messages
   - Follow the project's code style and conventions
   - Add tests for new functionality
   - Update documentation as needed

4. **Stay Updated**

   ```bash
   git remote add upstream https://github.com/original/repository
   git fetch upstream
   git rebase upstream/develop  # For feature/bugfix branches
   ```

5. **Submit Changes**
   - Push your branch to your fork
   - Create a Pull Request (PR) against the appropriate branch:
     - Features/bugfixes -> `develop`
     - Hotfixes -> `main`

### Pull Request Guidelines

1. **PR Title and Description**
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe the changes and their impact
   - Include any necessary migration steps

2. **Code Quality**
   - Follow code style guidelines
   - Remove debug statements and commented code

3. **Review Process**
   - Address reviewer feedback
   - Keep the PR focused and manageable in size
   - Rebase and resolve conflicts as needed

### Release Process

1. Release branches are created from `develop` as:

   ```bash
   git checkout -b release/v1.2.3 develop
   ```

2. Only bug fixes and release preparations are allowed in release branches

3. Once ready, the release branch is merged into both `main` and `develop`:

   ```bash
   git checkout main
   git merge --no-ff release/v1.2.3
   git tag -a v1.2.3
   git checkout develop
   git merge --no-ff release/v1.2.3
   ```

### Additional Guidelines

1. **Commit Messages**
   - Write descriptive commit messages in the imperative mood
   - Format: `type: brief description`
   - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

2. **Documentation**
   - Update README.md if needed
   - Document new features or changes in behavior
   - Include inline documentation for complex code

3. **Testing**
   - Help us get unit testing underway!

### Questions or Issues?

- Check existing issues before creating new ones
- Use issue templates when available
- Email <hello@livingcontent.co> for help

Thank you for contributing!
