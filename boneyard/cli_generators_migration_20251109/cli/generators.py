#!/usr/bin/env python3
"""
Service and Plugin generators for MMF CLI

Contains generators for creating services and plugins that integrate with MMF infrastructure.
"""

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ..framework.service_mesh import EnhancedServiceMeshManager


class ServiceGenerator:
    """Generates comprehensive services using Jinja2 templates."""

    def __init__(self, templates_dir: Path = None, output_dir: Path = None):
        """Initialize the service generator."""
        # Get the root directory of the project (assuming we're in src/marty_msf/cli)
        project_root = Path(__file__).parent.parent.parent.parent
        self.templates_dir = templates_dir or (project_root / "services")
        self.output_dir = output_dir or (project_root / "plugins")

        # Ensure directories exist
        if not self.templates_dir.exists():
            raise ValueError(f"Templates directory not found: {self.templates_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment if available
        if Environment and FileSystemLoader:
            self.env = Environment(
                loader=FileSystemLoader(self.templates_dir),
                trim_blocks=True,
                lstrip_blocks=True,
                autoescape=True,
            )
        else:
            self.env = None
            print("⚠️  Jinja2 not available, using fallback generation")

    def generate_service(self, service_type: str, service_name: str, **options: Any) -> bool:
        """
        Generate a new service from templates.

        Args:
            service_type: Type of service (grpc, fastapi, hybrid, minimal, production)
            service_name: Name of the service (e.g., "document-validator")
            **options: Additional template variables including service mesh options

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate service type
            valid_types = ["fastapi", "simple-fastapi", "production", "grpc", "hybrid", "minimal"]
            if service_type not in valid_types:
                print(f"Error: Service type must be one of: {valid_types}")
                return False

            # Validate service name
            if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", service_name):
                print("Error: Service name must be lowercase with hyphens (e.g., document-validator)")
                return False

            # Check if service already exists
            service_package = service_name.replace("-", "_")
            service_dir = self.output_dir / service_package
            if service_dir.exists():
                print(f"Error: Service '{service_name}' already exists at {service_dir}")
                return False

            # Prepare template variables
            template_vars = self._prepare_template_vars(service_name, **options)

            # Use Jinja2 templates if available, otherwise fallback
            if self.env:
                return self._generate_with_jinja2(service_type, template_vars)
            else:
                return self._generate_fallback(service_type, template_vars)

        except Exception as e:
            print(f"Error generating service: {e}")
            return False

    def _prepare_template_vars(self, service_name: str, **options: Any) -> dict[str, Any]:
        """Prepare template variables from service name and options."""
        service_package = service_name.replace("-", "_")
        service_class = self._to_class_name(service_name)

        template_vars = {
            "service_name": service_name,
            "service_package": service_package,
            "service_class": service_class,
            "service_description": options.get(
                "description",
                f"{service_class} service for {service_name} functionality",
            ),
            "author": options.get("author", "Marty Development Team"),
            "grpc_port": options.get("grpc_port", 50051),
            "http_port": options.get("http_port", 8080),
            "service_mesh_enabled": options.get("service_mesh", False),
            "service_mesh_type": options.get("service_mesh_type", "istio"),
            "namespace": options.get("namespace", "microservice-framework"),
            "domain": options.get("domain", "framework.local"),
            "package_name": service_package.replace("_", "."),
            "HTTP_PORT": options.get("http_port", 8080),
            "GRPC_PORT": options.get("grpc_port", 50051),
            "NAMESPACE": options.get("namespace", "microservice-framework"),
            "SERVICE_NAME": service_name,
            "PACKAGE_NAME": service_package.replace("_", "."),
            "DOMAIN": options.get("domain", "framework.local"),
        }

        template_vars.update(options)
        return template_vars

    def _to_class_name(self, service_name: str) -> str:
        """Convert service name to PascalCase class name."""
        parts = re.split(r"[-_]", service_name)
        return "".join(part.capitalize() for part in parts if part)

    def _generate_with_jinja2(self, service_type: str, template_vars: dict[str, Any]) -> bool:
        """Generate service using Jinja2 templates."""
        # Determine template directory
        template_mapping = {
            "fastapi": "fastapi/fastapi-service",
            "simple-fastapi": "fastapi/simple-fastapi-service",
            "production": "fastapi/production-service",
            "grpc": "grpc/grpc_service",
            "hybrid": "hybrid/hybrid_service",
            "minimal": "shared/config-service"
        }

        template_subdir = template_mapping.get(service_type)
        if not template_subdir:
            print(f"Error: Unsupported service type: {service_type}")
            return False

        # Generate service files
        self._generate_from_template_dir(template_subdir, template_vars)

        # Generate additional production-ready components
        if service_type == "production":
            self._generate_production_components(template_vars)

        # Generate Kubernetes manifests (skip for simple templates)
        if service_type not in ["simple-fastapi"]:
            self._generate_k8s_manifests(template_vars)

        print(f"✅ Generated {service_type} service: {template_vars['service_name']}")
        print(f"📁 Location: {self.output_dir / template_vars['service_package']}")

        self._print_getting_started_instructions(service_type, template_vars)
        return True

    def _generate_fallback(self, service_type: str, template_vars: dict[str, Any]) -> bool:
        """Generate service using fallback method (minimal FastAPI service)."""
        print("Using fallback generation (install Jinja2 for full template support)")

        # Create basic directory structure
        service_dir = self.output_dir / template_vars["service_package"]
        service_dir.mkdir(parents=True, exist_ok=True)

        # Generate minimal FastAPI service
        self._generate_minimal_fastapi_service(service_dir, template_vars)

        print(f"✅ Generated minimal {service_type} service: {template_vars['service_name']}")
        print(f"📁 Location: {service_dir}")
        return True

    def _generate_minimal_fastapi_service(self, service_dir: Path, template_vars: dict[str, Any]) -> None:
        """Generate a minimal FastAPI service as fallback."""
        # Create directory structure
        (service_dir / "app").mkdir(exist_ok=True)
        (service_dir / "tests").mkdir(exist_ok=True)

        # Generate main.py
        main_content = f'''"""
Main entry point for {template_vars["service_name"]} service.
"""

import uvicorn
from app import create_app

def main():
    """Main entry point for the service."""
    app = create_app()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port={template_vars["http_port"]},
        log_level="info"
    )

if __name__ == "__main__":
    main()
'''
        (service_dir / "main.py").write_text(main_content)

        # Generate app/__init__.py
        app_init_content = f'''"""
FastAPI application factory for {template_vars["service_name"]} service.
"""

from fastapi import FastAPI

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="{template_vars['service_class']} Service",
        description="{template_vars['service_description']}",
        version="1.0.0"
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {{"status": "healthy", "service": "{template_vars['service_name']}"}}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {{"message": "Welcome to {template_vars['service_class']} Service"}}

    return app
'''
        (service_dir / "app" / "__init__.py").write_text(app_init_content)

        # Generate requirements.txt
        requirements_content = '''fastapi>=0.104.0
uvicorn[standard]>=0.24.0
'''
        (service_dir / "requirements.txt").write_text(requirements_content)

        # Generate Dockerfile
        dockerfile_content = f'''FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install uv for faster Python package management
RUN pip install uv

# Copy framework source (when building from framework root)
COPY ./src /app/framework/src
COPY ./pyproject.toml /app/framework/
COPY ./README.md /app/framework/

# Copy plugin/service source
COPY ./{template_vars["service_package"]} /app/plugin

# Install framework as editable dependency
WORKDIR /app/framework
RUN uv pip install --system -e .

# Install service dependencies
WORKDIR /app/plugin
RUN uv pip install --system -r requirements.txt

# Set proper permissions
RUN mkdir -p logs && \\
    chown -R appuser:appuser /app

USER appuser

EXPOSE {template_vars["http_port"]}

CMD ["python", "main.py"]
'''
        (service_dir / "Dockerfile").write_text(dockerfile_content)

        # Generate development scripts
        self._generate_dev_scripts(service_dir, template_vars)

    def _generate_from_template_dir(self, template_subdir: str, template_vars: dict[str, Any]) -> None:
        """Generate files from a template directory."""
        template_dir = self.templates_dir / template_subdir
        if not template_dir.exists():
            raise ValueError(f"Template directory not found: {template_dir}")

        service_dir = self.output_dir / template_vars["service_package"]
        service_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (service_dir / "app").mkdir(exist_ok=True)
        (service_dir / "tests").mkdir(exist_ok=True)

        # Generate files from templates
        for template_file in template_dir.glob("*.j2"):
            self._generate_file(template_file, template_subdir, service_dir, template_vars)

        # Generate development scripts
        self._generate_dev_scripts(service_dir, template_vars)

    def _generate_file(self, template_file: Path, template_subdir: str, service_dir: Path, template_vars: dict[str, Any]) -> None:
        """Generate a single file from template."""
        relative_path = template_file.relative_to(self.templates_dir / template_subdir)

        # File mapping for proper output locations
        file_mapping = {
            "main.py": service_dir / "main.py",
            "config.py": service_dir / "app" / "core" / "config.py",
            "service.py": service_dir / "app" / "services" / f"{template_vars['service_package']}_service.py",
            "routes.py": service_dir / "app" / "api" / "routes.py",
            "models.py": service_dir / "app" / "models" / f"{template_vars['service_package']}_models.py",
            "pyproject.toml": service_dir / "pyproject.toml",
            "Dockerfile": service_dir / "Dockerfile",
            "requirements.txt": service_dir / "requirements.txt",
            "test_service.py": service_dir / "test_service.py",
        }

        # Skip files that should not be generated (middleware is now imported from framework)
        skip_files = {"middleware.py"}

        template_name = relative_path.with_suffix("").name

        # Skip files that shouldn't be generated
        if template_name in skip_files:
            return

        output_path = file_mapping.get(template_name, service_dir / relative_path.with_suffix(""))

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Render template
        template_path = f"{template_subdir}/{relative_path.name}"
        template = self.env.get_template(template_path)
        rendered_content = template.render(**template_vars)

        output_path.write_text(rendered_content, encoding="utf-8")
        print(f"  📝 Generated: {output_path.relative_to(self.output_dir.parent)}")

    def _generate_production_components(self, template_vars: dict[str, Any]) -> None:
        """Generate additional production-ready components."""
        service_dir = self.output_dir / template_vars["service_package"]

        # Create additional directories
        (service_dir / "app" / "models").mkdir(exist_ok=True)
        (service_dir / "app" / "utils").mkdir(exist_ok=True)
        (service_dir / "app" / "middleware").mkdir(exist_ok=True)
        (service_dir / "tests" / "unit").mkdir(exist_ok=True)
        (service_dir / "tests" / "integration").mkdir(exist_ok=True)
        (service_dir / "docs").mkdir(exist_ok=True)

        self._generate_readme(service_dir, template_vars)
        print("  📋 Generated production-ready structure with comprehensive documentation")

    def _generate_readme(self, service_dir: Path, template_vars: dict[str, Any]) -> None:
        """Generate comprehensive README for the service."""
        readme_content = f'''# {template_vars["service_class"]} Service

A production-ready microservice built with the Marty Microservices Framework.

## Quick Start

```bash
# Install dependencies
uv sync

# Run the service
python main.py
```

## API Endpoints

- **Health Check**: `GET /health`
- **API Documentation**: `GET /docs`

## Development

```bash
# Run tests
uv run pytest tests/

# Build Docker image
docker build -t {template_vars["service_name"]}:latest .

# Run container
docker run -p {template_vars["http_port"]}:{template_vars["http_port"]} {template_vars["service_name"]}:latest
```

## Architecture

This service follows the Marty Microservices Framework patterns for production readiness.
'''

        (service_dir / "README.md").write_text(readme_content, encoding="utf-8")

    def _generate_k8s_manifests(self, template_vars: dict[str, Any]) -> None:
        """Generate Kubernetes manifests."""
        service_dir = self.output_dir / template_vars["service_package"]
        k8s_dir = service_dir / "k8s"
        k8s_dir.mkdir(exist_ok=True)

        # Basic deployment manifest
        deployment_content = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {template_vars["service_name"]}
  labels:
    app: {template_vars["service_name"]}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {template_vars["service_name"]}
  template:
    metadata:
      labels:
        app: {template_vars["service_name"]}
    spec:
      containers:
      - name: {template_vars["service_name"]}
        image: {template_vars["service_name"]}:latest
        imagePullPolicy: Never
        ports:
        - containerPort: {template_vars["http_port"]}
        env:
        - name: PORT
          value: "{template_vars["http_port"]}"
        livenessProbe:
          httpGet:
            path: /health
            port: {template_vars["http_port"]}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: {template_vars["http_port"]}
          initialDelaySeconds: 5
          periodSeconds: 5
'''
        (k8s_dir / "deployment.yaml").write_text(deployment_content)

        # Basic service manifest
        service_content = f'''apiVersion: v1
kind: Service
metadata:
  name: {template_vars["service_name"]}-service
  labels:
    app: {template_vars["service_name"]}
spec:
  selector:
    app: {template_vars["service_name"]}
  ports:
  - port: 80
    targetPort: {template_vars["http_port"]}
    protocol: TCP
  type: ClusterIP
'''
        (k8s_dir / "service.yaml").write_text(service_content)

        print(f"  🎛️  Generated Kubernetes manifests in {k8s_dir.relative_to(self.output_dir.parent)}")

    def _print_getting_started_instructions(self, service_type: str, template_vars: dict[str, Any]) -> None:
        """Print getting started instructions based on service type."""
        print("🚀 To get started:")
        print("   1. cd to the service directory")
        print("   2. Install dependencies: uv sync")
        print("   3. Run the service: python main.py")
        print(f"   4. Test health: curl http://localhost:{template_vars['http_port']}/health")
        print(f"   5. View docs: http://localhost:{template_vars['http_port']}/docs")

        if service_type == "production":
            print("   6. Run tests: uv run pytest tests/")
            print("   7. Build for production: docker build -t service:latest .")

    # Legacy compatibility methods
    def generate_plugin(self, name: str) -> bool:
        """Generate a plugin (legacy compatibility)."""
        return self.generate_service("production", name)

    def add_service_to_plugin(self, plugin_dir: str, plugin_name: str, service_name: str, service_type: str = "business", features: list = None) -> bool:
        """Add a new service to existing plugin."""
        if features is None:
            features = []

        # Create service within the plugin's app/services directory
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            print(f"❌ Plugin directory not found: {plugin_dir}")
            return False

        # Ensure app/services directory exists
        services_dir = plugin_path / "app" / "services"
        services_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Generate service implementation file
            service_file = services_dir / f"{service_name.replace('-', '_')}_service.py"
            service_content = self._generate_service_content(service_name, service_type, features)
            service_file.write_text(service_content)

            # Generate service models if database feature is enabled
            if "database" in features:
                models_dir = plugin_path / "app" / "models"
                models_dir.mkdir(parents=True, exist_ok=True)
                models_file = models_dir / f"{service_name.replace('-', '_')}_models.py"
                models_content = self._generate_models_content(service_name)
                models_file.write_text(models_content)

            # Generate/update API routes
            api_dir = plugin_path / "app" / "api"
            api_dir.mkdir(parents=True, exist_ok=True)
            routes_file = api_dir / f"{service_name.replace('-', '_')}_routes.py"
            routes_content = self._generate_routes_content(service_name, features)
            routes_file.write_text(routes_content)

            # Update main.py to include the new service routes
            self._update_main_py_with_service(plugin_path, service_name)

            print(f"✅ Service '{service_name}' added to plugin '{plugin_name}' successfully!")
            print(f"   📁 Service file: app/services/{service_name.replace('-', '_')}_service.py")
            print(f"   📁 Routes file: app/api/{service_name.replace('-', '_')}_routes.py")
            if "database" in features:
                print(f"   📁 Models file: app/models/{service_name.replace('-', '_')}_models.py")
            return True

        except Exception as e:
            print(f"❌ Error creating service: {e}")
            return False

    def _generate_service_content(self, service_name: str, service_type: str, features: list) -> str:
        """Generate service implementation content."""
        return f'''"""
{service_name.title()} Service Implementation

Service Type: {service_type}
Features: {", ".join(features) if features else "none"}
"""
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from pydantic import BaseModel

class {service_name.title().replace("-", "").replace("_", "")}Service:
    """Service implementation for {service_name}."""

    def __init__(self):
        """Initialize the service."""
        pass

    async def get_health(self) -> Dict[str, Any]:
        """Get service health status."""
        return {{
            "status": "healthy",
            "service": "{service_name}",
            "type": "{service_type}",
            "features": {features}
        }}

    async def process_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a service request."""
        # Implement your business logic here
        return {{
            "message": f"Processed by {{self.__class__.__name__}}",
            "data": data,
            "service": "{service_name}"
        }}
'''

    def _generate_models_content(self, service_name: str) -> str:
        """Generate database models content."""
        return f'''"""
Database models for {service_name} service.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class {service_name.title().replace("-", "").replace("_", "")}Model(Base):
    """Database model for {service_name}."""

    __tablename__ = "{service_name.lower().replace("-", "_")}"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
'''

    def _generate_routes_content(self, service_name: str, features: list) -> str:
        """Generate API routes content."""
        service_package = service_name.replace('-', '_')
        service_class = service_name.title().replace("-", "").replace("_", "")
        return f'''"""
API routes for {service_name} service.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from pydantic import BaseModel

router = APIRouter(prefix="/{service_name.replace("_", "-")}", tags=["{service_name}"])

class RequestModel(BaseModel):
    """Request model for {service_name}."""
    data: Dict[str, Any]

class ResponseModel(BaseModel):
    """Response model for {service_name}."""
    message: str
    data: Dict[str, Any]
    service: str

@router.get("/health")
async def get_health():
    """Get service health."""
    return {{
        "status": "healthy",
        "service": "{service_name}",
        "features": {features}
    }}

@router.post("/process", response_model=ResponseModel)
async def process_request(request: RequestModel):
    """Process a service request."""
    # Import service here to avoid circular imports
    from ..services.{service_package}_service import {service_class}Service

    service = {service_class}Service()
    result = await service.process_request(request.data)

    return ResponseModel(
        message=result["message"],
        data=result["data"],
        service=result["service"]
    )
'''

    def generate_plugin_with_features(self, name: str, features: list = None, template: str = None) -> bool:
        """Generate a plugin with specific features (legacy compatibility)."""
        # Map to service generation for backward compatibility
        features_list = []
        if isinstance(features, dict):
            # Convert dict features to list
            features_list = list(features.keys())
        elif isinstance(features, list):
            features_list = features

        return self.generate_service("production", name, features=features_list)

    def generate_service_mesh_deployment(
        self,
        project_name: str,
        output_dir: str,
        domain: str = "example.com",
        mesh_type: str = "istio",
        **options: Any
    ) -> dict[str, str]:
        """
        Generate service mesh deployment scripts and configurations for a project.

        Args:
            project_name: Name of the project
            output_dir: Output directory for generated files
            domain: Domain name for the project
            mesh_type: Service mesh type (istio/linkerd)
            **options: Additional options like namespace, cluster_name, etc.

        Returns:
            Dictionary with paths to generated files
        """
        try:
            # Import the service mesh manager

            # Create manager and generate deployment files
            manager = EnhancedServiceMeshManager()

            generated_files = manager.generate_deployment_script(
                service_name=project_name,
                config={
                    "output_dir": output_dir,
                    "domain": domain,
                    "mesh_type": mesh_type
                }
            )

            print(f"✅ Generated service mesh deployment for {project_name}")
            print(f"   📄 Deployment script: {generated_files['deployment_script']}")
            print(f"   🔧 Plugin template: {generated_files['plugin_template']}")
            print(f"   📁 Manifests directory: {generated_files['manifests_dir']}")

            return generated_files

        except ImportError:
            print("❌ ServiceMeshManager not available - service mesh framework not properly installed")
            return {}
        except Exception as e:
            print(f"❌ Failed to generate service mesh deployment: {e}")
            return {}

    def _update_main_py_with_service(self, plugin_path: Path, service_name: str) -> None:
        """Update main.py to include the new service routes."""
        main_py_path = plugin_path / "main.py"
        if not main_py_path.exists():
            print("⚠️  main.py not found, skipping router integration")
            return

        try:
            # Read the current main.py content
            content = main_py_path.read_text()

            # Generate the import and router inclusion lines
            service_package = service_name.replace('-', '_')
            import_line = f"from app.api.{service_package}_routes import router as {service_package}_router"
            router_line = f"app.include_router({service_package}_router, prefix=\"/api/v1\", tags=[\"{service_name}\"])"

            # Check if import already exists
            if import_line in content:
                print(f"   📝 Router already imported for {service_name}")
                return

            # Add import after existing route imports
            if "from app.api.routes import router" in content:
                content = content.replace(
                    "from app.api.routes import router",
                    f"from app.api.routes import router\n{import_line}"
                )
            else:
                print("⚠️  Could not find main router import, manual integration needed")
                return

            # Add router inclusion after main router inclusion
            if "app.include_router(router, prefix=\"/api/v1\")" in content:
                content = content.replace(
                    "app.include_router(router, prefix=\"/api/v1\")",
                    f"app.include_router(router, prefix=\"/api/v1\")\n{router_line}"
                )
            else:
                print("⚠️  Could not find main router inclusion, manual integration needed")
                return

            # Write back the updated content
            main_py_path.write_text(content)
            print(f"   📝 Updated main.py to include {service_name} routes")

            # Update port forwarding script with new service endpoints
            self._update_port_forward_script(plugin_path, service_name)

        except Exception as e:
            print(f"⚠️  Error updating main.py: {e}")
            print(f"   Manual integration required for {service_name} routes")

    def _update_port_forward_script(self, plugin_path: Path, service_name: str) -> None:
        """Update port forwarding script to include new service endpoints."""
        port_forward_script = plugin_path / "dev" / "port-forward.sh"
        if not port_forward_script.exists():
            print("   ⚠️  Port forwarding script not found, skipping endpoint update")
            return

        try:
            # Read the current script content
            content = port_forward_script.read_text()

            # Add new service endpoints to the script
            service_endpoint_lines = f'''        log_info "  {service_name}: http://localhost:$local_port/api/v1/{service_name}/health"'''

            # Check if the service endpoint is already added
            if f"/api/v1/{service_name}/health" in content:
                print(f"   📝 Port forwarding script already includes {service_name} endpoints")
                return

            # Find the section where endpoints are listed and add the new service
            if 'log_info "  Status: http://localhost:$local_port/api/v1/status"' in content:
                content = content.replace(
                    'log_info "  Status: http://localhost:$local_port/api/v1/status"',
                    f'log_info "  Status: http://localhost:$local_port/api/v1/status"\n{service_endpoint_lines}'
                )

                # Write back the updated content
                port_forward_script.write_text(content)
                print(f"   📝 Updated port forwarding script to include {service_name} endpoints")
            else:
                print("   ⚠️  Could not find endpoint section in port forwarding script")

        except Exception as e:
            print(f"   ⚠️  Error updating port forwarding script: {e}")

    def _generate_dev_scripts(self, service_dir: Path, template_vars: dict[str, Any]) -> None:
        """Generate development scripts for the service."""
        # Create dev directory
        dev_dir = service_dir / "dev"
        dev_dir.mkdir(exist_ok=True)

        # Generate port-forward script
        port_forward_content = f'''#!/bin/bash
# Port forwarding script for {template_vars["service_name"]} service
# Generated by MMF CLI

set -e

# Configuration
SERVICE_NAME="{template_vars["service_package"]}-service"
LOCAL_PORT="${{1:-{template_vars["http_port"]}}}"
SERVICE_PORT="${{2:-80}}"
NAMESPACE="${{3:-default}}"

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

log_info() {{
    echo -e "${{BLUE}}[INFO]${{NC}} $1"
}}

log_success() {{
    echo -e "${{GREEN}}[SUCCESS]${{NC}} $1"
}}

log_warning() {{
    echo -e "${{YELLOW}}[WARNING]${{NC}} $1"
}}

log_error() {{
    echo -e "${{RED}}[ERROR]${{NC}} $1"
}}

# Function to check if kubectl is available
check_kubectl() {{
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
}}

# Function to check if service exists
check_service() {{
    local service_name=$1
    local namespace=$2

    if ! kubectl get service "$service_name" -n "$namespace" &> /dev/null; then
        log_error "Service '$service_name' not found in namespace '$namespace'"
        log_info "Available services:"
        kubectl get services -n "$namespace"
        exit 1
    fi
}}

# Function to check if port is already in use
check_port() {{
    local port=$1

    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warning "Port $port is already in use"
        log_info "Processes using port $port:"
        lsof -Pi :$port -sTCP:LISTEN

        read -p "Do you want to kill existing processes on port $port? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Killing processes on port $port..."
            lsof -ti:$port | xargs kill -9 2>/dev/null || true
            sleep 2
        else
            log_error "Cannot proceed with port $port in use"
            exit 1
        fi
    fi
}}

# Function to start port forwarding
start_port_forward() {{
    local service_name=$1
    local local_port=$2
    local service_port=$3
    local namespace=$4

    log_info "Starting port forwarding for {template_vars["service_name"]}:"
    log_info "  Service: $service_name (namespace: $namespace)"
    log_info "  Local port: $local_port"
    log_info "  Service port: $service_port"

    # Start port forwarding in background
    kubectl port-forward "service/$service_name" "$local_port:$service_port" -n "$namespace" &
    PF_PID=$!

    # Wait a moment for port forwarding to establish
    sleep 3

    # Check if port forwarding is working
    if ps -p $PF_PID > /dev/null; then
        log_success "Port forwarding started successfully (PID: $PF_PID)"
        log_info "Access the service at: http://localhost:$local_port"

        # Test basic connectivity
        if command -v curl &> /dev/null; then
            log_info "Testing connectivity..."
            if curl -s "http://localhost:$local_port/health" > /dev/null 2>&1; then
                log_success "Health check passed!"
            else
                log_warning "Health check failed, but port forwarding is active"
            fi
        fi

        # Print useful endpoints
        log_info "Common endpoints to test:"
        log_info "  Health: http://localhost:$local_port/health"
        log_info "  Docs: http://localhost:$local_port/docs"
        log_info "  Metrics: http://localhost:$local_port/metrics"
        log_info "  Status: http://localhost:$local_port/api/v1/status"

        # Keep the script running and handle cleanup on exit
        trap 'log_info "Stopping port forwarding..."; kill $PF_PID 2>/dev/null || true' EXIT

        log_info "Port forwarding is running. Press Ctrl+C to stop."
        wait $PF_PID
    else
        log_error "Failed to start port forwarding"
        exit 1
    fi
}}

# Function to show help
show_help() {{
    echo "{template_vars["service_name"]} Port Forwarding Helper"
    echo ""
    echo "Usage: $0 [local-port] [service-port] [namespace]"
    echo ""
    echo "Arguments:"
    echo "  local-port      Local port to forward to (default: {template_vars["http_port"]})"
    echo "  service-port    Service port to forward from (default: 80)"
    echo "  namespace       Kubernetes namespace (default: default)"
    echo ""
    echo "Examples:"
    echo "  $0                    # Forward {template_vars["service_package"]}-service:80 to localhost:{template_vars["http_port"]}"
    echo "  $0 8081              # Forward {template_vars["service_package"]}-service:80 to localhost:8081"
    echo "  $0 8081 8080         # Forward {template_vars["service_package"]}-service:8080 to localhost:8081"
}}

# Handle help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# Main execution
log_info "{template_vars["service_name"]} Port Forwarding Helper"
log_info "================================"

check_kubectl
check_service "$SERVICE_NAME" "$NAMESPACE"
check_port "$LOCAL_PORT"
start_port_forward "$SERVICE_NAME" "$LOCAL_PORT" "$SERVICE_PORT" "$NAMESPACE"
'''
        port_forward_script = dev_dir / "port-forward.sh"
        port_forward_script.write_text(port_forward_content)
        port_forward_script.chmod(0o755)
        print(f"  📝 Generated: {port_forward_script.relative_to(service_dir.parent)}")

        # Generate development configuration
        dev_config_content = f'''# Development Configuration for {template_vars["service_name"]}
# Generated by MMF CLI

service:
  name: "{template_vars["service_name"]}"
  package: "{template_vars["service_package"]}"
  port: {template_vars["http_port"]}

kubernetes:
  service_name: "{template_vars["service_package"]}-service"
  namespace: "default"
  deployment_name: "{template_vars["service_package"]}"

development:
  local_port: {template_vars["http_port"]}
  health_endpoint: "/health"
  docs_endpoint: "/docs"
  metrics_endpoint: "/metrics"

endpoints:
  health: "http://localhost:{template_vars["http_port"]}/health"
  docs: "http://localhost:{template_vars["http_port"]}/docs"
  metrics: "http://localhost:{template_vars["http_port"]}/metrics"
  status: "http://localhost:{template_vars["http_port"]}/api/v1/status"

docker:
  image_name: "{template_vars["service_package"]}:latest"
  build_context: "../.."  # Build from framework root
  dockerfile: "./Dockerfile"
'''
        dev_config = dev_dir / "dev-config.yaml"
        dev_config.write_text(dev_config_content)
        print(f"  📝 Generated: {dev_config.relative_to(service_dir.parent)}")

        # Generate quick deployment script
        deploy_script_content = f'''#!/bin/bash
# Quick deployment script for {template_vars["service_name"]}
# Generated by MMF CLI

set -e

# Configuration
SERVICE_NAME="{template_vars["service_package"]}"
IMAGE_NAME="{template_vars["service_package"]}:latest"
CLUSTER_NAME="${{KIND_CLUSTER_NAME:-microservices-framework}}"

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m'

log_info() {{
    echo -e "${{BLUE}}[INFO]${{NC}} $1"
}}

log_success() {{
    echo -e "${{GREEN}}[SUCCESS]${{NC}} $1"
}}

log_error() {{
    echo -e "${{RED}}[ERROR]${{NC}} $1"
}}

# Build Docker image
log_info "Building Docker image..."
cd ../..
if docker build -f plugins/{template_vars["service_package"]}/Dockerfile -t "$IMAGE_NAME" .; then
    log_success "Docker image built successfully"
else
    log_error "Failed to build Docker image"
    exit 1
fi

# Load image into kind cluster
log_info "Loading image into kind cluster..."
if kind load docker-image "$IMAGE_NAME" --name "$CLUSTER_NAME"; then
    log_success "Image loaded into kind cluster"
else
    log_error "Failed to load image into kind cluster"
    exit 1
fi

# Apply Kubernetes manifests
log_info "Applying Kubernetes manifests..."
cd plugins/{template_vars["service_package"]}
if kubectl apply -f k8s/; then
    log_success "Kubernetes manifests applied"
else
    log_error "Failed to apply Kubernetes manifests"
    exit 1
fi

# Wait for deployment to be ready
log_info "Waiting for deployment to be ready..."
if kubectl wait --for=condition=available --timeout=300s deployment/$SERVICE_NAME; then
    log_success "Deployment is ready!"

    # Show deployment status
    log_info "Deployment status:"
    kubectl get pods,svc -l app=$SERVICE_NAME

    log_info "To start port forwarding, run: ./dev/port-forward.sh"
else
    log_error "Deployment failed to become ready"
    exit 1
fi
'''
        deploy_script = dev_dir / "deploy.sh"
        deploy_script.write_text(deploy_script_content)
        deploy_script.chmod(0o755)
        print(f"  📝 Generated: {deploy_script.relative_to(service_dir.parent)}")

        # Generate README for development
        dev_readme_content = f'''# Development Guide for {template_vars["service_name"]}

This directory contains development scripts and configuration for the {template_vars["service_name"]} service.

## Quick Start

1. **Deploy to kind cluster:**
   ```bash
   ./dev/deploy.sh
   ```

2. **Start port forwarding:**
   ```bash
   ./dev/port-forward.sh
   ```

3. **Test the service:**
   ```bash
   curl http://localhost:{template_vars["http_port"]}/health
   ```

## Scripts

- `port-forward.sh` - Port forwarding helper for accessing the service locally
- `deploy.sh` - Quick deployment script for kind cluster
- `dev-config.yaml` - Development configuration

## Development Endpoints

- Health Check: http://localhost:{template_vars["http_port"]}/health
- API Documentation: http://localhost:{template_vars["http_port"]}/docs
- Metrics: http://localhost:{template_vars["http_port"]}/metrics
- Service Status: http://localhost:{template_vars["http_port"]}/api/v1/status

## Port Forwarding

The port forwarding script supports various options:

```bash
# Use default port ({template_vars["http_port"]})
./dev/port-forward.sh

# Use custom local port
./dev/port-forward.sh 8081

# Use custom local and service ports
./dev/port-forward.sh 8081 8080

# Use custom namespace
./dev/port-forward.sh 8081 80 production
```

## Deployment

The deployment script:
1. Builds the Docker image from the framework root
2. Loads the image into the kind cluster
3. Applies Kubernetes manifests
4. Waits for the deployment to be ready

Make sure you have:
- Docker running
- kind cluster running (`kind get clusters`)
- kubectl configured for the cluster

## Configuration

The `dev-config.yaml` file contains service-specific configuration for development:
- Service name and package information
- Kubernetes resource names
- Port configurations
- Endpoint URLs
'''
        dev_readme = dev_dir / "README.md"
        dev_readme.write_text(dev_readme_content)
        print(f"  📝 Generated: {dev_readme.relative_to(service_dir.parent)}")


# Legacy alias for backward compatibility
MinimalPluginGenerator = ServiceGenerator
