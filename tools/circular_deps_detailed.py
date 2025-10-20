#!/usr/bin/env python3
"""
Detailed analysis of circular dependencies with specific recommendations.
"""
import ast
import json
from pathlib import Path


def analyze_specific_circular_deps():
    """Analyze the specific circular dependencies found."""

    # Load the detailed analysis
    with open('internal_import_analysis.json') as f:
        data = json.load(f)

    print("="*100)
    print("DETAILED CIRCULAR DEPENDENCY ANALYSIS")
    print("="*100)

    circular_deps = data['circular_dependencies']

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

def create_dependency_graph():
    """Create a simple text representation of the dependency graph."""

    with open('internal_import_analysis.json') as f:
        data = json.load(f)

    print("\n" + "="*100)
    print("DEPENDENCY GRAPH - MOST CONNECTED MODULES")
    print("="*100)

    # Get highly coupled modules
    highly_coupled = data['highly_coupled_modules'][:10]

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
    analyze_specific_circular_deps()
    create_dependency_graph()
    generate_refactoring_plan()

    print(f"\n{'='*100}")
    print("SUMMARY OF ACTIONS NEEDED:")
    print(f"{'='*100}")
    print("1. 🔥 IMMEDIATE: Fix 10 circular dependencies")
    print("2. ⚠️  HIGH: Refactor 5 highly coupled modules")
    print("3. 🏗️  MEDIUM: Establish clear architectural layers")
    print("4. 📚 LOW: Add documentation for new interfaces")
    print(f"{'='*100}")
