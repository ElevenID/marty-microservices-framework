#!/bin/bash

# Security Scanning Suite for Microservices Framework
# Comprehensive security checks and vulnerability assessments for microservices

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Security configuration
SECURITY_REPORTS_DIR="$PROJECT_ROOT/reports/security"
SECURITY_CONFIG_DIR="$PROJECT_ROOT/security/policies"
LOG_FILE="$PROJECT_ROOT/logs/security_scan.log"

# Function to print colored output
print_header() {
    echo -e "${BLUE}${1}${NC}"
    echo "$(printf '=%.0s' {1..60})"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

print_critical() {
    echo -e "${PURPLE}🚨${NC} $1"
}

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to ensure required tools are available
check_dependencies() {
    print_header "🔧 Checking Security Tools Dependencies"

    local missing_tools=()

    # Check for Python and pip
    if ! command_exists python3; then
        missing_tools+=("python3")
    fi

    # Check for UV (primary package manager)
    if ! command_exists uv; then
        missing_tools+=("uv")
    fi

    # Check for Docker (for container security scans)
    if ! command_exists docker; then
        missing_tools+=("docker")
    fi

    # Check for git (for secrets scanning)
    if ! command_exists git; then
        missing_tools+=("git")
    fi

    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_info "Please install missing tools before running security scans"
        exit 1
    fi

    # Install security-specific Python packages
    install_security_packages

    print_success "All required tools are available"
}

# Function to install security packages
install_security_packages() {
    print_info "Installing security scanning packages..."

    # Install bandit for code security analysis
    uv run pip install bandit[toml] safety detect-secrets 2>/dev/null || {
        print_warning "Failed to install some security packages, continuing with available tools"
    }
}

# Function to setup security directories
setup_directories() {
    print_header "📁 Setting up Security Directories"

    mkdir -p "$SECURITY_REPORTS_DIR"/{dependency,vulnerability,secrets,container,code,compliance}
    mkdir -p "$SECURITY_CONFIG_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"

    print_success "Security directories created"
}

# Function to run dependency vulnerability scanning
scan_dependencies() {
    print_header "🔍 Scanning Dependencies for Vulnerabilities"

    cd "$PROJECT_ROOT"

    echo "Running safety check for Python dependencies..."
    if uv run safety check --json --output "$SECURITY_REPORTS_DIR/dependency/safety_report.json" 2>/dev/null; then
        print_success "Safety scan completed successfully"
    else
        # Safety returns non-zero exit code when vulnerabilities are found
        print_warning "Safety scan found vulnerabilities (check report for details)"
    fi

    # Generate human-readable report
    uv run safety check --output "$SECURITY_REPORTS_DIR/dependency/safety_report.txt" 2>/dev/null || true

    echo "Checking for outdated packages..."
    uv run pip list --outdated --format=json > "$SECURITY_REPORTS_DIR/dependency/outdated_packages.json" 2>/dev/null || true

    log_message "Dependency vulnerability scan completed"
}

# Function to run code security analysis
scan_code_security() {
    print_header "🔒 Running Code Security Analysis"

    cd "$PROJECT_ROOT"

    echo "Running Bandit security analysis..."

    # Scan framework source code
    if [[ -d "src" ]]; then
        uv run bandit -r src/ -f json -o "$SECURITY_REPORTS_DIR/code/bandit_framework.json" 2>/dev/null || true
        uv run bandit -r src/ -f txt -o "$SECURITY_REPORTS_DIR/code/bandit_framework.txt" 2>/dev/null || true
    fi

    # Scan service templates
    if [[ -d "service" ]]; then
        uv run bandit -r service/ -f json -o "$SECURITY_REPORTS_DIR/code/bandit_templates.json" 2>/dev/null || true
        uv run bandit -r service/ -f txt -o "$SECURITY_REPORTS_DIR/code/bandit_templates.txt" 2>/dev/null || true
    fi

    # Scan examples
    if [[ -d "examples" ]]; then
        uv run bandit -r examples/ -f json -o "$SECURITY_REPORTS_DIR/code/bandit_examples.json" 2>/dev/null || true
        uv run bandit -r examples/ -f txt -o "$SECURITY_REPORTS_DIR/code/bandit_examples.txt" 2>/dev/null || true
    fi

    print_success "Bandit security analysis completed"

    # Custom security pattern checks for microservices
    echo "Running microservices-specific security checks..."
    check_microservices_patterns

    log_message "Code security analysis completed"
}

# Function to check microservices-specific security patterns
check_microservices_patterns() {
    local patterns_report="$SECURITY_REPORTS_DIR/code/microservices_security_patterns.txt"

    {
        echo "=== MICROSERVICES SECURITY PATTERNS ANALYSIS ==="
        echo "Generated: $(date)"
        echo ""

        echo "=== Authentication & Authorization ==="
        echo "JWT token usage: $(find . -name "*.py" -exec grep -l "jwt\|JWT" {} \; | wc -l) files"
        echo "OAuth implementations: $(find . -name "*.py" -exec grep -l "oauth\|OAuth" {} \; | wc -l) files"
        echo "API key references: $(find . -name "*.py" -exec grep -l "api_key\|API_KEY" {} \; | wc -l) files"
        echo ""

        echo "=== Service Communication Security ==="
        echo "TLS/SSL configurations: $(find . -name "*.py" -o -name "*.yaml" -o -name "*.json" | xargs grep -l "tls\|ssl\|https" | wc -l) files"
        echo "Certificate handling: $(find . -name "*.py" -exec grep -l "cert\|certificate" {} \; | wc -l) files"
        echo "mTLS references: $(find . -name "*.py" -o -name "*.yaml" | xargs grep -l "mtls\|mutual.*tls" | wc -l) files"
        echo ""

        echo "=== Input Validation ==="
        echo "Pydantic models: $(find . -name "*.py" -exec grep -l "pydantic\|BaseModel" {} \; | wc -l) files"
        echo "Input validation: $(find . -name "*.py" -exec grep -l "validate\|validator" {} \; | wc -l) files"
        echo "Schema validation: $(find . -name "*.py" -exec grep -l "schema\|Schema" {} \; | wc -l) files"
        echo ""

        echo "=== Rate Limiting & DDoS Protection ==="
        echo "Rate limiting: $(find . -name "*.py" -exec grep -l "rate.limit\|throttle" {} \; | wc -l) files"
        echo "Circuit breaker: $(find . -name "*.py" -exec grep -l "circuit.breaker\|CircuitBreaker" {} \; | wc -l) files"
        echo "Timeout configurations: $(find . -name "*.py" -o -name "*.yaml" | xargs grep -l "timeout" | wc -l) files"
        echo ""

        echo "=== Logging & Monitoring ==="
        echo "Structured logging: $(find . -name "*.py" -exec grep -l "logging\|logger" {} \; | wc -l) files"
        echo "Security logging: $(find . -name "*.py" -exec grep -l "security.*log\|audit.*log" {} \; | wc -l) files"
        echo "Metrics collection: $(find . -name "*.py" -exec grep -l "metrics\|prometheus" {} \; | wc -l) files"
        echo ""

        echo "=== Secret Management ==="
        echo "Environment variables: $(find . -name "*.py" -exec grep -l "os.environ\|getenv" {} \; | wc -l) files"
        echo "Secret references: $(find . -name "*.py" -o -name "*.yaml" | xargs grep -l "secret\|password\|key" | wc -l) files"
        echo "Vault integration: $(find . -name "*.py" -exec grep -l "vault\|hvac" {} \; | wc -l) files"
        echo ""

    } > "$patterns_report"

    print_success "Microservices security patterns analysis completed"
}

# Function to scan for secrets in code
scan_secrets() {
    print_header "🕵️ Scanning for Secrets and Sensitive Data"

    cd "$PROJECT_ROOT"

    echo "Running detect-secrets scan..."
    if command_exists detect-secrets || uv run detect-secrets --version >/dev/null 2>&1; then
        uv run detect-secrets scan --all-files > "$SECURITY_REPORTS_DIR/secrets/detect_secrets_baseline.json" 2>/dev/null || true
        print_success "detect-secrets scan completed"
    else
        print_info "detect-secrets not available, running manual pattern matching"
    fi

    # Custom secrets pattern scanning for microservices
    echo "Running microservices-specific secrets patterns..."

    {
        echo "=== MICROSERVICES SECRETS SCAN ==="
        echo "Generated: $(date)"
        echo ""

        echo "=== Database Credentials ==="
        find . -name "*.py" -o -name "*.yaml" -o -name "*.json" -o -name "*.env*" | xargs grep -n -E "(database_url|db_password|db_user|DATABASE_URL)" 2>/dev/null || echo "No database credentials found in plain text"
        echo ""

        echo "=== API Keys and Tokens ==="
        find . -name "*.py" -o -name "*.yaml" -o -name "*.json" -o -name "*.env*" | xargs grep -n -E "(api_key|API_KEY|access_token|ACCESS_TOKEN|bearer.*token)" 2>/dev/null || echo "No API keys found in plain text"
        echo ""

        echo "=== Cloud Provider Credentials ==="
        find . -name "*.py" -o -name "*.yaml" -o -name "*.json" -o -name "*.env*" | xargs grep -n -E "(aws_access_key|aws_secret|AZURE_CLIENT_SECRET|gcp_service_account)" 2>/dev/null || echo "No cloud credentials found in plain text"
        echo ""

        echo "=== JWT Secrets ==="
        find . -name "*.py" -o -name "*.yaml" -o -name "*.json" -o -name "*.env*" | xargs grep -n -E "(jwt_secret|JWT_SECRET|secret_key|SECRET_KEY)" 2>/dev/null || echo "No JWT secrets found in plain text"
        echo ""

        echo "=== Encryption Keys ==="
        find . -name "*.py" -o -name "*.yaml" -o -name "*.json" -o -name "*.env*" | xargs grep -n -E "(private_key|encryption_key|PRIVATE_KEY)" 2>/dev/null || echo "No encryption keys found in plain text"

    } > "$SECURITY_REPORTS_DIR/secrets/microservices_secrets_scan.txt"

    log_message "Secrets scanning completed"
}

# Function to scan container security
scan_containers() {
    print_header "🐳 Scanning Container Security"

    cd "$PROJECT_ROOT"

    if [[ -d "docker" ]] || find . -name "Dockerfile*" -o -name "*.Dockerfile" | grep -q .; then
        echo "Analyzing Docker configurations..."

        # Check for security best practices in Dockerfiles
        find . -name "*.Dockerfile" -o -name "Dockerfile*" | while read -r dockerfile; do
            echo "Analyzing $dockerfile..."

            # Custom security checks for Dockerfiles
            {
                echo "=== Security Analysis for $dockerfile ==="
                echo "Checking for security best practices..."

                # Check for running as root
                if ! grep -q "USER " "$dockerfile"; then
                    echo "WARNING: No USER instruction found - container may run as root"
                fi

                # Check for COPY vs ADD
                if grep -q "ADD " "$dockerfile"; then
                    echo "WARNING: ADD instruction found - consider using COPY instead"
                fi

                # Check for version pinning
                if grep -qE "FROM.*:latest" "$dockerfile"; then
                    echo "WARNING: Using 'latest' tag - consider pinning specific versions"
                fi

                # Check for distroless or minimal base images
                if grep -qE "FROM.*:(alpine|distroless|slim)" "$dockerfile"; then
                    echo "GOOD: Using minimal base image"
                else
                    echo "INFO: Consider using distroless or slim base images"
                fi

                # Check for health checks
                if grep -q "HEALTHCHECK" "$dockerfile"; then
                    echo "GOOD: Health check defined"
                else
                    echo "WARNING: No health check defined"
                fi

                # Check for secrets in build context
                if grep -qE "(password|secret|key|token)" "$dockerfile"; then
                    echo "WARNING: Potential secrets in Dockerfile"
                fi

                echo ""
            } >> "$SECURITY_REPORTS_DIR/container/dockerfile_analysis.txt"
        done

        print_success "Docker configuration analysis completed"
    else
        print_info "No Docker configurations found"
    fi

    log_message "Container security scan completed"
}

# Function to run compliance checks for microservices
run_compliance_checks() {
    print_header "📋 Running Microservices Security Compliance Checks"

    cd "$PROJECT_ROOT"

    local compliance_report="$SECURITY_REPORTS_DIR/compliance/microservices_compliance.txt"

    {
        echo "=== MICROSERVICES FRAMEWORK SECURITY COMPLIANCE REPORT ==="
        echo "Generated: $(date)"
        echo ""

        echo "=== OWASP Top 10 for Microservices ==="
        echo "□ A01:2021 – Broken Access Control"
        echo "  - Authentication middleware: $(find . -name "*.py" -exec grep -l "auth.*middleware\|authentication" {} \; | wc -l) files"
        echo "  - Authorization decorators: $(find . -name "*.py" -exec grep -l "@.*auth\|@.*permission" {} \; | wc -l) occurrences"
        echo ""

        echo "□ A02:2021 – Cryptographic Failures"
        echo "  - TLS/SSL configuration: $(find . -name "*.py" -o -name "*.yaml" | xargs grep -l "ssl\|tls" | wc -l) files"
        echo "  - Encryption libraries: $(find . -name "*.py" -exec grep -l "cryptography\|Fernet\|encrypt" {} \; | wc -l) files"
        echo ""

        echo "□ A03:2021 – Injection"
        echo "  - SQL injection prevention: $(find . -name "*.py" -exec grep -l "sqlalchemy\|asyncpg\|aiopg" {} \; | wc -l) files"
        echo "  - Input validation (Pydantic): $(find . -name "*.py" -exec grep -l "pydantic\|BaseModel" {} \; | wc -l) files"
        echo ""

        echo "=== Microservices-Specific Security ==="
        echo "□ Service-to-Service Communication"
        echo "  - mTLS implementation: $(find . -name "*.py" -o -name "*.yaml" | xargs grep -l "mtls\|mutual.*tls" | wc -l) files"
        echo "  - Service mesh configuration: $(find . -name "*.yaml" | xargs grep -l "istio\|linkerd" | wc -l) files"
        echo ""

        echo "□ API Gateway Security"
        echo "  - Rate limiting: $(find . -name "*.py" -exec grep -l "rate.limit\|throttle" {} \; | wc -l) files"
        echo "  - API versioning: $(find . -name "*.py" -exec grep -l "version\|v1\|v2" {} \; | wc -l) files"
        echo ""

        echo "□ Configuration Management"
        echo "  - Environment-based config: $(find . -name "*.yaml" | wc -l) config files"
        echo "  - Secret management: $(find . -name "*.py" -exec grep -l "getenv\|environ" {} \; | wc -l) files"
        echo ""

        echo "□ Observability & Monitoring"
        echo "  - Structured logging: $(find . -name "*.py" -exec grep -l "logging\|logger" {} \; | wc -l) files"
        echo "  - Metrics collection: $(find . -name "*.py" -exec grep -l "prometheus\|metrics" {} \; | wc -l) files"
        echo "  - Distributed tracing: $(find . -name "*.py" -exec grep -l "opentelemetry\|jaeger\|trace" {} \; | wc -l) files"
        echo ""

        echo "□ Container Security"
        echo "  - Non-root user: $(find . -name "*Dockerfile*" -exec grep -l "USER " {} \; | wc -l) Dockerfiles"
        echo "  - Minimal base images: $(find . -name "*Dockerfile*" -exec grep -l "alpine\|distroless" {} \; | wc -l) Dockerfiles"
        echo "  - Health checks: $(find . -name "*Dockerfile*" -exec grep -l "HEALTHCHECK" {} \; | wc -l) Dockerfiles"
        echo ""

        echo "□ Deployment Security"
        echo "  - Resource limits: $(find . -name "*.yaml" | xargs grep -l "limits:\|requests:" | wc -l) files"
        echo "  - Security contexts: $(find . -name "*.yaml" | xargs grep -l "securityContext" | wc -l) files"
        echo "  - Network policies: $(find . -name "*.yaml" | xargs grep -l "NetworkPolicy" | wc -l) files"

    } > "$compliance_report"

    print_success "Microservices compliance checklist generated"
    log_message "Compliance checks completed"
}

# Function to generate security summary report
generate_security_report() {
    print_header "📊 Generating Security Summary Report"

    local summary_report="$SECURITY_REPORTS_DIR/security_summary.md"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    {
        echo "# Microservices Framework Security Scan Summary"
        echo ""
        echo "**Generated:** $timestamp"
        echo "**Framework:** Marty Microservices Framework"
        echo "**Scan Type:** Comprehensive Security Assessment"
        echo ""

        echo "## 🔍 Scan Results Overview"
        echo ""

        # Dependency vulnerabilities
        if [[ -f "$SECURITY_REPORTS_DIR/dependency/safety_report.txt" ]]; then
            local vuln_count=$(grep -c "vulnerability" "$SECURITY_REPORTS_DIR/dependency/safety_report.txt" 2>/dev/null || echo "0")
            echo "- **Dependency Vulnerabilities:** $vuln_count found"
        fi

        # Code security issues
        if [[ -f "$SECURITY_REPORTS_DIR/code/bandit_framework.txt" ]]; then
            local code_issues=$(grep -c "Issue" "$SECURITY_REPORTS_DIR/code/bandit_framework.txt" 2>/dev/null || echo "0")
            echo "- **Code Security Issues:** $code_issues found"
        fi

        # Secrets detection
        if [[ -f "$SECURITY_REPORTS_DIR/secrets/detect_secrets_baseline.json" ]]; then
            local secrets_count=$(python3 -c "import json; print(len(json.load(open('$SECURITY_REPORTS_DIR/secrets/detect_secrets_baseline.json', 'r')).get('results', {})))" 2>/dev/null || echo "0")
            echo "- **Potential Secrets:** $secrets_count detected"
        fi

        echo ""
        echo "## 🏗️ Framework Components Analyzed"
        echo ""
        echo "- **Core Framework:** \`src/\` directory"
        echo "- **Service Templates:** \`service/\` directory"
        echo "- **Examples:** \`examples/\` directory"
        echo "- **Security Modules:** \`security/\` directory"
        echo "- **Container Configurations:** Docker files"
        echo "- **Kubernetes Manifests:** \`k8s/\` directory"
        echo ""

        echo "## 📁 Report Files Generated"
        echo ""
        find "$SECURITY_REPORTS_DIR" -type f -name "*.txt" -o -name "*.json" -o -name "*.md" | while read -r file; do
            local rel_path=${file#$PROJECT_ROOT/}
            echo "- \`$rel_path\`"
        done

        echo ""
        echo "## 🚨 Critical Security Recommendations for Microservices"
        echo ""
        echo "1. **Service-to-Service Security:** Implement mTLS for all service communication"
        echo "2. **API Gateway Protection:** Use rate limiting, authentication, and input validation"
        echo "3. **Container Security:** Use non-root users, minimal base images, and regular vulnerability scanning"
        echo "4. **Secret Management:** Implement proper secrets management (Kubernetes secrets, Vault)"
        echo "5. **Network Segmentation:** Use network policies to restrict inter-service communication"
        echo "6. **Observability:** Implement comprehensive logging, monitoring, and distributed tracing"
        echo "7. **Input Validation:** Use strong input validation (Pydantic models) for all APIs"
        echo "8. **Configuration Security:** Externalize configuration and use environment-specific settings"
        echo ""

        echo "## 🔧 Framework-Specific Next Steps"
        echo ""
        echo "1. Review security reports in \`reports/security/\`"
        echo "2. Update service templates with security best practices"
        echo "3. Implement security middleware in framework core"
        echo "4. Add security validation to service generator"
        echo "5. Create security testing templates"
        echo "6. Update documentation with security guidelines"
        echo ""

        echo "## 📚 Security Resources"
        echo ""
        echo "- [OWASP Microservices Security](https://owasp.org/www-project-microservices-security/)"
        echo "- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)"
        echo "- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)"
        echo "- [Docker Security Best Practices](https://docs.docker.com/engine/security/)"

    } > "$summary_report"

    print_success "Security summary report generated: $summary_report"
}

# Function to display scan results
display_results() {
    print_header "📊 Security Scan Results Summary"

    echo "Security reports have been generated in:"
    echo "  📁 $SECURITY_REPORTS_DIR"
    echo ""

    echo "Key reports to review:"
    echo "  🔍 Dependency vulnerabilities: dependency/"
    echo "  🔒 Code security analysis: code/"
    echo "  🕵️ Secrets detection: secrets/"
    echo "  🐳 Container security: container/"
    echo "  📋 Microservices compliance: compliance/"
    echo ""

    if [[ -f "$SECURITY_REPORTS_DIR/security_summary.md" ]]; then
        print_info "View complete summary: reports/security/security_summary.md"
    fi

    print_warning "⚠️  IMPORTANT: Review all reports and update framework templates with security fixes"
}

# Main execution function
main() {
    local action="${1:-full}"

    print_header "🛡️ Microservices Framework Security Scanner"
    echo "Starting comprehensive security assessment for microservices framework..."
    echo ""

    # Initialize
    check_dependencies
    setup_directories

    log_message "Security scan started - action: $action"

    case "$action" in
        "deps"|"dependencies")
            scan_dependencies
            ;;
        "code")
            scan_code_security
            ;;
        "secrets")
            scan_secrets
            ;;
        "containers")
            scan_containers
            ;;
        "compliance")
            run_compliance_checks
            ;;
        "full"|*)
            scan_dependencies
            scan_code_security
            scan_secrets
            scan_containers
            run_compliance_checks
            generate_security_report
            ;;
    esac

    display_results
    log_message "Security scan completed - action: $action"

    print_success "Microservices Framework security assessment complete! 🎉"
    print_info "Review reports in: $SECURITY_REPORTS_DIR"
}

# Show help if requested
if [[ "${1:-}" == "help" || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Microservices Framework Security Scanner"
    echo "======================================"
    echo ""
    echo "Usage: $0 [ACTION]"
    echo ""
    echo "Actions:"
    echo "  full         - Run complete security assessment (default)"
    echo "  deps         - Scan dependencies for vulnerabilities"
    echo "  code         - Run code security analysis"
    echo "  secrets      - Scan for secrets and sensitive data"
    echo "  containers   - Analyze container security"
    echo "  compliance   - Generate microservices compliance checklist"
    echo "  help         - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0           # Run full security assessment"
    echo "  $0 deps      # Check dependencies only"
    echo "  $0 secrets   # Scan for secrets only"
    echo ""
    echo "Framework Components Scanned:"
    echo "  - Core framework (src/)"
    echo "  - Service templates (service/)"
    echo "  - Security modules (security/)"
    echo "  - Container configurations"
    echo "  - Kubernetes manifests"
    exit 0
fi

# Run main function
main "$@"
