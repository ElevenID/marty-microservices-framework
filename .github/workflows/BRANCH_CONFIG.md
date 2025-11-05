# 🌿 MMF Workflow Branch Configuration

## Updated Branch Triggers

All MMF workflows have been updated to trigger on **`main`** and **`dev`** branches as requested.

### 📋 Current Configuration

| Workflow | Trigger Type | Branches | Description |
|----------|-------------|----------|-------------|
| **MMF PR Validation** | `pull_request` | `main`, `dev` | Validates PRs to main/dev |
| **MMF Comprehensive E2E** | `pull_request` | `main`, `dev` | Full testing for main/dev PRs |
| **MMF E2E Tests** | `push` + `pull_request` | `main`, `dev` | Tests on push to main/dev + PRs |
| **MMF Quick E2E** | `workflow_dispatch` | *Manual only* | On-demand testing |

### 🚦 Trigger Behavior

#### For `main` branch:
- ✅ Push to `main` → Runs **MMF E2E Tests**
- ✅ PR to `main` → Runs **MMF PR Validation** + **MMF Comprehensive E2E** + **MMF E2E Tests**

#### For `dev` branch:
- ✅ Push to `dev` → Runs **MMF E2E Tests**
- ✅ PR to `dev` → Runs **MMF PR Validation** + **MMF Comprehensive E2E** + **MMF E2E Tests**

#### Manual Testing:
- 🔧 **MMF Quick E2E** → Available anytime via workflow dispatch

### 📁 Path Filtering

All automatic workflows only run when these paths change:
- `mmf/**` - Your MMF microservices code
- `tests/**` - Testing infrastructure
- `pyproject.toml` - Python dependencies
- `requirements.txt` - Package requirements

### 🎯 Recommended Workflow

1. **Development**: Work in feature branches → create PR to `dev`
2. **Integration**: Merge `dev` → `main` when ready for release
3. **Testing**: All workflows validate MMF changes automatically
4. **Debugging**: Use manual **MMF Quick E2E** for focused testing

### ✅ Summary

Your workflows now support:
- **`main`** - Production/release branch
- **`dev`** - Development/integration branch
- **Manual dispatch** - On-demand testing
- **Path filtering** - Only MMF-related changes trigger workflows

**Ready for your main/dev branch workflow! 🚀**
