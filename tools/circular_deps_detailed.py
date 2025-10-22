#!/usr/bin/env python3
"""
Detailed analysis of circular dependencies with specific recommendations.
Can work with cached data or perform real-time analysis.
"""
import ast
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def ensure_fresh_analysis(force_refresh: bool = False) -> dict:
    """Ensure we have fresh analysis data, regenerating if needed."""
    cache_file = Path('internal_import_analysis.json')

    # Check if we need to regenerate
    needs_refresh = force_refresh or not cache_file.exists()

    if not needs_refresh:
        try:
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age > 300:  # 5 minutes
                needs_refresh = True
                print(f"🔄 Analysis cache is {cache_age:.0f}s old, refreshing...")
        except (OSError, ValueError):
            needs_refresh = True

    if needs_refresh:
        print("🔍 Running fresh import analysis...")
        try:
            subprocess.run(
                [sys.executable, 'tools/analyze_project_imports.py', '--quiet'],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running analysis: {e}")
            print(f"Output: {e.stdout}")
            print(f"Error: {e.stderr}")
            sys.exit(1)

    # Load the data
    try:
        with open(cache_file, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading analysis data: {e}")
        sys.exit(1)


def analyze_specific_circular_deps(data: dict):
    """Analyze the specific circular dependencies found."""

    print("="*100)
    print("DETAILED CIRCULAR DEPENDENCY ANALYSIS")
    print("="*100)

    circular_deps = data.get('circular_dependencies', [])

    if not circular_deps:
        print("\n🎉 NO CIRCULAR DEPENDENCIES FOUND!")
        print("   Your codebase has clean dependency architecture.")

        # Show metadata if available
        if 'metadata' in data:
            meta = data['metadata']
            if 'generated_at' in meta:
                generated_time = datetime.fromisoformat(meta['generated_at'].replace('Z', '+00:00'))
                print(f"   Analysis generated: {generated_time.strftime('%Y-%m-%d %H:%M:%S')}")
        return

    for i, cycle in enumerate(circular_deps, 1):
        print(f"\n🔄 CIRCULAR DEPENDENCY #{i}:")
        print(f"   Path: {' → '.join(cycle)}")

        # Provide specific recommendations for each cycle
        cycle_modules = cycle[:-1]  # Remove duplicate last element

        if 'plugins' in ' '.join(cycle_modules):
            print("   📋 RECOMMENDATION:")
            print("   - Move shared plugin interfaces to marty_msf.framework.plugins.interfaces")
            print("   - Use dependency injection for plugin registration")
            print("   - Consider plugin registry pattern")

        elif 'resilience' in ' '.join(cycle_modules):
            print("   📋 RECOMMENDATION:")
            print("   - Extract common resilience interfaces to a separate module")
            print("   - Use event-driven communication between resilience components")
            print("   - Consider manager pattern with clear responsibilities")

        elif 'messaging' in ' '.join(cycle_modules):
            print("   📋 RECOMMENDATION:")
            print("   - Separate message patterns from message core functionality")
            print("   - Use abstract base classes for messaging components")
            print("   - Consider message broker pattern")

        elif 'security' in ' '.join(cycle_modules):
            print("   📋 RECOMMENDATION:")
            print("   - Extract security interfaces and protocols")
            print("   - Use dependency inversion for security components")
            print("   - Consider security context pattern")

        else:
            print("   📋 RECOMMENDATION:")
            print("   - Extract shared interfaces and abstract classes")
            print("   - Use dependency injection or factory patterns")
            print("   - Consider event-driven architecture")

        print("   💡 BREAKING STRATEGIES:")
        if len(cycle_modules) == 2:
            print("   - Create an interface module that both can import")
            print("   - Use dependency injection to resolve at runtime")
            print("   - Move shared types to a common module")
        else:
            print("   - Identify the core module and make others depend on it")
            print("   - Extract shared functionality to a lower-level module")
            print("   - Use events/signals for loose coupling")

def create_dependency_graph(data: dict):
    """Create a simple text representation of the dependency graph."""

    print("\n" + "="*100)
    print("DEPENDENCY GRAPH - MOST CONNECTED MODULES")
    print("="*100)

    # Get highly coupled modules
    highly_coupled = data.get('highly_coupled_modules', [])[:10]

    for module_info in highly_coupled:
        module = module_info['module']
        coupling = module_info['coupling_score']
        imports = module_info['imports']
        imported_by = module_info['imported_by']

        print(f"\n📦 {module}")
        print(f"   Coupling Score: {coupling} (imports: {imports}, imported by: {imported_by})")

        # Show what this module imports
        module_stats = data['module_statistics'].get(module, {})
        if module_stats.get('imports'):
            print(f"   📥 IMPORTS ({len(module_stats['imports'])}):")
            for imp in sorted(module_stats['imports'][:5]):
                print(f"      → {imp}")
            if len(module_stats['imports']) > 5:
                print(f"      ... and {len(module_stats['imports']) - 5} more")

        # Show what imports this module
        if module_stats.get('imported_by'):
            print(f"   📤 IMPORTED BY ({len(module_stats['imported_by'])}):")
            for imp_by in sorted(module_stats['imported_by'][:5]):
                print(f"      ← {imp_by}")
            if len(module_stats['imported_by']) > 5:
                print(f"      ... and {len(module_stats['imported_by']) - 5} more")

def generate_refactoring_plan():
    """Generate a specific refactoring plan."""

    print("\n" + "="*100)
    print("REFACTORING PLAN")
    print("="*100)

    plan = [
        {
            "priority": "CRITICAL",
            "task": "Break Plugin Circular Dependencies",
            "description": "Plugins.services ↔ plugins.core cycle",
            "steps": [
                "1. Create marty_msf.framework.plugins.interfaces module",
                "2. Move shared interfaces and protocols there",
                "3. Update imports to use interfaces module",
                "4. Use dependency injection for plugin registration"
            ]
        },
        {
            "priority": "HIGH",
            "task": "Refactor Security Unified Framework",
            "description": "Reduce coupling from 16 to under 10",
            "steps": [
                "1. Split unified_framework into smaller, focused modules",
                "2. Extract security.interfaces module",
                "3. Move authentication logic to security.auth",
                "4. Move authorization logic to security.authz",
                "5. Create security.core for shared functionality"
            ]
        },
        {
            "priority": "HIGH",
            "task": "Break Resilience Circular Dependencies",
            "description": "Manager ↔ consolidated_manager cycle",
            "steps": [
                "1. Create resilience.interfaces module",
                "2. Extract IResilientService interface",
                "3. Use dependency injection for manager registration",
                "4. Consider event-driven communication"
            ]
        },
        {
            "priority": "MEDIUM",
            "task": "Refactor Messaging Architecture",
            "description": "Break patterns ↔ core ↔ manager cycle",
            "steps": [
                "1. Create messaging.interfaces module",
                "2. Define IMessagePattern, IMessageManager interfaces",
                "3. Move concrete implementations to separate modules",
                "4. Use factory pattern for message creation"
            ]
        },
        {
            "priority": "MEDIUM",
            "task": "Simplify Gateway Module",
            "description": "Reduce imports from 13 to under 8",
            "steps": [
                "1. Extract gateway.interfaces",
                "2. Move routing logic to gateway.routing",
                "3. Move middleware to gateway.middleware",
                "4. Keep only core gateway functionality in main module"
            ]
        }
    ]

    for i, item in enumerate(plan, 1):
        print(f"\n🎯 TASK #{i} - {item['priority']} PRIORITY")
        print(f"   Title: {item['task']}")
        print(f"   Issue: {item['description']}")
        print("   Steps:")
        for step in item['steps']:
            print(f"      {step}")

if __name__ == "__main__":
    # Check command line arguments
    force_refresh = '--force' in sys.argv or '--refresh' in sys.argv

    # Get fresh analysis data
    data = ensure_fresh_analysis(force_refresh)

    # Run the analysis
    analyze_specific_circular_deps(data)
    create_dependency_graph(data)
    generate_refactoring_plan()

    print(f"\n{'='*100}")
    print("SUMMARY OF ACTIONS NEEDED:")
    print(f"{'='*100}")

    circular_count = len(data.get('circular_dependencies', []))
    coupled_count = len(data.get('highly_coupled_modules', []))

    if circular_count > 0:
        print(f"1. 🔥 IMMEDIATE: Fix {circular_count} circular dependencies")
    else:
        print("1. ✅ CIRCULAR DEPENDENCIES: None found - excellent!")

    if coupled_count > 5:
        print(f"2. ⚠️  HIGH: Refactor {coupled_count} highly coupled modules")
    elif coupled_count > 0:
        print(f"2. 🟡 MEDIUM: Review {coupled_count} moderately coupled modules")
    else:
        print("2. ✅ COUPLING: Low coupling detected - good architecture!")

    print("3. �️  MEDIUM: Establish clear architectural layers")
    print("4. 📚 LOW: Add documentation for new interfaces")
    print(f"{'='*100}")
