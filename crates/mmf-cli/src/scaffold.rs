use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::{CliError, GeneratedArtifact, TemplateContext, TemplateEngine, validate_token};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum ServiceTemplate {
    FastapiService,
    ApiGatewayService,
    ConfigService,
    SagaOrchestrator,
    ServiceDiscovery,
    ApiVersioning,
    GrpcService,
    HybridService,
    ProductionService,
    MinimalService,
}

impl ServiceTemplate {
    pub fn parse(value: &str) -> Result<Self, CliError> {
        match value {
            "fastapi-service" | "fastapi" => Ok(Self::FastapiService),
            "api-gateway-service" | "api-gateway" => Ok(Self::ApiGatewayService),
            "config-service" | "config" => Ok(Self::ConfigService),
            "saga-orchestrator" | "saga" => Ok(Self::SagaOrchestrator),
            "service-discovery" | "discovery" => Ok(Self::ServiceDiscovery),
            "api-versioning" => Ok(Self::ApiVersioning),
            "grpc-service" | "grpc" => Ok(Self::GrpcService),
            "hybrid-service" | "hybrid" => Ok(Self::HybridService),
            "production-service" | "production" => Ok(Self::ProductionService),
            "minimal-service" | "minimal" => Ok(Self::MinimalService),
            _ => Err(CliError::NotFound(format!("service template {value}"))),
        }
    }

    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            Self::FastapiService => "fastapi-service",
            Self::ApiGatewayService => "api-gateway-service",
            Self::ConfigService => "config-service",
            Self::SagaOrchestrator => "saga-orchestrator",
            Self::ServiceDiscovery => "service-discovery",
            Self::ApiVersioning => "api-versioning",
            Self::GrpcService => "grpc-service",
            Self::HybridService => "hybrid-service",
            Self::ProductionService => "production-service",
            Self::MinimalService => "minimal-service",
        }
    }

    #[must_use]
    pub const fn category(self) -> TemplateCategory {
        match self {
            Self::ApiGatewayService
            | Self::ConfigService
            | Self::ServiceDiscovery
            | Self::ApiVersioning => TemplateCategory::Infrastructure,
            Self::SagaOrchestrator => TemplateCategory::Workflow,
            _ => TemplateCategory::Service,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TemplateCategory {
    Service,
    Infrastructure,
    Workflow,
    Plugin,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TemplateDescriptor {
    pub name: String,
    pub description: String,
    pub category: TemplateCategory,
    #[serde(default)]
    pub dependencies: Vec<String>,
    #[serde(default)]
    pub variables: BTreeMap<String, Value>,
    pub framework_version: String,
}

impl TemplateDescriptor {
    pub fn validate(&self) -> Result<(), CliError> {
        validate_token("template name", &self.name)?;
        validate_token("template description", &self.description)?;
        validate_token("framework version", &self.framework_version)
    }
}

#[must_use]
pub fn builtin_templates() -> Vec<TemplateDescriptor> {
    [
        ServiceTemplate::FastapiService,
        ServiceTemplate::ApiGatewayService,
        ServiceTemplate::ConfigService,
        ServiceTemplate::SagaOrchestrator,
        ServiceTemplate::ServiceDiscovery,
        ServiceTemplate::ApiVersioning,
        ServiceTemplate::GrpcService,
        ServiceTemplate::HybridService,
        ServiceTemplate::ProductionService,
        ServiceTemplate::MinimalService,
    ]
    .into_iter()
    .map(|template| TemplateDescriptor {
        name: template.name().into(),
        description: template_description(template).into(),
        category: template.category(),
        dependencies: template_dependencies(template),
        variables: BTreeMap::new(),
        framework_version: env!("CARGO_PKG_VERSION").into(),
    })
    .collect()
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct ProjectConfig {
    pub name: String,
    pub template: ServiceTemplate,
    pub output_path: PathBuf,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub email: String,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_license")]
    pub license: String,
    #[serde(default)]
    pub git_repository: String,
    #[serde(default = "default_true")]
    pub docker_enabled: bool,
    #[serde(default = "default_true")]
    pub kubernetes_enabled: bool,
    #[serde(default = "default_true")]
    pub monitoring_enabled: bool,
    #[serde(default = "default_true")]
    pub testing_enabled: bool,
    #[serde(default = "default_true")]
    pub ci_cd_enabled: bool,
    #[serde(default = "default_environment")]
    pub environment: String,
    #[serde(default = "default_http_port")]
    pub http_port: u16,
    #[serde(default = "default_grpc_port")]
    pub grpc_port: u16,
    #[serde(default)]
    pub variables: BTreeMap<String, Value>,
}

impl ProjectConfig {
    pub fn validate(&self) -> Result<(), CliError> {
        validate_project_name(&self.name)?;
        if self.output_path.as_os_str().is_empty() {
            return Err(CliError::InvalidInput(
                "project output path is required".into(),
            ));
        }
        if self.http_port == self.grpc_port {
            return Err(CliError::InvalidInput(
                "HTTP and gRPC ports must be different".into(),
            ));
        }
        validate_token("license", &self.license)?;
        validate_token("environment", &self.environment)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct GeneratedProject {
    pub root: PathBuf,
    pub template: ServiceTemplate,
    pub files: Vec<GeneratedArtifact>,
    #[serde(default)]
    pub post_generation: Vec<ProcessInvocation>,
}

impl GeneratedProject {
    pub fn validate(&self) -> Result<(), CliError> {
        if self.root.as_os_str().is_empty() || self.root == Path::new("/") {
            return Err(CliError::InvalidInput("unsafe project root".into()));
        }
        for file in &self.files {
            if file.relative_path.is_absolute()
                || file
                    .relative_path
                    .components()
                    .any(|part| matches!(part, std::path::Component::ParentDir))
            {
                return Err(CliError::InvalidInput(format!(
                    "project file escapes root: {}",
                    file.relative_path.display()
                )));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ProcessInvocation {
    pub program: String,
    #[serde(default)]
    pub arguments: Vec<String>,
    pub working_directory: Option<PathBuf>,
    #[serde(default)]
    pub environment: BTreeMap<String, String>,
}

impl ProcessInvocation {
    pub fn validate(&self) -> Result<(), CliError> {
        validate_token("program", &self.program)?;
        if self.program.contains(['/', '\\']) {
            return Err(CliError::InvalidInput(
                "program must be resolved by the host PATH".into(),
            ));
        }
        if self
            .arguments
            .iter()
            .any(|argument| argument.contains(['\0', '\n', '\r']))
        {
            return Err(CliError::InvalidInput(
                "process argument contains a control character".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default)]
pub struct ScaffoldGenerator;

impl ScaffoldGenerator {
    pub fn generate(config: &ProjectConfig) -> Result<GeneratedProject, CliError> {
        config.validate()?;
        let names = ProjectNames::new(&config.name);
        let root = config.output_path.join(&names.kebab);
        let mut files = Vec::new();
        add_file(
            &mut files,
            "Cargo.toml",
            "text/plain",
            &cargo_manifest(config, &names),
        );
        add_file(
            &mut files,
            "src/lib.rs",
            "text/x-rust",
            &library_source(config, &names),
        );
        add_file(
            &mut files,
            "src/main.rs",
            "text/x-rust",
            &main_source(config, &names),
        );
        add_file(
            &mut files,
            "marty.toml",
            "text/plain",
            &project_manifest(config, &names),
        );
        add_file(
            &mut files,
            "README.md",
            "text/markdown",
            &readme(config, &names),
        );
        add_file(&mut files, ".gitignore", "text/plain", "/target\n.env\n");
        if config.testing_enabled {
            add_file(
                &mut files,
                "tests/behavior.rs",
                "text/x-rust",
                &behavior_test(&names),
            );
        }
        if config.docker_enabled {
            add_file(&mut files, "Dockerfile", "text/plain", &dockerfile(&names));
        }
        if config.kubernetes_enabled {
            add_file(
                &mut files,
                "k8s/base/deployment.yaml",
                "application/yaml",
                &deployment(config, &names),
            );
            add_file(
                &mut files,
                "k8s/base/service.yaml",
                "application/yaml",
                &service_manifest(config, &names),
            );
            add_file(
                &mut files,
                "k8s/base/kustomization.yaml",
                "application/yaml",
                &kustomization(&names),
            );
        }
        if config.monitoring_enabled {
            add_file(
                &mut files,
                "docs/OBSERVABILITY.md",
                "text/markdown",
                OBSERVABILITY_DOCS,
            );
        }
        if config.ci_cd_enabled {
            add_file(
                &mut files,
                ".github/workflows/ci.yml",
                "application/yaml",
                CI_WORKFLOW,
            );
        }
        let project = GeneratedProject {
            root: root.clone(),
            template: config.template,
            files,
            post_generation: vec![ProcessInvocation {
                program: "git".into(),
                arguments: vec!["init".into()],
                working_directory: Some(root),
                environment: BTreeMap::new(),
            }],
        };
        project.validate()?;
        Ok(project)
    }

    pub fn render_custom(
        engine: &TemplateEngine,
        templates: &BTreeMap<PathBuf, String>,
        config: &ProjectConfig,
    ) -> Result<GeneratedProject, CliError> {
        config.validate()?;
        let names = ProjectNames::new(&config.name);
        let mut context = TemplateContext::default()
            .with("project_name", config.name.clone())
            .with("project_slug", names.kebab.clone())
            .with("project_snake", names.snake.clone())
            .with("project_pascal", names.pascal.clone())
            .with("project_kebab", names.kebab.clone())
            .with("author", config.author.clone())
            .with("email", config.email.clone())
            .with("description", config.description.clone())
            .with("service_port", u64::from(config.http_port))
            .with("framework_version", env!("CARGO_PKG_VERSION"));
        context.variables.extend(config.variables.clone());
        let mut files = Vec::new();
        for (path, template_name) in templates {
            let rendered = engine.render(template_name, &context, None)?;
            add_file(&mut files, path, media_type(path), &rendered);
        }
        let project = GeneratedProject {
            root: config.output_path.join(&names.kebab),
            template: config.template,
            files,
            post_generation: Vec::new(),
        };
        project.validate()?;
        Ok(project)
    }
}

pub fn plugin_scaffold(
    name: &str,
    description: &str,
    author: &str,
    features: &[String],
) -> Result<Vec<GeneratedArtifact>, CliError> {
    validate_project_name(name)?;
    let names = ProjectNames::new(name);
    let metadata = json!({
        "name": names.kebab,
        "version": "0.1.0",
        "description": description,
        "author": author,
        "dependencies": [],
        "api_version": "v1",
        "min_mmf_version": env!("CARGO_PKG_VERSION"),
        "keywords": features,
        "homepage": "",
        "license": "AGPL-3.0-only",
        "kind": "service"
    });
    let mut files = Vec::new();
    add_file(
        &mut files,
        "plugin.json",
        "application/json",
        &serde_json::to_string_pretty(&metadata)
            .map_err(|error| CliError::Operation(error.to_string()))?,
    );
    add_file(
        &mut files,
        "README.md",
        "text/markdown",
        &format!("# {}\n\n{}\n", names.pascal, description),
    );
    add_file(
        &mut files,
        "src/lib.rs",
        "text/x-rust",
        &format!(
            "//! {} MMF plugin.\n\npub const PLUGIN_NAME: &str = {:?};\n",
            names.pascal, names.kebab
        ),
    );
    Ok(files)
}

fn validate_project_name(name: &str) -> Result<(), CliError> {
    let expression = Regex::new(r"^[A-Za-z][A-Za-z0-9_-]{1,62}$")
        .map_err(|error| CliError::Operation(error.to_string()))?;
    if expression.is_match(name) {
        Ok(())
    } else {
        Err(CliError::InvalidInput(
            "project name must start with a letter and contain 2-63 safe characters".into(),
        ))
    }
}

struct ProjectNames {
    kebab: String,
    snake: String,
    pascal: String,
}

impl ProjectNames {
    fn new(name: &str) -> Self {
        let words = name
            .split(|character: char| !character.is_ascii_alphanumeric())
            .filter(|word| !word.is_empty())
            .map(str::to_lowercase)
            .collect::<Vec<_>>();
        let pascal = words
            .iter()
            .map(|word| {
                let mut characters = word.chars();
                characters.next().map_or_else(String::new, |first| {
                    format!("{}{}", first.to_ascii_uppercase(), characters.as_str())
                })
            })
            .collect();
        Self {
            kebab: words.join("-"),
            snake: words.join("_"),
            pascal,
        }
    }
}

fn template_description(template: ServiceTemplate) -> &'static str {
    match template {
        ServiceTemplate::FastapiService => "REST service with health, metrics, and MMF composition",
        ServiceTemplate::ApiGatewayService => {
            "API gateway with routing, rate limiting, and security"
        }
        ServiceTemplate::ConfigService => "Centralized configuration and secret-reference service",
        ServiceTemplate::SagaOrchestrator => "Durable distributed-workflow coordinator",
        ServiceTemplate::ServiceDiscovery => "Service registration and discovery endpoint",
        ServiceTemplate::ApiVersioning => "Versioned API and behavioral contract service",
        ServiceTemplate::GrpcService => "Typed gRPC service with health and observability",
        ServiceTemplate::HybridService => "Combined REST and gRPC service",
        ServiceTemplate::ProductionService => {
            "Production REST service with all operational defaults"
        }
        ServiceTemplate::MinimalService => "Minimal Rust MMF service",
    }
}

fn template_dependencies(template: ServiceTemplate) -> Vec<String> {
    let capability = match template {
        ServiceTemplate::ApiGatewayService | ServiceTemplate::ServiceDiscovery => "mmf-platform",
        ServiceTemplate::ConfigService => "mmf-config",
        ServiceTemplate::SagaOrchestrator => "mmf-workflow",
        ServiceTemplate::ApiVersioning => "mmf-cli",
        ServiceTemplate::GrpcService | ServiceTemplate::HybridService => "mmf-runtime",
        _ => "mmf",
    };
    vec![capability.into()]
}

fn cargo_manifest(config: &ProjectConfig, names: &ProjectNames) -> String {
    let mut dependencies = String::from(
        "axum = \"0.8\"\nmmf = \"__MMF_VERSION__\"\nserde = { version = \"1\", features = [\"derive\"] }\nserde_json = \"1\"\ntokio = { version = \"1\", features = [\"macros\", \"rt-multi-thread\", \"signal\"] }\n",
    )
    .replace("__MMF_VERSION__", env!("CARGO_PKG_VERSION"));
    if matches!(
        config.template,
        ServiceTemplate::GrpcService | ServiceTemplate::HybridService
    ) {
        dependencies.push_str("tonic = \"0.14\"\n");
    }
    format!(
        "[package]\nname = {:?}\nversion = \"0.1.0\"\nedition = \"2024\"\nlicense = {:?}\n\n[dependencies]\n{dependencies}",
        names.kebab, config.license
    )
}

fn library_source(config: &ProjectConfig, names: &ProjectNames) -> String {
    let feature = match config.template {
        ServiceTemplate::ApiGatewayService => "pub type RouteRegistry = mmf::platform::RouteTable;",
        ServiceTemplate::ConfigService => {
            "pub type ConfigurationRegistry = mmf::config::LayeredConfig;"
        }
        ServiceTemplate::SagaOrchestrator => {
            "pub type SagaCoordinator = mmf::workflow::InMemoryWorkflowRepository;"
        }
        ServiceTemplate::ServiceDiscovery => {
            "pub type ServiceRegistry = mmf::platform::InMemoryRegistry;"
        }
        ServiceTemplate::ApiVersioning => {
            "pub type ApiVersionRegistry = mmf::cli::VersionRegistry;"
        }
        ServiceTemplate::GrpcService => "pub type GrpcService = mmf::runtime::RuntimeState;",
        ServiceTemplate::HybridService => "pub type HybridService = mmf::runtime::RuntimeState;",
        ServiceTemplate::ProductionService => {
            "pub type ProductionService = mmf::runtime::RuntimeState;"
        }
        ServiceTemplate::FastapiService | ServiceTemplate::MinimalService => {
            "pub type Service = mmf::runtime::RuntimeState;"
        }
    };
    format!(
        "//! {} service domain.\n\nuse serde::Serialize;\n\n#[derive(Clone, Debug, Eq, PartialEq, Serialize)]\npub struct Health {{\n    pub status: &'static str,\n    pub service: &'static str,\n    pub version: &'static str,\n}}\n\n#[must_use]\npub const fn health() -> Health {{\n    Health {{ status: \"healthy\", service: {:?}, version: env!(\"CARGO_PKG_VERSION\") }}\n}}\n\n{}\n",
        names.pascal, names.kebab, feature
    )
}

fn main_source(config: &ProjectConfig, names: &ProjectNames) -> String {
    format!(
        "use axum::{{Router, routing::get}};\nuse {}::health;\n\n#[tokio::main]\nasync fn main() -> Result<(), Box<dyn std::error::Error>> {{\n    let app = Router::new().route(\"/health\", get(|| async {{ axum::Json(health()) }}));\n    let listener = tokio::net::TcpListener::bind((\"0.0.0.0\", {})).await?;\n    axum::serve(listener, app).with_graceful_shutdown(async {{ let _ = tokio::signal::ctrl_c().await; }}).await?;\n    Ok(())\n}}\n",
        names.snake, config.http_port
    )
}

fn project_manifest(config: &ProjectConfig, names: &ProjectNames) -> String {
    format!(
        "[project]\nname = {:?}\nversion = \"0.1.0\"\ndescription = {:?}\nauthor = {:?}\nemail = {:?}\n\n[service]\nport = {}\ngrpc_port = {}\ntemplate = {:?}\nenvironment = {:?}\n",
        names.kebab,
        config.description,
        config.author,
        config.email,
        config.http_port,
        config.grpc_port,
        config.template.name(),
        config.environment
    )
}

fn readme(config: &ProjectConfig, names: &ProjectNames) -> String {
    format!(
        "# {}\n\n{}\n\nGenerated from `{}` by the Rust Marty CLI.\n\n```sh\ncargo test\ncargo run\n```\n",
        names.pascal,
        config.description,
        config.template.name()
    )
}

fn behavior_test(names: &ProjectNames) -> String {
    format!(
        "#[test]\nfn health_contract() {{\n    let health = {}::health();\n    assert_eq!(health.status, \"healthy\");\n    assert_eq!(health.service, {:?});\n}}\n",
        names.snake, names.kebab
    )
}

fn dockerfile(names: &ProjectNames) -> String {
    format!(
        "FROM rust:1.95 AS build\nWORKDIR /app\nCOPY . .\nRUN cargo build --release --locked\nFROM gcr.io/distroless/cc-debian12:nonroot\nCOPY --from=build /app/target/release/{0} /usr/local/bin/service\nUSER nonroot\nENTRYPOINT [\"/usr/local/bin/service\"]\n",
        names.kebab
    )
}

fn deployment(config: &ProjectConfig, names: &ProjectNames) -> String {
    format!(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {0}\nspec:\n  replicas: 1\n  selector:\n    matchLabels:\n      app: {0}\n  template:\n    metadata:\n      labels:\n        app: {0}\n    spec:\n      containers:\n        - name: {0}\n          image: {0}:latest\n          ports:\n            - name: http\n              containerPort: {1}\n          readinessProbe:\n            httpGet:\n              path: /health\n              port: http\n          livenessProbe:\n            httpGet:\n              path: /health\n              port: http\n",
        names.kebab, config.http_port
    )
}

fn service_manifest(config: &ProjectConfig, names: &ProjectNames) -> String {
    format!(
        "apiVersion: v1\nkind: Service\nmetadata:\n  name: {0}\nspec:\n  selector:\n    app: {0}\n  ports:\n    - name: http\n      port: {1}\n      targetPort: http\n",
        names.kebab, config.http_port
    )
}

fn kustomization(names: &ProjectNames) -> String {
    format!(
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - deployment.yaml\n  - service.yaml\ncommonLabels:\n  app.kubernetes.io/name: {}\n",
        names.kebab
    )
}

fn add_file(
    files: &mut Vec<GeneratedArtifact>,
    path: impl Into<PathBuf>,
    media_type: &str,
    content: &str,
) {
    files.push(GeneratedArtifact {
        relative_path: path.into(),
        media_type: media_type.into(),
        content: content.into(),
    });
}

fn media_type(path: &Path) -> &'static str {
    match path.extension().and_then(|extension| extension.to_str()) {
        Some("json") => "application/json",
        Some("yaml" | "yml") => "application/yaml",
        Some("md") => "text/markdown",
        Some("rs") => "text/x-rust",
        _ => "text/plain",
    }
}

fn default_license() -> String {
    "AGPL-3.0-only".into()
}
const fn default_true() -> bool {
    true
}
fn default_environment() -> String {
    "development".into()
}
const fn default_http_port() -> u16 {
    8000
}
const fn default_grpc_port() -> u16 {
    50_051
}

const OBSERVABILITY_DOCS: &str = "# Observability\n\nThe service exposes `/health`; compose tracing, metrics, and structured logging through `mmf-observability`.\n";
const CI_WORKFLOW: &str = "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: dtolnay/rust-toolchain@stable\n      - run: cargo fmt --check\n      - run: cargo clippy --all-targets -- -D warnings\n      - run: cargo test\n";
