# Dependency Analysis Tools

This directory contains improved tools for analyzing and maintaining clean dependency architecture in the Marty Microservices Framework.

## Tools Overview

### 1. `dependency_analyzer.py` - Main Analysis Tool

**The primary tool for developers to analyze project dependencies**

```bash
# Quick analysis (focuses on changed files)
python tools/dependency_analyzer.py --quick

# Full comprehensive analysis
python tools/dependency_analyzer.py --full

# Focus on circular dependencies only
python tools/dependency_analyzer.py --circular

# Focus on coupling analysis
python tools/dependency_analyzer.py --coupling --threshold 10

# Export results
python tools/dependency_analyzer.py --full --export json
python tools/dependency_analyzer.py --coupling --export md --output report.md
```

**Features:**

- ✅ Real-time analysis of current codebase
- ✅ Smart caching (auto-refresh after 5 minutes)
- ✅ Multiple analysis modes (quick/full/focused)
- ✅ Export to JSON, CSV, or Markdown
- ✅ Configurable coupling thresholds
- ✅ Actionable recommendations

### 2. `check_circular_deps_fast.py` - Pre-commit Hook

**Fast circular dependency checker for git pre-commit hooks**

```bash
# Check changed files for circular dependencies
python tools/check_circular_deps_fast.py
```

**Features:**

- ✅ Only analyzes changed files (fast)
- ✅ Includes immediate dependencies
- ✅ Blocks commits with circular dependencies
- ✅ Provides specific fix recommendations
- ✅ Integrated with pre-commit framework

### 3. `circular_deps_detailed.py` - Detailed Analysis

**Comprehensive circular dependency analysis with architectural insights**

```bash
# Detailed analysis with fresh data
python tools/circular_deps_detailed.py

# Force refresh of analysis data
python tools/circular_deps_detailed.py --force
```

**Features:**

- ✅ Auto-refreshes stale cached data
- ✅ Detailed architectural recommendations
- ✅ Coupling analysis and refactoring plans
- ✅ Module relationship mapping
- ✅ Tier-based priority recommendations

### 4. `analyze_project_imports.py` - Core Analysis Engine

**The foundational import analysis engine**

```bash
# Generate fresh analysis
python tools/analyze_project_imports.py

# Force regeneration even with recent cache
python tools/analyze_project_imports.py --force

# Quiet mode (minimal output)
python tools/analyze_project_imports.py --quiet
```

**Features:**

- ✅ Real-time import parsing
- ✅ Intelligent caching system
- ✅ Comprehensive module statistics
- ✅ Architectural layer identification
- ✅ Parse error tracking and reporting

## Pre-commit Integration

The tools are integrated into the pre-commit pipeline:

```yaml
# In .pre-commit-config.yaml
- id: check-circular-dependencies
  name: Check for Circular Dependencies
  entry: python3 tools/check_circular_deps_fast.py
  language: system
  files: ^src/marty_msf/.*\.py$
  exclude: ^(tests/.*|examples/.*|tools/.*|scripts/.*)\.py$
  require_serial: true
  pass_filenames: false
  stages: [pre-commit]
```

## Analysis Cache System

The tools use an intelligent caching system:

- **Cache File**: `internal_import_analysis.json`
- **Auto-refresh**: After 5 minutes of cache age
- **Force Refresh**: Use `--force` flag on any tool
- **Cache Metadata**: Includes generation timestamp and error tracking

## Coupling Thresholds

Default coupling score interpretations:

- **🚨 Critical (>15)**: Immediate refactoring required
- **⚠️ High (10-15)**: Should be refactored soon
- **🔶 Medium (5-10)**: Monitor and consider splitting
- **✅ Acceptable (≤5)**: Good architectural health

## Recommendations Engine

The tools provide specific, actionable recommendations:

### For Circular Dependencies

- Extract shared interfaces to common modules
- Use dependency injection patterns
- Implement lazy loading (imports inside functions)
- Create abstraction layers
- Consider event-driven architecture

### For High Coupling

- Apply Single Responsibility Principle
- Extract shared functionality to utilities
- Use interfaces and abstract base classes
- Implement dependency inversion
- Consider composition over inheritance

## Usage Patterns

### For Daily Development

```bash
# Quick check before committing
python tools/dependency_analyzer.py --quick

# Weekly architectural health check
python tools/dependency_analyzer.py --full --export md
```

### For Code Reviews

```bash
# Focus on specific concerns
python tools/dependency_analyzer.py --circular
python tools/dependency_analyzer.py --coupling --threshold 8
```

### For Architectural Planning

```bash
# Comprehensive analysis with export
python tools/dependency_analyzer.py --full --export json --output architecture_analysis.json
```

## Error Handling

The tools gracefully handle:

- ✅ Syntax errors in Python files
- ✅ Unicode encoding issues
- ✅ Missing or corrupted cache files
- ✅ Git repository issues
- ✅ Network connectivity problems

Parse errors are tracked and reported in the analysis metadata.

## Performance

- **Quick Analysis**: ~1-2 seconds (changed files only)
- **Full Analysis**: ~5-10 seconds (all 200+ modules)
- **Cache Hit**: ~0.1 seconds (when cache is fresh)
- **Pre-commit Check**: ~1-3 seconds (optimized for speed)

## Output Formats

### JSON Export

```json
{
  "summary": {
    "total_modules": 208,
    "circular_dependencies_count": 0,
    "highly_coupled_modules_count": 10
  },
  "recommendations": [...],
  "metadata": {
    "generated_at": "2025-10-21T15:15:41",
    "analysis_type": "real_time"
  }
}
```

### Markdown Export

Clean, readable reports suitable for documentation or code reviews.

### CSV Export

Module statistics suitable for spreadsheet analysis or further data processing.

## Continuous Integration

The tools support CI/CD workflows:

```bash
# In CI pipeline
python tools/dependency_analyzer.py --quick
if [ $? -eq 1 ]; then
  echo "Circular dependencies detected - failing build"
  exit 1
fi
```

## Troubleshooting

### Common Issues

1. **"Command not found" error**

   ```bash
   chmod +x tools/*.py
   ```

2. **Stale cache issues**

   ```bash
   python tools/dependency_analyzer.py --quick --force
   ```

3. **Git repository issues**

   ```bash
   git status  # Ensure you're in a git repository
   ```

4. **Import path issues**

   ```bash
   # Run from project root directory
   cd /path/to/marty-microservices-framework
   ```

## Future Enhancements

Planned improvements:

- 🔄 Watch mode for continuous monitoring
- 📊 Trend analysis over time
- 🌐 Web-based dependency visualization
- 📈 Integration with code quality metrics
- 🎯 Custom rule definition system

---

These improved tools provide comprehensive, real-time dependency analysis that helps maintain clean architecture and prevents the introduction of circular dependencies through automated pre-commit checks.
