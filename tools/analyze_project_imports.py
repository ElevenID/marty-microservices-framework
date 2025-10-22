#!/usr/bin/env python3
"""
Analyze internal project imports to identify architectural issues.
"""
import ast
import json
import os
import sys
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any


class ImportAnalyzer:
    def __init__(self, project_root: str, project_name: str = "marty_msf", real_time: bool = True):
        self.project_root = Path(project_root)
        self.project_name = project_name
        self.src_path = self.project_root / "src" / project_name
        self.real_time = real_time
        self.analysis_timestamp = None

        # Data structures for analysis
        self.file_imports: dict[str, set[str]] = defaultdict(set)
        self.module_dependencies: dict[str, set[str]] = defaultdict(set)
        self.reverse_dependencies: dict[str, set[str]] = defaultdict(set)
        self.circular_deps: list[list[str]] = []
        self.import_graph = defaultdict(set)

        # Track analysis metadata
        self.parse_errors: list[tuple[str, str]] = []
        self.skipped_files: list[str] = []

    def find_python_files(self) -> list[Path]:
        """Find all Python files in the project."""
        python_files = []
        for root, dirs, files in os.walk(self.src_path):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        return python_files

    def get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        try:
            relative_path = file_path.relative_to(self.project_root / "src")
            parts = list(relative_path.parts)
            if parts[-1] == '__init__.py':
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1][:-3]  # Remove .py extension
            return '.'.join(parts)
        except ValueError:
            return str(file_path)

    def parse_imports(self, file_path: Path) -> set[str]:
        """Parse imports from a Python file."""
        imports = set()
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(self.project_name):
                            imports.add(alias.name)

                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith(self.project_name):
                        imports.add(node.module)
                    elif node.level > 0:  # Relative import
                        # Handle relative imports
                        current_module = self.get_module_name(file_path)
                        current_parts = current_module.split('.')

                        if node.level <= len(current_parts):
                            base_parts = current_parts[:-node.level] if node.level > 0 else current_parts
                            if node.module:
                                full_module = '.'.join(base_parts + [node.module])
                            else:
                                full_module = '.'.join(base_parts)

                            if full_module.startswith(self.project_name):
                                imports.add(full_module)

        except (SyntaxError, UnicodeDecodeError, FileNotFoundError) as e:
            error_msg = f"Error parsing {file_path}: {e}"
            if self.real_time:
                print(error_msg)
            self.parse_errors.append((str(file_path), str(e)))

        return imports

    def analyze_imports(self):
        """Analyze all imports in the project."""
        python_files = self.find_python_files()
        print(f"Found {len(python_files)} Python files")

        for file_path in python_files:
            module_name = self.get_module_name(file_path)
            imports = self.parse_imports(file_path)

            self.file_imports[module_name] = imports

            for imported_module in imports:
                self.module_dependencies[module_name].add(imported_module)
                self.reverse_dependencies[imported_module].add(module_name)
                self.import_graph[module_name].add(imported_module)

    def find_circular_dependencies(self) -> list[list[str]]:
        """Find circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.import_graph.get(node, []):
                dfs(neighbor, path[:])

            rec_stack.remove(node)

        for module in self.module_dependencies:
            if module not in visited:
                dfs(module, [])

        # Remove duplicates and sort
        unique_cycles = []
        for cycle in cycles:
            normalized = tuple(sorted(cycle[:-1]))  # Remove duplicate last element
            if normalized not in [tuple(sorted(c[:-1])) for c in unique_cycles]:
                unique_cycles.append(cycle)

        return unique_cycles

    def get_module_stats(self) -> dict:
        """Get statistics about modules."""
        stats = {}
        for module, deps in self.module_dependencies.items():
            stats[module] = {
                'imports_count': len(deps),
                'imported_by_count': len(self.reverse_dependencies[module]),
                'imports': list(deps),
                'imported_by': list(self.reverse_dependencies[module])
            }
        return stats

    def generate_report(self) -> dict:
        """Generate comprehensive import analysis report."""
        self.analyze_imports()
        circular_deps = self.find_circular_dependencies()
        module_stats = self.get_module_stats()

        # Find highly coupled modules
        highly_coupled = []
        for module, stats in module_stats.items():
            total_coupling = stats['imports_count'] + stats['imported_by_count']
            if total_coupling > 5:  # Threshold for high coupling
                highly_coupled.append({
                    'module': module,
                    'coupling_score': total_coupling,
                    'imports': stats['imports_count'],
                    'imported_by': stats['imported_by_count']
                })

        highly_coupled.sort(key=lambda x: x['coupling_score'], reverse=True)

        # Find potential architectural layers
        layers = self.identify_layers()

        report = {
            'summary': {
                'total_modules': len(self.module_dependencies),
                'total_internal_imports': sum(len(deps) for deps in self.module_dependencies.values()),
                'circular_dependencies_count': len(circular_deps),
                'highly_coupled_modules_count': len(highly_coupled)
            },
            'circular_dependencies': circular_deps,
            'highly_coupled_modules': highly_coupled[:10],  # Top 10
            'module_statistics': module_stats,
            'architectural_layers': layers,
            'recommendations': self.generate_recommendations(circular_deps, highly_coupled)
        }

        return report

    def identify_layers(self) -> dict:
        """Identify potential architectural layers based on import patterns."""
        layers = {
            'core': [],
            'domain': [],
            'services': [],
            'api': [],
            'infrastructure': [],
            'utils': [],
            'other': []
        }

        for module in self.module_dependencies.keys():
            parts = module.split('.')
            if len(parts) > 1:
                second_level = parts[1]

                if 'core' in second_level or 'base' in second_level:
                    layers['core'].append(module)
                elif 'domain' in second_level or 'model' in second_level:
                    layers['domain'].append(module)
                elif 'service' in second_level:
                    layers['services'].append(module)
                elif 'api' in second_level or 'handler' in second_level or 'controller' in second_level:
                    layers['api'].append(module)
                elif 'infrastructure' in second_level or 'repo' in second_level or 'database' in second_level:
                    layers['infrastructure'].append(module)
                elif 'util' in second_level or 'helper' in second_level or 'tool' in second_level:
                    layers['utils'].append(module)
                else:
                    layers['other'].append(module)

        return layers

    def generate_recommendations(self, circular_deps: list, highly_coupled: list) -> list[str]:
        """Generate architectural recommendations."""
        recommendations = []

        if circular_deps:
            recommendations.append(f"🔄 CRITICAL: Found {len(circular_deps)} circular dependencies that need immediate attention")
            recommendations.append("   - Consider using dependency injection or interfaces to break cycles")
            recommendations.append("   - Move shared code to a common module")

        if highly_coupled:
            recommendations.append(f"⚠️  HIGH COUPLING: {len(highly_coupled)} modules are highly coupled")
            recommendations.append("   - Consider splitting large modules into smaller, focused modules")
            recommendations.append("   - Apply Single Responsibility Principle")

        # Check for potential God modules
        god_modules = [m for m in highly_coupled if m['coupling_score'] > 15]
        if god_modules:
            recommendations.append(f"🏛️  GOD MODULES: {len(god_modules)} modules may be doing too much")
            for god in god_modules[:3]:
                recommendations.append(f"   - {god['module']} (coupling: {god['coupling_score']})")

        recommendations.extend([
            "📋 GENERAL RECOMMENDATIONS:",
            "   - Follow layered architecture: API → Services → Domain → Infrastructure",
            "   - Use dependency inversion for external dependencies",
            "   - Consider using events/messaging for loose coupling",
            "   - Implement proper abstractions and interfaces"
        ])

        return recommendations

def main():

    # Check if we should force regeneration or use cached data
    force_regenerate = '--force' in sys.argv or '--real-time' in sys.argv
    quiet_mode = '--quiet' in sys.argv

    analyzer = ImportAnalyzer(".", "marty_msf", real_time=True)

    # Check if cached analysis exists and is recent
    cache_file = Path('internal_import_analysis.json')
    should_regenerate = force_regenerate

    if not should_regenerate and cache_file.exists():
        try:
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age > 300:  # 5 minutes
                should_regenerate = True
                if not quiet_mode:
                    print(f"🔄 Cache is {cache_age:.0f}s old, regenerating...")
        except (OSError, ValueError):
            should_regenerate = True
    else:
        should_regenerate = True

    if should_regenerate:
        if not quiet_mode:
            print("🔍 Analyzing project imports in real-time...")
        report = analyzer.generate_report()
        report['metadata'] = {
            'generated_at': datetime.now().isoformat(),
            'analysis_type': 'real_time',
            'parse_errors': analyzer.parse_errors,
            'skipped_files': analyzer.skipped_files
        }

        # Save detailed report to JSON
        with open('internal_import_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
    else:
        if not quiet_mode:
            print("📋 Using cached analysis (use --force to regenerate)")
        with open('internal_import_analysis.json', encoding='utf-8') as f:
            report = json.load(f)    # Print summary report
    print("="*80)
    print("MARTY MICROSERVICES FRAMEWORK - IMPORT ARCHITECTURE ANALYSIS")
    print("="*80)

    print("\n📊 SUMMARY:")
    print(f"   Total Modules: {report['summary']['total_modules']}")
    print(f"   Internal Imports: {report['summary']['total_internal_imports']}")
    print(f"   Circular Dependencies: {report['summary']['circular_dependencies_count']}")
    print(f"   Highly Coupled Modules: {report['summary']['highly_coupled_modules_count']}")

    if report['circular_dependencies']:
        print(f"\n🔄 CIRCULAR DEPENDENCIES ({len(report['circular_dependencies'])}):")
        for i, cycle in enumerate(report['circular_dependencies'][:5], 1):
            print(f"   {i}. {' → '.join(cycle)}")
        if len(report['circular_dependencies']) > 5:
            print(f"   ... and {len(report['circular_dependencies']) - 5} more")

    if report['highly_coupled_modules']:
        print("\n⚠️  HIGHLY COUPLED MODULES:")
        for module in report['highly_coupled_modules'][:5]:
            print(f"   {module['module']} (coupling: {module['coupling_score']}, "
                  f"imports: {module['imports']}, imported_by: {module['imported_by']})")

    print("\n🏗️  ARCHITECTURAL LAYERS:")
    for layer, modules in report['architectural_layers'].items():
        if modules:
            print(f"   {layer.upper()}: {len(modules)} modules")

    print("\n💡 RECOMMENDATIONS:")
    for rec in report['recommendations']:
        print(f"   {rec}")

    # Show analysis metadata if available
    if 'metadata' in report and not quiet_mode:
        print("\n📊 ANALYSIS METADATA:")
        meta = report['metadata']
        if 'generated_at' in meta:
            print(f"   Generated: {meta['generated_at']}")
        if 'parse_errors' in meta and meta['parse_errors']:
            print(f"   Parse Errors: {len(meta['parse_errors'])} files")
            for file_path, error in meta['parse_errors'][:3]:  # Show first 3
                print(f"     - {file_path}: {error}")
            if len(meta['parse_errors']) > 3:
                print(f"     ... and {len(meta['parse_errors']) - 3} more")

    print("\n📁 DETAILED REPORT: internal_import_analysis.json")
    print("="*80)

if __name__ == "__main__":
    main()
