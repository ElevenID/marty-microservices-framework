# Enhanced GitHub Workflows for MMF Testing

This document describes the enhanced GitHub Actions workflows that leverage the new MMF unified testing framework with KIND (Kubernetes in Docker) for comprehensive e2e testing.

## 🚀 Available Workflows

### 1. PR Validation (`pr-validation.yml`)
**Trigger:** Automatic on PR creation/updates
**Purpose:** Quick validation for all PRs

**Features:**
- ✅ Updated to use `tests/run_tests.sh` unified runner
- ✅ Skips draft PRs (configurable)
- ✅ Runs unit, contract, e2e, performance, and security tests
- ✅ Uses KIND for e2e testing
- ✅ Matrix strategy for parallel execution
- ✅ Automatic PR comments with results

**Test Categories:**
- **Quick Validation:** Unit tests + code quality
- **Contract Tests:** API contract validation
- **E2E Tests:** Quick and smoke test modes
- **Performance:** Baseline performance checks
- **Security:** Security validation tests

### 2. Comprehensive E2E Testing (`comprehensive-e2e.yml`)
**Trigger:** PR events + manual dispatch
**Purpose:** Full-scale testing with all categories

**Features:**
- ✅ Intelligent test mode selection
- ✅ Full test matrix (e2e, integration, performance, security, chaos)
- ✅ KIND-based infrastructure setup
- ✅ Advanced artifact collection
- ✅ Chaos engineering support
- ✅ Comprehensive reporting

**Test Modes:**
- **Quick:** `./tests/run_tests.sh --{category} --quick --verbose`
- **Smoke:** `./tests/run_tests.sh --{category} --smoke --verbose`
- **Comprehensive:** `./tests/run_tests.sh --{category} --verbose`
- **Chaos:** `./tests/run_tests.sh --{category} --chaos --verbose`

**Mode Selection:**
- Manual: Via workflow dispatch input
- Automatic: PR title tags like `[quick]` or `[chaos]`
- Default: Comprehensive mode

### 3. Quick E2E with KIND (`quick-e2e-kind.yml`)
**Trigger:** Manual dispatch only
**Purpose:** On-demand E2E testing

**Features:**
- ✅ Manual test scope selection (smoke/quick/full)
- ✅ PR-specific testing (by number)
- ✅ Debug mode support
- ✅ Focused on speed and simplicity
- ✅ Minimal resource usage

## 🛠️ Infrastructure Components

### KIND (Kubernetes in Docker)
- **Version:** v0.20.0
- **Usage:** All E2E and integration tests
- **Features:**
  - Automatic cluster creation/cleanup
  - Multi-cluster support for advanced scenarios
  - Container image pre-loading for speed

### Python Environment
- **Version:** 3.11
- **Package Manager:** UV (fast Python package manager)
- **Dependencies:** Installed via `uv sync --group dev`

### Container Infrastructure
- **Docker Buildx:** For multi-platform builds
- **kubectl:** v1.28.0 for Kubernetes interaction
- **Registry:** Local KIND registry for test images

## 📊 Test Integration

### Unified Test Runner Integration
All workflows now use the `tests/run_tests.sh` script with standardized arguments:

```bash
# Unit tests
./tests/run_tests.sh --unit --verbose

# Contract tests
./tests/run_tests.sh --contract --verbose

# E2E tests with modes
./tests/run_tests.sh --e2e --quick --verbose
./tests/run_tests.sh --e2e --smoke --verbose
./tests/run_tests.sh --e2e --verbose

# Performance tests
./tests/run_tests.sh --performance --quick --verbose

# Security tests
./tests/run_tests.sh --security --verbose

# Chaos engineering
./tests/run_tests.sh --chaos --verbose
```

### Test Categories Supported
1. **Unit Tests:** Fast, isolated component tests
2. **Integration Tests:** Service integration validation
3. **Contract Tests:** API contract verification
4. **E2E Tests:** Full system testing with KIND
5. **Performance Tests:** Load and performance validation
6. **Security Tests:** Security vulnerability scanning
7. **Chaos Tests:** Resilience and failure testing

## 🎯 Workflow Selection Guide

### For Regular Development
- **Use:** `pr-validation.yml` (automatic)
- **When:** Every PR creation/update
- **Duration:** ~15-25 minutes
- **Coverage:** Essential validation

### For Comprehensive Testing
- **Use:** `comprehensive-e2e.yml` (automatic + manual)
- **When:** Major changes, pre-release, or manual testing
- **Duration:** ~45-90 minutes (depending on mode)
- **Coverage:** Full test suite

### For Quick Debugging
- **Use:** `quick-e2e-kind.yml` (manual only)
- **When:** Debugging specific E2E issues
- **Duration:** ~10-30 minutes
- **Coverage:** Focused E2E testing

## 🔧 Configuration Options

### Environment Variables
```yaml
PYTHON_VERSION: "3.11"      # Python runtime version
KIND_VERSION: "v0.20.0"     # KIND version for K8s clusters
KUBECTL_VERSION: "v1.28.0"  # kubectl client version
DOCKER_BUILDKIT: 1          # Enable Docker BuildKit
```

### Timeout Settings
- **PR Validation:** 10-25 minutes per job
- **Comprehensive E2E:** 45 minutes for e2e/integration
- **Quick E2E:** 30 minutes total
- **Performance:** 20 minutes
- **Security:** 15 minutes
- **Chaos:** 30 minutes

### Artifact Retention
- **PR Validation:** 3-7 days
- **Comprehensive E2E:** 7 days
- **Quick E2E:** 3 days

## 📋 Workflow Features

### Smart Execution
- **Draft PR Skipping:** Avoids running expensive tests on draft PRs
- **Fail-Fast Strategy:** Configurable for different scenarios
- **Parallel Execution:** Matrix strategies for speed
- **Resource Cleanup:** Automatic cleanup of KIND clusters and Docker resources

### Reporting & Notifications
- **GitHub Step Summary:** Rich markdown summaries in workflow results
- **PR Comments:** Automatic comments with test results
- **Artifact Upload:** Comprehensive artifact collection
- **Status Badges:** Integration with GitHub status checks

### Error Handling
- **Graceful Failures:** Tests continue even if some categories fail
- **Resource Cleanup:** Always runs regardless of test outcomes
- **Debug Support:** Optional debug logging for troubleshooting
- **Retry Logic:** Built into individual test runners

## 🚦 Usage Examples

### Triggering Specific Test Modes

**Quick Mode (via PR title):**
```
feat: add new service [quick]
```

**Chaos Mode (via PR title):**
```
refactor: improve resilience [chaos]
```

**Manual Comprehensive Testing:**
```bash
# Go to Actions tab → Comprehensive E2E Testing → Run workflow
# Select: test_mode = "comprehensive"
```

**Quick E2E Debug Session:**
```bash
# Go to Actions tab → Quick E2E with KIND → Run workflow
# Select: test_scope = "smoke", debug_mode = true
```

## 🔄 Migration from Old Workflows

### Updated References
The workflows have been updated to use the new test structure:

**Old:**
```bash
./deploy/e2e-test.sh
./scripts/test-e2e.sh -m quick -v
pytest tests/unit/ -v --tb=short
```

**New:**
```bash
./tests/run_tests.sh --e2e --verbose
./tests/run_tests.sh --e2e --quick --verbose
./tests/run_tests.sh --unit --verbose
```

### Benefits of Migration
- ✅ **Unified Interface:** Single test runner for all categories
- ✅ **Better Organization:** Clear separation of test types
- ✅ **Enhanced Flexibility:** Support for different test modes
- ✅ **Improved Debugging:** Better logging and artifact collection
- ✅ **KIND Integration:** Consistent Kubernetes testing environment
- ✅ **Scalable Architecture:** Easy to add new test categories

## 📚 Next Steps

1. **Monitor Workflow Performance:** Track execution times and optimize as needed
2. **Add Test Categories:** Extend with additional test types (accessibility, mobile, etc.)
3. **Enhanced Reporting:** Integrate with external reporting tools
4. **Security Integration:** Add SAST/DAST scanning tools
5. **Performance Baselines:** Establish performance benchmarks and regression detection

---

**🤖 Generated by MMF GitHub Workflows Enhancement**
*Last Updated: November 2025*
