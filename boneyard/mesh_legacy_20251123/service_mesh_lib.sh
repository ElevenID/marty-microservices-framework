#!/bin/bash
# Service Mesh Framework Library
# Core reusable functions for service mesh deployment

# Framework version
export MARTY_MSF_SERVICE_MESH_VERSION="1.0.0"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# Default configuration that can be overridden
MESH_TYPE="${MESH_TYPE:-istio}"
CLUSTER_NAME="${CLUSTER_NAME:-default-cluster}"
NETWORK_NAME="${NETWORK_NAME:-default-network}"
ENABLE_MULTICLUSTER="${ENABLE_MULTICLUSTER:-false}"
ENABLE_OBSERVABILITY="${ENABLE_OBSERVABILITY:-true}"
DRY_RUN="${DRY_RUN:-false}"

# =============================================================================
# LOGGING FUNCTIONS
# =============================================================================

msf_log_info() {
    echo -e "${BLUE}[MSF-INFO]${NC} $*" >&2
}

msf_log_success() {
    echo -e "${GREEN}[MSF-SUCCESS]${NC} $*" >&2
}

msf_log_warning() {
    echo -e "${YELLOW}[MSF-WARNING]${NC} $*" >&2
}

msf_log_error() {
    echo -e "${RED}[MSF-ERROR]${NC} $*" >&2
}

msf_log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${CYAN}[MSF-DEBUG]${NC} $*" >&2
    fi
}

msf_log_section() {
    echo -e "${PURPLE}[MSF]${NC} $*" >&2
    echo -e "${PURPLE}=====================================${NC}" >&2
}

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

msf_check_prerequisites() {
    msf_log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        msf_log_error "kubectl is not installed or not in PATH"
        return 1
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        msf_log_error "Cannot connect to Kubernetes cluster"
        msf_log_info "Please check your KUBECONFIG and cluster connectivity"
        return 1
    fi

    # Check mesh-specific tools
    case "$MESH_TYPE" in
        istio)
            if ! command -v istioctl &> /dev/null; then
                msf_log_warning "istioctl not found, will attempt to install"
            fi
            ;;
        linkerd)
            if ! command -v linkerd &> /dev/null; then
                msf_log_warning "linkerd CLI not found, will attempt to install"
            fi
            ;;
        *)
            msf_log_error "Unsupported mesh type: $MESH_TYPE"
            msf_log_info "Supported types: istio, linkerd"
            return 1
            ;;
    esac

    msf_log_success "Prerequisites check completed"
    return 0
}

msf_validate_config() {
    msf_log_info "Validating configuration..."

    local errors=0

    if [[ -z "$CLUSTER_NAME" ]]; then
        msf_log_error "CLUSTER_NAME is required"
        errors=$((errors + 1))
    fi

    if [[ "$MESH_TYPE" != "istio" && "$MESH_TYPE" != "linkerd" ]]; then
        msf_log_error "MESH_TYPE must be 'istio' or 'linkerd'"
        errors=$((errors + 1))
    fi

    if [[ $errors -gt 0 ]]; then
        msf_log_error "Configuration validation failed with $errors errors"
        return 1
    fi

    msf_log_success "Configuration validation passed"
    return 0
}

# =============================================================================
# INSTALLATION FUNCTIONS
# =============================================================================

msf_install_mesh_cli() {
    case "$MESH_TYPE" in
        istio)
            if ! command -v istioctl &> /dev/null; then
                msf_log_info "Installing istioctl..."
                curl -L https://istio.io/downloadIstio | sh -
                export PATH="$PWD/istio-*/bin:$PATH"
            fi
            ;;
        linkerd)
            if ! command -v linkerd &> /dev/null; then
                msf_log_info "Installing linkerd CLI..."
                curl -sL https://run.linkerd.io/install | sh
                export PATH=$HOME/.linkerd2/bin:$PATH
            fi
            ;;
    esac
}

# =============================================================================
# KUBERNETES UTILITIES
# =============================================================================

msf_apply_manifest() {
    local manifest_file="$1"
    local description="$2"
    local namespace="${3:-}"

    if [[ ! -f "$manifest_file" ]]; then
        msf_log_error "Manifest file not found: $manifest_file"
        return 1
    fi

    msf_log_info "Applying $description..."

    # Substitute environment variables
    local temp_file
    temp_file=$(mktemp)
    envsubst < "$manifest_file" > "$temp_file"

    local kubectl_args=()
    if [[ -n "$namespace" ]]; then
        kubectl_args+=("-n" "$namespace")
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        msf_log_info "DRY RUN: Would apply $manifest_file"
        kubectl apply --dry-run=client -f "$temp_file" "${kubectl_args[@]}"
    else
        kubectl apply -f "$temp_file" "${kubectl_args[@]}"
    fi

    rm -f "$temp_file"
    return 0
}

msf_wait_for_deployment() {
    local namespace="$1"
    local deployment="$2"
    local timeout="${3:-300s}"

    msf_log_info "Waiting for deployment $deployment in namespace $namespace..."

    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl wait --for=condition=Available \
            deployment/"$deployment" \
            -n "$namespace" \
            --timeout="$timeout"
    fi
}

msf_create_namespace() {
    local namespace="$1"
    local labels="${2:-}"

    msf_log_info "Creating namespace: $namespace"

    if [[ "$DRY_RUN" == "true" ]]; then
        msf_log_info "DRY RUN: Would create namespace $namespace"
        return 0
    fi

    # Create namespace YAML
    local ns_yaml
    ns_yaml=$(cat << EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $namespace
EOF
)

    # Add labels if provided
    if [[ -n "$labels" ]]; then
        ns_yaml+=$'\n  labels:'
        while IFS='=' read -r key value; do
            ns_yaml+=$'\n    '"$key: \"$value\""
        done <<< "$labels"
    fi

    echo "$ns_yaml" | kubectl apply -f -
}

msf_enable_mesh_injection() {
    local namespace="$1"

    msf_log_info "Enabling service mesh injection for namespace: $namespace"

    if [[ "$DRY_RUN" == "true" ]]; then
        msf_log_info "DRY RUN: Would enable mesh injection for $namespace"
        return 0
    fi

    case "$MESH_TYPE" in
        istio)
            kubectl label namespace "$namespace" istio-injection=enabled --overwrite
            ;;
        linkerd)
            kubectl annotate namespace "$namespace" linkerd.io/inject=enabled --overwrite
            ;;
    esac

    msf_log_success "Mesh injection enabled for $namespace"
}

# =============================================================================
# HIGH-LEVEL DEPLOYMENT FUNCTIONS
# =============================================================================

msf_deploy_istio_production() {
    local config_dir="$1"

    msf_log_section "Deploying Istio Production Configuration"

    # Apply production manifests in order
    local manifests=(
        "istio-production.yaml"
        "istio-security.yaml"
        "istio-traffic-management.yaml"
        "istio-gateways.yaml"
    )

    for manifest in "${manifests[@]}"; do
        if [[ -f "$config_dir/$manifest" ]]; then
            msf_apply_manifest "$config_dir/$manifest" "Istio $manifest"
        else
            msf_log_warning "Manifest not found: $config_dir/$manifest"
        fi
    done

    # Multi-cluster if enabled
    if [[ "$ENABLE_MULTICLUSTER" == "true" ]] && [[ -f "$config_dir/istio-cross-cluster.yaml" ]]; then
        msf_apply_manifest "$config_dir/istio-cross-cluster.yaml" "Istio multi-cluster configuration"
    fi

    msf_wait_for_deployment "istio-system" "istiod" "600s"
}

msf_deploy_linkerd_production() {
    local config_dir="$1"

    msf_log_section "Deploying Linkerd Production Configuration"

    # Check pre-installation requirements
    if [[ "$DRY_RUN" == "false" ]]; then
        linkerd check --pre
        linkerd install --crds | kubectl apply -f -
        linkerd install | kubectl apply -f -
    else
        msf_log_info "DRY RUN: Would install Linkerd"
    fi

    msf_wait_for_deployment "linkerd" "linkerd-controller" "600s"

    # Apply production manifests
    local manifests=(
        "linkerd-production.yaml"
        "linkerd-security.yaml"
        "linkerd-traffic-management.yaml"
    )

    for manifest in "${manifests[@]}"; do
        if [[ -f "$config_dir/$manifest" ]]; then
            msf_apply_manifest "$config_dir/$manifest" "Linkerd $manifest"
        else
            msf_log_warning "Manifest not found: $config_dir/$manifest"
        fi
    done

    # Observability extensions
    if [[ "$ENABLE_OBSERVABILITY" == "true" && "$DRY_RUN" == "false" ]]; then
        linkerd viz install | kubectl apply -f -
        msf_wait_for_deployment "linkerd-viz" "web" "300s"
    fi
}

# =============================================================================
# MAIN DEPLOYMENT TEMPLATE
# =============================================================================

msf_deploy_service_mesh() {
    local config_dir="$1"
    local namespace="${2:-microservice-framework}"

    msf_log_section "Deploying $MESH_TYPE Service Mesh"
    msf_log_info "Config: $config_dir | Namespace: $namespace | Cluster: $CLUSTER_NAME"

    # Validation
    msf_check_prerequisites || return 1
    msf_validate_config || return 1

    # Install CLI tools
    msf_install_mesh_cli

    # Plugin pre-deployment hook
    if declare -f plugin_pre_deploy_hook > /dev/null; then
        plugin_pre_deploy_hook
    fi

    # Create and configure namespace
    msf_create_namespace "$namespace"
    msf_enable_mesh_injection "$namespace"

    # Deploy mesh
    case "$MESH_TYPE" in
        istio)
            msf_deploy_istio_production "$config_dir"
            ;;
        linkerd)
            msf_deploy_linkerd_production "$config_dir"
            ;;
    esac

    # Plugin custom configuration hook
    if declare -f plugin_custom_configuration > /dev/null; then
        plugin_custom_configuration
    fi

    # Verification
    msf_verify_deployment

    # Plugin post-deployment hook
    if declare -f plugin_post_deploy_hook > /dev/null; then
        plugin_post_deploy_hook
    fi

    msf_log_success "$MESH_TYPE service mesh deployment completed!"
}

# =============================================================================
# VERIFICATION FUNCTIONS
# =============================================================================

msf_verify_deployment() {
    msf_log_section "Verifying Service Mesh Deployment"

    case "$MESH_TYPE" in
        istio)
            if [[ "$DRY_RUN" == "false" ]]; then
                istioctl verify-install
                istioctl proxy-status
            else
                msf_log_info "DRY RUN: Would verify Istio installation"
            fi
            ;;
        linkerd)
            if [[ "$DRY_RUN" == "false" ]]; then
                linkerd check
                linkerd check --proxy
            else
                msf_log_info "DRY RUN: Would verify Linkerd installation"
            fi
            ;;
    esac

    msf_log_success "Service mesh verification completed"
}

# =============================================================================
# TEMPLATE GENERATION FUNCTIONS
# =============================================================================

msf_generate_deployment_script() {
    local project_name="$1"
    local output_dir="$2"
    local domain="${3:-example.com}"

    msf_log_info "Generating deployment script for project: $project_name"

    cat << 'EOF' > "$output_dir/deploy-service-mesh.sh"
#!/bin/bash
# Generated Service Mesh Deployment Script
# Project: {{PROJECT_NAME}}
# Generated by Marty Microservices Framework

# Source the framework library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_LIB_PATH="${MARTY_MSF_PATH:-$HOME/.marty-msf}/lib/service-mesh-lib.sh"

if [[ -f "$FRAMEWORK_LIB_PATH" ]]; then
    source "$FRAMEWORK_LIB_PATH"
else
    echo "ERROR: Marty MSF service mesh library not found at $FRAMEWORK_LIB_PATH"
    echo "Please ensure Marty MSF is properly installed"
    exit 1
fi

# Source project-specific plugin extensions
if [[ -f "$SCRIPT_DIR/plugins/service-mesh-extensions.sh" ]]; then
    source "$SCRIPT_DIR/plugins/service-mesh-extensions.sh"
fi

# =============================================================================
# PROJECT CONFIGURATION
# =============================================================================

PROJECT_NAME="{{PROJECT_NAME}}"
PROJECT_DOMAIN="{{PROJECT_DOMAIN}}"
PROJECT_NAMESPACE="{{PROJECT_NAMESPACE}}"

# Override default framework settings
MESH_TYPE="${MESH_TYPE:-istio}"
CLUSTER_NAME="${CLUSTER_NAME:-{{PROJECT_NAME}}-cluster}"
NETWORK_NAME="${NETWORK_NAME:-{{PROJECT_NAME}}-network}"
ENABLE_MULTICLUSTER="${ENABLE_MULTICLUSTER:-false}"
ENABLE_OBSERVABILITY="${ENABLE_OBSERVABILITY:-true}"

# =============================================================================
# PROJECT-SPECIFIC HOOKS (Override in plugins/service-mesh-extensions.sh)
# =============================================================================

plugin_pre_deploy_hook() {
    msf_log_section "Project Pre-Deploy Hook"
    # Add your pre-deployment logic here
    # Example: create project-specific secrets, certificates, etc.
}

plugin_custom_configuration() {
    msf_log_section "Project Custom Configuration"
    # Add your custom service mesh configuration here
    # Example: apply project-specific policies, gateways, traffic rules
}

plugin_post_deploy_hook() {
    msf_log_section "Project Post-Deploy Hook"
    # Add your post-deployment logic here
    # Example: configure monitoring, set up external integrations
}

# =============================================================================
# USAGE FUNCTION
# =============================================================================

show_usage() {
    cat << USAGE
Usage: $0 [OPTIONS]

Service mesh deployment for $PROJECT_NAME

OPTIONS:
    --mesh-type TYPE        Service mesh type (istio|linkerd) [default: $MESH_TYPE]
    --cluster-name NAME     Kubernetes cluster name [default: $CLUSTER_NAME]
    --domain DOMAIN         Project domain [default: $PROJECT_DOMAIN]
    --namespace NAMESPACE   Target namespace [default: $PROJECT_NAMESPACE]
    --enable-multicluster   Enable multi-cluster features
    --enable-observability  Enable observability features
    --dry-run              Show what would be done without applying
    --debug                Enable debug logging
    -h, --help             Show this help message

EXAMPLES:
    # Deploy with default settings
    $0

    # Deploy with custom domain and Linkerd
    $0 --mesh-type linkerd --domain mycompany.com

    # Dry run deployment
    $0 --dry-run

USAGE
}

# =============================================================================
# MAIN FUNCTION
# =============================================================================

main() {
    local config_dir="$SCRIPT_DIR/k8s/service-mesh"

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --mesh-type)
                MESH_TYPE="$2"
                shift 2
                ;;
            --cluster-name)
                CLUSTER_NAME="$2"
                shift 2
                ;;
            --domain)
                PROJECT_DOMAIN="$2"
                shift 2
                ;;
            --namespace)
                PROJECT_NAMESPACE="$2"
                shift 2
                ;;
            --enable-multicluster)
                ENABLE_MULTICLUSTER="true"
                shift
                ;;
            --enable-observability)
                ENABLE_OBSERVABILITY="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --debug)
                export DEBUG="true"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                msf_log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Header
    msf_log_section "$PROJECT_NAME Service Mesh Deployment"
    msf_log_info "Domain: $PROJECT_DOMAIN | Namespace: $PROJECT_NAMESPACE"

    # Export configuration for framework
    export MESH_TYPE CLUSTER_NAME NETWORK_NAME ENABLE_MULTICLUSTER ENABLE_OBSERVABILITY
    export PROJECT_NAME PROJECT_DOMAIN PROJECT_NAMESPACE

    # Run deployment
    msf_deploy_service_mesh "$config_dir" "$PROJECT_NAMESPACE"

    msf_log_success "$PROJECT_NAME service mesh deployment completed!"
    msf_log_info "Access your services at: https://$PROJECT_DOMAIN"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
EOF

    # Replace template variables
    sed -i.bak "s/{{PROJECT_NAME}}/$project_name/g" "$output_dir/deploy-service-mesh.sh"
    sed -i.bak "s/{{PROJECT_DOMAIN}}/$domain/g" "$output_dir/deploy-service-mesh.sh"
    sed -i.bak "s/{{PROJECT_NAMESPACE}}/$project_name/g" "$output_dir/deploy-service-mesh.sh"
    rm -f "$output_dir/deploy-service-mesh.sh.bak"

    chmod +x "$output_dir/deploy-service-mesh.sh"

    msf_log_success "Deployment script generated: $output_dir/deploy-service-mesh.sh"
}

msf_generate_plugin_template() {
    local output_dir="$1"

    mkdir -p "$output_dir/plugins"

    cat << 'EOF' > "$output_dir/plugins/service-mesh-extensions.sh"
#!/bin/bash
# Project-Specific Service Mesh Extensions
# Customize your service mesh deployment here

# =============================================================================
# PROJECT-SPECIFIC CONFIGURATION
# =============================================================================

# Add your project-specific variables here
# CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-api.myproject.com}"
# ENABLE_CUSTOM_AUTH="${ENABLE_CUSTOM_AUTH:-true}"
# CUSTOM_SECRET_NAME="${CUSTOM_SECRET_NAME:-my-project-secrets}"

# =============================================================================
# HOOK IMPLEMENTATIONS
# =============================================================================

plugin_pre_deploy_hook() {
    msf_log_section "Project Pre-Deploy Extensions"

    # Example: Create project-specific secrets
    # create_project_secrets

    # Example: Set up custom certificates
    # setup_custom_certificates

    msf_log_info "Pre-deploy extensions completed"
}

plugin_custom_configuration() {
    msf_log_section "Project Custom Service Mesh Configuration"

    # Example: Apply custom authorization policies
    # apply_custom_auth_policies

    # Example: Configure custom gateways
    # configure_project_gateways

    # Example: Set up custom traffic rules
    # setup_traffic_management

    msf_log_info "Custom configuration completed"
}

plugin_post_deploy_hook() {
    msf_log_section "Project Post-Deploy Extensions"

    # Example: Configure monitoring dashboards
    # deploy_monitoring_dashboards

    # Example: Set up external integrations
    # setup_external_services

    # Example: Configure backup policies
    # configure_backup_policies

    msf_log_info "Post-deploy extensions completed"
}

# =============================================================================
# EXAMPLE EXTENSION FUNCTIONS
# =============================================================================

# Uncomment and customize these examples for your project

# create_project_secrets() {
#     msf_log_info "Creating project-specific secrets..."
#
#     local secret_yaml
#     secret_yaml=$(cat << SECRET_EOF
# apiVersion: v1
# kind: Secret
# metadata:
#   name: $CUSTOM_SECRET_NAME
#   namespace: $PROJECT_NAMESPACE
# type: Opaque
# data:
#   api-key: $(echo -n "your-api-key" | base64 -w 0)
#   database-url: $(echo -n "your-db-url" | base64 -w 0)
# SECRET_EOF
# )
#
#     if [[ "$DRY_RUN" == "true" ]]; then
#         msf_log_info "DRY RUN: Would create project secrets"
#     else
#         echo "$secret_yaml" | kubectl apply -f -
#     fi
# }

# apply_custom_auth_policies() {
#     msf_log_info "Applying custom authorization policies..."
#
#     local auth_policy_yaml
#     auth_policy_yaml=$(cat << AUTH_EOF
# apiVersion: security.istio.io/v1beta1
# kind: AuthorizationPolicy
# metadata:
#   name: ${PROJECT_NAME}-auth-policy
#   namespace: $PROJECT_NAMESPACE
# spec:
#   rules:
#   - from:
#     - source:
#         principals: ["cluster.local/ns/$PROJECT_NAMESPACE/sa/api-service"]
#   - to:
#     - operation:
#         methods: ["GET", "POST"]
# AUTH_EOF
# )
#
#     if [[ "$DRY_RUN" == "true" ]]; then
#         msf_log_info "DRY RUN: Would apply custom auth policies"
#     else
#         echo "$auth_policy_yaml" | kubectl apply -f -
#     fi
# }

# configure_project_gateways() {
#     msf_log_info "Configuring project-specific gateways..."
#
#     local gateway_yaml
#     gateway_yaml=$(cat << GATEWAY_EOF
# apiVersion: networking.istio.io/v1beta1
# kind: Gateway
# metadata:
#   name: ${PROJECT_NAME}-gateway
#   namespace: $PROJECT_NAMESPACE
# spec:
#   selector:
#     istio: gateway
#   servers:
#   - port:
#       number: 443
#       name: https
#       protocol: HTTPS
#     tls:
#       mode: SIMPLE
#       credentialName: ${PROJECT_NAME}-tls-cert
#     hosts:
#     - "$PROJECT_DOMAIN"
# GATEWAY_EOF
# )
#
#     if [[ "$DRY_RUN" == "true" ]]; then
#         msf_log_info "DRY RUN: Would configure project gateways"
#     else
#         echo "$gateway_yaml" | kubectl apply -f -
#     fi
# }

EOF

    msf_log_success "Plugin template generated: $output_dir/plugins/service-mesh-extensions.sh"
}

# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

# Export core functions for use by generated scripts
export -f msf_log_info msf_log_success msf_log_warning msf_log_error msf_log_debug msf_log_section
export -f msf_check_prerequisites msf_validate_config msf_install_mesh_cli
export -f msf_apply_manifest msf_wait_for_deployment msf_create_namespace msf_enable_mesh_injection
export -f msf_deploy_istio_production msf_deploy_linkerd_production
export -f msf_deploy_service_mesh msf_verify_deployment
export -f msf_generate_deployment_script msf_generate_plugin_template
