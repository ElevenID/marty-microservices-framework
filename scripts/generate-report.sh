#!/bin/bash

# E2E Test Report Generator
# Generates detailed HTML and JSON reports from test results

set -e

# Configuration
REPORT_DIR="/tmp/mmf-e2e-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
HTML_REPORT="$REPORT_DIR/e2e-report-$TIMESTAMP.html"
JSON_REPORT="$REPORT_DIR/e2e-report-$TIMESTAMP.json"

# Test data (this would normally be passed from the test runner)
TEST_RESULTS=()
SYSTEM_INFO=""
PERFORMANCE_DATA=""

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Function to add test result
add_test_result() {
    local test_name="$1"
    local status="$2"
    local duration="$3"
    local message="$4"
    local timestamp="$5"

    TEST_RESULTS+=("$test_name|$status|$duration|$message|$timestamp")
}

# Function to collect system information
collect_system_info() {
    local cluster_name="$1"

    SYSTEM_INFO=$(cat << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "cluster_name": "$cluster_name",
  "kubectl_version": "$(kubectl version --client -o json 2>/dev/null | jq -r '.clientVersion.gitVersion' || echo 'unknown')",
  "kind_version": "$(kind --version 2>/dev/null | cut -d' ' -f3 || echo 'unknown')",
  "docker_version": "$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo 'unknown')",
  "os": "$(uname -s)",
  "arch": "$(uname -m)"
}
EOF
)
}

# Function to collect performance data
collect_performance_data() {
    local namespace="$1"
    local service_name="$2"

    # Get pod resource usage
    local pod_resources=""
    if kubectl top pods -n "$namespace" -l app="$service_name" >/dev/null 2>&1; then
        pod_resources=$(kubectl top pods -n "$namespace" -l app="$service_name" --no-headers | awk '{print $2, $3}' | paste -sd ',' -)
    else
        pod_resources="metrics-server-not-available"
    fi

    # Get pod count and status
    local pod_count=$(kubectl get pods -n "$namespace" -l app="$service_name" --no-headers | wc -l)
    local running_pods=$(kubectl get pods -n "$namespace" -l app="$service_name" --field-selector=status.phase=Running --no-headers | wc -l)

    PERFORMANCE_DATA=$(cat << EOF
{
  "pod_count": $pod_count,
  "running_pods": $running_pods,
  "resource_usage": "$pod_resources",
  "service_endpoints": $(kubectl get endpoints -n "$namespace" "$service_name" -o json 2>/dev/null | jq '.subsets[0].addresses | length' || echo '0')
}
EOF
)
}

# Function to generate JSON report
generate_json_report() {
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    local test_results_json="["

    for result in "${TEST_RESULTS[@]}"; do
        IFS='|' read -r name status duration message timestamp <<< "$result"
        total_tests=$((total_tests + 1))

        if [ "$status" = "PASS" ]; then
            passed_tests=$((passed_tests + 1))
        else
            failed_tests=$((failed_tests + 1))
        fi

        if [ $total_tests -gt 1 ]; then
            test_results_json+=","
        fi

        test_results_json+=$(cat << EOF
    {
      "name": "$name",
      "status": "$status",
      "duration": "$duration",
      "message": "$message",
      "timestamp": "$timestamp"
    }
EOF
)
    done

    test_results_json+="]"

    cat > "$JSON_REPORT" << EOF
{
  "summary": {
    "total_tests": $total_tests,
    "passed_tests": $passed_tests,
    "failed_tests": $failed_tests,
    "success_rate": $(echo "scale=2; $passed_tests * 100 / $total_tests" | bc -l 2>/dev/null || echo "0"),
    "generated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  },
  "system_info": $SYSTEM_INFO,
  "performance": $PERFORMANCE_DATA,
  "test_results": $test_results_json
}
EOF
}

# Function to generate HTML report
generate_html_report() {
    local json_data
    json_data=$(cat "$JSON_REPORT")

    local total_tests=$(echo "$json_data" | jq -r '.summary.total_tests')
    local passed_tests=$(echo "$json_data" | jq -r '.summary.passed_tests')
    local failed_tests=$(echo "$json_data" | jq -r '.summary.failed_tests')
    local success_rate=$(echo "$json_data" | jq -r '.summary.success_rate')

    cat > "$HTML_REPORT" << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MMF E2E Test Report - $TIMESTAMP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
        .metric h3 { margin: 0 0 10px 0; color: #333; }
        .metric .value { font-size: 2em; font-weight: bold; }
        .passed { color: #28a745; }
        .failed { color: #dc3545; }
        .total { color: #007bff; }
        .success-rate { color: #6f42c1; }
        .test-results { margin: 20px 0; }
        .test-item { background: white; border: 1px solid #ddd; border-radius: 4px; margin: 10px 0; padding: 15px; }
        .test-item.pass { border-left: 4px solid #28a745; }
        .test-item.fail { border-left: 4px solid #dc3545; }
        .test-name { font-weight: bold; margin-bottom: 5px; }
        .test-message { color: #666; font-style: italic; }
        .system-info { background: #e9ecef; padding: 15px; border-radius: 4px; margin: 20px 0; }
        .system-info h3 { margin-top: 0; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>MMF E2E Test Report</h1>
            <p>Generated on $(date)</p>
        </div>

        <div class="summary">
            <div class="metric">
                <h3>Total Tests</h3>
                <div class="value total">$total_tests</div>
            </div>
            <div class="metric">
                <h3>Passed</h3>
                <div class="value passed">$passed_tests</div>
            </div>
            <div class="metric">
                <h3>Failed</h3>
                <div class="value failed">$failed_tests</div>
            </div>
            <div class="metric">
                <h3>Success Rate</h3>
                <div class="value success-rate">$success_rate%</div>
            </div>
        </div>

        <div class="test-results">
            <h2>Test Results</h2>
EOF

    # Add test results
    for result in "${TEST_RESULTS[@]}"; do
        IFS='|' read -r name status duration message timestamp <<< "$result"
        local css_class="pass"
        local status_icon="✅"

        if [ "$status" != "PASS" ]; then
            css_class="fail"
            status_icon="❌"
        fi

        cat >> "$HTML_REPORT" << EOF
            <div class="test-item $css_class">
                <div class="test-name">$status_icon $name</div>
                <div class="test-message">$message</div>
                <div style="font-size: 0.8em; color: #999;">Duration: ${duration}s | Time: $timestamp</div>
            </div>
EOF
    done

    cat >> "$HTML_REPORT" << EOF
        </div>

        <div class="system-info">
            <h3>System Information</h3>
            <pre>$(echo "$SYSTEM_INFO" | jq '.')</pre>
        </div>

        <div class="system-info">
            <h3>Performance Data</h3>
            <pre>$(echo "$PERFORMANCE_DATA" | jq '.')</pre>
        </div>

        <div class="footer">
            <p>MMF End-to-End Test Report | Generated by MMF Test Framework</p>
        </div>
    </div>
</body>
</html>
EOF
}

# Main function
main() {
    local cluster_name="${1:-mmf-e2e-test}"
    local namespace="${2:-mmf-system}"
    local service_name="${3:-identity-service}"

    echo -e "${BLUE}📊 Generating E2E test report...${NC}"

    # Create report directory
    mkdir -p "$REPORT_DIR"

    # Collect system information
    collect_system_info "$cluster_name"

    # Collect performance data
    collect_performance_data "$namespace" "$service_name"

    # Example test results (in real implementation, this would come from test runner)
    add_test_result "Health Check" "PASS" "0.5" "Service is healthy" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    add_test_result "Authentication" "PASS" "1.2" "Authentication successful" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    add_test_result "Invalid Credentials" "PASS" "0.8" "Correctly rejected invalid credentials" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    # Generate reports
    generate_json_report
    generate_html_report

    echo -e "${GREEN}✅ Reports generated:${NC}"
    echo -e "   JSON: $JSON_REPORT"
    echo -e "   HTML: $HTML_REPORT"

    # Open HTML report if on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${BLUE}🔍 Opening HTML report...${NC}"
        open "$HTML_REPORT"
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
