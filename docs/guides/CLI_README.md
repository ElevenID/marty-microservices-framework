# Marty CLI Documentation

The Marty CLI is a powerful command-line interface for creating, managing, and deploying microservices using the Marty Microservices Framework.

## Installation

### From PyPI (Recommended)

```bash
pip install marty-msf
```

### From Source

```bash
git clone https://github.com/ElevenID/marty-microservices-framework.git
cd marty-microservices-framework
pip install -e .
```

## Quick Start

### 1. Create a New Service

```bash
# Create a basic FastAPI service
marty new fastapi-service my-user-service

# Create with options
marty new fastapi-service my-user-service \
  --author "Your Name" \
  --email "you@example.com" \
  --description "User management service"
```

### 2. Explore Available Templates

```bash
# List all available templates
marty templates

# Get detailed template information
marty templates fastapi-service
```

### 3. Build and Run Your Service

```bash
cd my-user-service

# Build the service
marty build

# Run tests
marty test

# Start the service locally
marty run

# Deploy to Kubernetes
marty deploy
```

## Available Templates

### Core Services

- **`fastapi-service`** - Basic FastAPI microservice with monitoring
- **`api-gateway-service`** - API Gateway with routing, rate limiting, and security
- **`config-service`** - Centralized configuration management service
- **`saga-orchestrator`** - Distributed transaction coordinator

### Infrastructure

- **`service-discovery`** - Service registry and discovery system
- **`api-versioning`** - API versioning and contract testing framework

## CLI Commands

### `marty new`

Create a new microservice from a template.

```bash
marty new <template> <name> [OPTIONS]

Options:
  --path PATH              Project directory (default: current directory)
  --author TEXT           Author name
  --email TEXT            Author email
  --description TEXT      Project description
  --port INTEGER          Service port (default: 8000)
  --interactive          Use interactive mode for configuration
  --skip-git             Skip git repository initialization
  --skip-venv            Skip virtual environment creation
```

### `marty templates`

List and explore available templates.

```bash
marty templates [TEMPLATE_NAME]

# Examples:
marty templates                    # List all templates
marty templates fastapi-service    # Show template details
marty templates --category service # Filter by category
```

### `marty build`

Build the current project.

```bash
marty build [OPTIONS]

Options:
  --docker              Build Docker image
  --push                Push to registry (with --docker)
  --tag TEXT            Docker image tag
  --no-cache            Don't use Docker cache
```

### `marty test`

Run tests for the current project.

```bash
marty test [OPTIONS]

Options:
  --unit                Run unit tests only
  --integration         Run integration tests only
  --coverage            Generate coverage report
  --watch               Watch for changes and re-run tests
```

### `marty run`

Run the current project locally.

```bash
marty run [OPTIONS]

Options:
  --port INTEGER        Override service port
  --env TEXT            Environment file to load
  --debug               Enable debug mode
  --reload              Enable auto-reload on changes
```

### `marty deploy`

Deploy the current project.

```bash
marty deploy [OPTIONS]

Options:
  --environment TEXT    Target environment (dev/staging/prod)
  --namespace TEXT      Kubernetes namespace
  --dry-run            Show what would be deployed
  --wait               Wait for deployment to complete
```

### `marty info`

Show information about the current project.

```bash
marty info [OPTIONS]

Options:
  --dependencies        Show dependency information
  --config              Show configuration
  --status              Show service status
```

### `marty config`

Manage CLI configuration.

```bash
marty config [OPTIONS]

Options:
  --author TEXT         Set default author
  --email TEXT          Set default email
  --registry TEXT       Set default Docker registry
  --show                Show current configuration
  --reset               Reset to defaults
```

## Project Structure

When you create a new service, Marty generates a complete project structure:

```
my-service/
├── marty.toml              # Project configuration
├── pyproject.toml          # Python package configuration
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── docker-compose.yml     # Local development environment
├── README.md              # Project documentation
├── src/
│   └── my_service/
│       ├── __init__.py
│       ├── main.py        # Main application entry point
│       ├── api/           # API routes and handlers
│       ├── models/        # Data models
│       ├── services/      # Business logic
│       └── config.py      # Configuration management
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Pytest configuration
│   ├── test_api.py        # API tests
│   └── test_services.py   # Service tests
├── k8s/
│   ├── deployment.yaml    # Kubernetes deployment
│   ├── service.yaml       # Kubernetes service
│   └── configmap.yaml     # Configuration
└── docs/
    └── api.md             # API documentation
```

## Configuration

### Project Configuration (`marty.toml`)

```toml
[project]
name = "my-service"
version = "1.0.0"
description = "My microservice"
author = "Your Name"
email = "you@example.com"

[service]
port = 8000
framework = "fastapi"
template = "fastapi-service"

[build]
docker_registry = "your-registry.com"
docker_namespace = "example"

[deployment]
environments = ["development", "staging", "production"]
default_environment = "development"
```

### CLI Configuration

The CLI stores user preferences in `~/.marty/config.toml`:

```toml
[user]
author = "Your Name"
email = "you@example.com"

[defaults]
docker_registry = "your-registry.com"
docker_namespace = "example"
kubernetes_namespace = "default"
```

## Environment Variables

The CLI respects the following environment variables:

- `MARTY_FRAMEWORK_PATH` - Custom framework installation path
- `MARTY_CONFIG_PATH` - Custom configuration file path
- `MARTY_TEMPLATES_PATH` - Additional template directories
- `DOCKER_REGISTRY` - Default Docker registry
- `KUBERNETES_NAMESPACE` - Default Kubernetes namespace

## Integration with IDEs

### VS Code

Install the Marty extension for enhanced support:

1. Auto-completion for `marty.toml` files
2. Template snippets
3. Integrated terminal commands
4. Service debugging support

### PyCharm

Configure PyCharm to recognize Marty projects:

1. Mark `src/` as sources root
2. Set up run configurations for `marty run`
3. Configure test runner for `marty test`

## Troubleshooting

### Common Issues

1. **Template not found**

   ```bash
   marty templates  # Check available templates
   ```

2. **Permission denied**

   ```bash
   sudo chown -R $USER ~/.marty/  # Fix permissions
   ```

3. **Docker build fails**

   ```bash
   marty build --no-cache  # Clear Docker cache
   ```

4. **Service won't start**

   ```bash
   marty info --status     # Check service status
   marty run --debug       # Enable debug mode
   ```

### Debug Mode

Enable verbose logging:

```bash
export MARTY_DEBUG=1
marty --verbose <command>
```

### Getting Help

```bash
marty --help              # General help
marty <command> --help    # Command-specific help
```

## Contributing

### Adding New Templates

1. Create template directory in `templates/`
2. Add `template.yaml` with metadata
3. Create template files with Jinja2 placeholders
4. Test with `marty new your-template test-project`

### Template Variables

Templates can use these built-in variables:

- `{{project_name}}` - Human-readable project name
- `{{project_slug}}` - URL-safe project identifier
- `{{project_snake}}` - Snake_case identifier
- `{{project_pascal}}` - PascalCase identifier
- `{{project_kebab}}` - kebab-case identifier
- `{{author}}` - Author name
- `{{email}}` - Author email
- `{{description}}` - Project description
- `{{service_port}}` - Service port number
- `{{framework_version}}` - Marty framework version

### Custom Filters

Available Jinja2 filters:

- `{{text|slug}}` - Convert to URL-safe slug
- `{{text|snake}}` - Convert to snake_case
- `{{text|pascal}}` - Convert to PascalCase
- `{{text|kebab}}` - Convert to kebab-case

## Support

- **Documentation**: [https://marty-msf.readthedocs.io](https://marty-msf.readthedocs.io)
- **Issues**: [https://github.com/ElevenID/marty-microservices-framework/issues](https://github.com/ElevenID/marty-microservices-framework/issues)
- **Discussions**: [https://github.com/ElevenID/marty-microservices-framework/discussions](https://github.com/ElevenID/marty-microservices-framework/discussions)
- **Community**: use the repository Discussions forum for public questions.
