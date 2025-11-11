#!/usr/bin/env python3
"""
Create a visual representation of the module architecture.
"""

import json
from collections import defaultdict, deque


def create_layer_visualization():
    """Create a layered architecture visualization."""

    with open("internal_import_analysis.json") as f:
        data = json.load(f)

    print("=" * 120)
    print("MARTY MICROSERVICES FRAMEWORK - ARCHITECTURAL LAYERS")
    print("=" * 120)

    # Define architectural layers based on module paths
    layers = {
        "Core Infrastructure": ["marty_msf.core", "marty_msf.utils", "marty_msf.types"],
        "Framework Foundation": [
            "marty_msf.framework.core",
            "marty_msf.framework.config",
            "marty_msf.framework.discovery",
        ],
        "Security Layer": ["marty_msf.security"],
        "Messaging & Communication": [
            "marty_msf.framework.messaging",
            "marty_msf.framework.websocket",
            "marty_msf.framework.grpc",
        ],
        "Service Management": [
            "marty_msf.framework.plugins",
            "marty_msf.framework.resilience",
            "marty_msf.framework.service_mesh",
        ],
        "Gateway & Routing": [
            "marty_msf.framework.gateway",
            "marty_msf.framework.routing",
            "marty_msf.framework.api_gateway",
        ],
        "Integration & Extensions": [
            "marty_msf.framework.integration",
            "marty_msf.framework.ml",
            "marty_msf.framework.generators",
        ],
        "Observability": ["marty_msf.observability", "marty_msf.framework.monitoring"],
    }

    # Get module statistics
    module_stats = data["module_statistics"]
    circular_deps = data["circular_dependencies"]

    # Find problematic modules in each layer
    problematic_modules = set()
    for cycle in circular_deps:
        for module in cycle:
            problematic_modules.add(module)

    for layer_name, layer_modules in layers.items():
        print(f"\n📁 {layer_name}")
        print("─" * (len(layer_name) + 3))

        layer_problems = []
        layer_coupling = []

        for module_pattern in layer_modules:
            matching_modules = [m for m in module_stats.keys() if m.startswith(module_pattern)]

            for module in matching_modules:
                stats = module_stats[module]
                imports = len(stats.get("imports", []))
                imported_by = len(stats.get("imported_by", []))
                coupling = imports + imported_by

                status = "🔴" if module in problematic_modules else "🟡" if coupling > 8 else "🟢"

                print(f"  {status} {module}")

                if imports > 0 or imported_by > 0:
                    print(
                        f"      📊 Coupling: {coupling} (imports: {imports}, imported by: {imported_by})"
                    )

                if module in problematic_modules:
                    layer_problems.append(module)

                if coupling > 8:
                    layer_coupling.append((module, coupling))

        if layer_problems:
            print(f"  ⚠️  Circular Dependencies: {len(layer_problems)} modules")

        if layer_coupling:
            high_coupling = [m for m, c in layer_coupling if c > 10]
            if high_coupling:
                print(f"  🔗 High Coupling: {len(high_coupling)} modules")


def create_dependency_flow():
    """Show the dependency flow between major components."""

    with open("internal_import_analysis.json") as f:
        data = json.load(f)

    print(f"\n{'=' * 120}")
    print("DEPENDENCY FLOW ANALYSIS")
    print(f"{'=' * 120}")

    # Focus on major components and their relationships
    major_components = {
        "core": "marty_msf.core",
        "security": "marty_msf.security",
        "messaging": "marty_msf.framework.messaging",
        "plugins": "marty_msf.framework.plugins",
        "resilience": "marty_msf.framework.resilience",
        "gateway": "marty_msf.framework.gateway",
        "discovery": "marty_msf.framework.discovery",
    }

    module_stats = data["module_statistics"]

    # Build dependency matrix
    component_deps = defaultdict(set)

    for module_name, stats in module_stats.items():
        source_component = None
        for comp_name, comp_prefix in major_components.items():
            if module_name.startswith(comp_prefix):
                source_component = comp_name
                break

        if source_component:
            for imported_module in stats.get("imports", []):
                for comp_name, comp_prefix in major_components.items():
                    if imported_module.startswith(comp_prefix) and comp_name != source_component:
                        component_deps[source_component].add(comp_name)

    print("\n🏗️ COMPONENT DEPENDENCY MATRIX:")
    print("   (→ Component depends on)")

    for component in major_components.keys():
        deps = component_deps.get(component, set())
        if deps:
            print(f"\n   📦 {component.upper()}")
            for dep in sorted(deps):
                print(f"      → {dep}")
        else:
            print(f"\n   📦 {component.upper()} (no major dependencies)")


def generate_refactoring_priority():
    """Generate a priority matrix for refactoring."""

    with open("internal_import_analysis.json") as f:
        data = json.load(f)

    print(f"\n{'=' * 120}")
    print("REFACTORING PRIORITY MATRIX")
    print(f"{'=' * 120}")

    circular_modules = set()
    for cycle in data["circular_dependencies"]:
        circular_modules.update(cycle)

    highly_coupled = data["highly_coupled_modules"][:15]

    # Priority scoring: circular dependency = +10, high coupling = +coupling_score
    priority_scores = defaultdict(int)

    for module in circular_modules:
        priority_scores[module] += 10

    for module_info in highly_coupled:
        module = module_info["module"]
        coupling = module_info["coupling_score"]
        priority_scores[module] += coupling

    # Sort by priority
    sorted_priorities = sorted(priority_scores.items(), key=lambda x: x[1], reverse=True)

    print("\n🎯 TOP PRIORITY MODULES FOR REFACTORING:")
    print("   (Score = 10 * circular_deps + coupling_score)")

    for i, (module, score) in enumerate(sorted_priorities[:10], 1):
        is_circular = module in circular_modules
        coupling_info = next((m for m in highly_coupled if m["module"] == module), None)
        coupling_score = coupling_info["coupling_score"] if coupling_info else 0

        priority_level = "🔥 CRITICAL" if score >= 20 else "⚠️ HIGH" if score >= 15 else "🟡 MEDIUM"

        print(f"\n   {i:2d}. {priority_level} (Score: {score})")
        print(f"       📦 {module}")

        if is_circular:
            print("       🔄 Part of circular dependency")
        if coupling_score > 0:
            print(f"       🔗 Coupling score: {coupling_score}")


if __name__ == "__main__":
    create_layer_visualization()
    create_dependency_flow()
    generate_refactoring_priority()

    print(f"\n{'=' * 120}")
    print("🎯 NEXT STEPS RECOMMENDATION:")
    print(f"{'=' * 120}")
    print("1. Start with CRITICAL modules (circular dependencies)")
    print("2. Focus on plugins.services ↔ plugins.core cycle first")
    print("3. Refactor security.unified_framework (highest coupling)")
    print("4. Break messaging circular dependencies")
    print("5. Establish clear interface contracts between layers")
    print(f"{'=' * 120}")
