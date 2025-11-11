# Petstore Domain Example

This directory contains a complete example domain implementation using the Marty Microservices Framework (MMF). This demonstrates how to build a business domain using the framework's unified configuration, services, and plugin systems.

## Structure

```
petstore_domain/
├── README.md                    # This file
├── plugins/                     # Plugin configurations for the domain
│   ├── marty.yaml              # Marty Trust PKI plugin configuration
│   └── production_payment_service.yaml  # Payment service plugin configuration
├── services/                    # Service implementations (to be added)
├── config/                      # Domain-specific configuration
└── docs/                        # Domain documentation
```

## Plugin Configuration

The `plugins/` directory contains configurations for plugins used in this domain:

### marty.yaml

Configuration for the Marty Trust PKI plugin, demonstrating:

- Trust anchor and PKD integration
- Document signing services
- Certificate management
- Security configurations
- MMF database integration

### production_payment_service.yaml

Configuration for a production payment service plugin, demonstrating:

- Payment provider integration (Stripe)
- Fraud detection settings
- Audit logging
- Security and rate limiting
- Database requirements

## Plugin Configuration Loading

These plugin configurations demonstrate the MMF plugin configuration loading strategy:

1. **Plugin Discovery**: Plugins are discovered in the `plugins/` directory
2. **Configuration Loading**: Plugin configs are loaded hierarchically with environment overrides
3. **Dependency Resolution**: Plugin dependencies are resolved automatically
4. **Service Integration**: Plugins integrate with MMF's unified configuration system

## Usage

This example demonstrates:

- How to structure a business domain using MMF
- Plugin configuration patterns
- Integration with MMF's unified systems
- Best practices for domain organization

## Framework Integration

The plugin configurations use MMF's unified configuration system features:

- Secret references with `${SECRET:key}` syntax
- Environment-specific overrides
- Database integration patterns
- Security configuration inheritance
- Monitoring and observability integration
