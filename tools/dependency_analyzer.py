#!/usr/bin/env python3
"""
Dependency Analysis Utility

A convenient script for developers to analyze project dependencies and
architectural health. Can be run with various options for different use cases.

Usage:
    python tools/dependency_analyzer.py [OPTIONS]

Options:
    --quick, -q          Quick analysis (fast, focuses on changed files)
    --full, -f           Full analysis (comprehensive, all files)
    --circular, -c       Focus on circular dependencies only
    --coupling, -u       Focus on coupling analysis only
    --watch, -w          Watch mode (run analysis when files change)
    --export FORMAT      Export results (json, csv, md)
    --threshold N        Set coupling threshold (default: 5)
    --help, -h           Show this help message
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

# Import our analysis tools
from analyze_project_imports import ImportAnalyzer
from check_circular_deps_fast import FastCircularDependencyChecker


class DependencyAnalyzer:
    """Main analyzer that orchestrates different analysis types."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.full_analyzer = ImportAnalyzer(project_root, real_time=True)
        self.fast_checker = FastCircularDependencyChecker(project_root)

    def quick_analysis(self) -> dict:
        """Run quick analysis focusing on changed files."""
        print("🚀 Running quick dependency analysis...")

        # Check circular dependencies in changed files
        cycles_clean = self.fast_checker.check_changed_files()

        # Get basic metrics from cached data if available
        cache_file = self.project_root / 'internal_import_analysis.json'
        basic_metrics = {}

        if cache_file.exists():
            try:
                with open(cache_file, encoding='utf-8') as f:
                    cached_data = json.load(f)
                    basic_metrics = cached_data.get('summary', {})
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        return {
            'type': 'quick',
            'circular_dependencies_clean': cycles_clean,
            'basic_metrics': basic_metrics,
            'timestamp': time.time()
        }

    def full_analysis(self, coupling_threshold: int = 5) -> dict:
        """Run comprehensive analysis of all files."""
        print("🔍 Running full dependency analysis...")

        # Run full import analysis
        report = self.full_analyzer.generate_report()

        # Add threshold-based analysis
        highly_coupled = [
            module for module in report.get('highly_coupled_modules', [])
            if module['coupling_score'] > coupling_threshold
        ]

        report['threshold_analysis'] = {
            'coupling_threshold': coupling_threshold,
            'modules_above_threshold': len(highly_coupled),
            'highly_coupled_modules': highly_coupled
        }

        return report

    def circular_analysis(self) -> dict:
        """Focus specifically on circular dependency analysis."""
        print("🔄 Analyzing circular dependencies...")

        # Run both fast and full circular dependency checks
        fast_result = self.fast_checker.check_changed_files()

        # Get full analysis for complete picture
        full_report = self.full_analyzer.generate_report()

        return {
            'type': 'circular_focus',
            'changed_files_clean': fast_result,
            'all_circular_dependencies': full_report.get('circular_dependencies', []),
            'circular_count': len(full_report.get('circular_dependencies', [])),
            'recommendations': self._get_circular_recommendations(
                full_report.get('circular_dependencies', [])
            )
        }

    def coupling_analysis(self, threshold: int = 5) -> dict:
        """Focus specifically on coupling analysis."""
        print("🔗 Analyzing module coupling...")

        report = self.full_analyzer.generate_report()

        # Detailed coupling analysis
        highly_coupled = report.get('highly_coupled_modules', [])

        coupling_tiers = {
            'critical': [m for m in highly_coupled if m['coupling_score'] > 15],
            'high': [m for m in highly_coupled if 10 < m['coupling_score'] <= 15],
            'medium': [m for m in highly_coupled if 5 < m['coupling_score'] <= 10],
            'acceptable': [m for m in highly_coupled if m['coupling_score'] <= 5]
        }

        return {
            'type': 'coupling_focus',
            'threshold': threshold,
            'coupling_tiers': coupling_tiers,
            'total_modules': report.get('summary', {}).get('total_modules', 0),
            'recommendations': self._get_coupling_recommendations(coupling_tiers)
        }

    def _get_circular_recommendations(self, cycles: list) -> list[str]:
        """Generate specific recommendations for circular dependencies."""
        if not cycles:
            return ["✅ No circular dependencies found - excellent architecture!"]

        recommendations = [
            f"🔄 Found {len(cycles)} circular dependencies - immediate action required:",
            "",
            "Breaking Strategies:",
            "• Extract shared interfaces to common modules",
            "• Use dependency injection patterns",
            "• Implement lazy loading (imports inside functions)",
            "• Create abstraction layers between components",
            "• Consider event-driven architecture for loose coupling",
            "",
            "Specific Actions:"
        ]

        for i, cycle in enumerate(cycles[:3], 1):
            recommendations.append(f"  {i}. Fix: {' → '.join(cycle)}")

        if len(cycles) > 3:
            recommendations.append(f"  ... and {len(cycles) - 3} more cycles")

        return recommendations

    def _get_coupling_recommendations(self, coupling_tiers: dict) -> list[str]:
        """Generate specific recommendations for high coupling."""
        recommendations = []

        if coupling_tiers['critical']:
            recommendations.extend([
                f"🚨 CRITICAL: {len(coupling_tiers['critical'])} modules have excessive coupling (>15)",
                "  These modules need immediate refactoring:",
            ])
            for module in coupling_tiers['critical'][:3]:
                recommendations.append(f"    • {module['module']} (score: {module['coupling_score']})")

        if coupling_tiers['high']:
            recommendations.extend([
                f"⚠️ HIGH: {len(coupling_tiers['high'])} modules have high coupling (10-15)",
                "  Consider splitting these modules into smaller components",
            ])

        if coupling_tiers['medium']:
            recommendations.append(
                f"🔶 MEDIUM: {len(coupling_tiers['medium'])} modules have moderate coupling (5-10)"
            )

        if not any(coupling_tiers.values()):
            recommendations.append("✅ All modules have acceptable coupling levels!")

        recommendations.extend([
            "",
            "General Coupling Reduction Strategies:",
            "• Apply Single Responsibility Principle",
            "• Extract shared functionality to utility modules",
            "• Use interfaces and abstract base classes",
            "• Implement dependency inversion",
            "• Consider using composition over inheritance"
        ])

        return recommendations

    def export_results(self, results: dict, format_type: str, output_file: str | None = None):
        """Export analysis results in specified format."""
        if not output_file:
            timestamp = int(time.time())
            output_file = f"dependency_analysis_{timestamp}.{format_type}"

        if format_type == 'json':
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)

        elif format_type == 'md':
            self._export_markdown(results, output_file)

        elif format_type == 'csv':
            self._export_csv(results, output_file)

        print(f"📄 Results exported to: {output_file}")

    def _export_markdown(self, results: dict, output_file: str):
        """Export results as markdown report."""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Dependency Analysis Report\n\n")
            f.write(f"Generated: {time.ctime()}\n\n")

            if 'summary' in results:
                summary = results['summary']
                f.write("## Summary\n\n")
                f.write(f"- Total Modules: {summary.get('total_modules', 'N/A')}\n")
                f.write(f"- Internal Imports: {summary.get('total_internal_imports', 'N/A')}\n")
                f.write(f"- Circular Dependencies: {summary.get('circular_dependencies_count', 'N/A')}\n")
                f.write(f"- Highly Coupled Modules: {summary.get('highly_coupled_modules_count', 'N/A')}\n\n")

            if 'recommendations' in results:
                f.write("## Recommendations\n\n")
                for rec in results['recommendations']:
                    f.write(f"- {rec}\n")

    def _export_csv(self, results: dict, output_file: str):
        """Export results as CSV (focusing on module statistics)."""

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Module', 'Coupling Score', 'Imports', 'Imported By'])

            if 'highly_coupled_modules' in results:
                for module in results['highly_coupled_modules']:
                    writer.writerow([
                        module['module'],
                        module['coupling_score'],
                        module['imports'],
                        module['imported_by']
                    ])


def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Analyze project dependencies and architectural health",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('-q', '--quick', action='store_true',
                       help='Quick analysis (focuses on changed files)')
    parser.add_argument('-f', '--full', action='store_true',
                       help='Full analysis (comprehensive, all files)')
    parser.add_argument('-c', '--circular', action='store_true',
                       help='Focus on circular dependencies only')
    parser.add_argument('-u', '--coupling', action='store_true',
                       help='Focus on coupling analysis only')
    parser.add_argument('--export', metavar='FORMAT',
                       choices=['json', 'csv', 'md'],
                       help='Export results in specified format')
    parser.add_argument('--threshold', type=int, default=5,
                       help='Set coupling threshold (default: 5)')
    parser.add_argument('--output', metavar='FILE',
                       help='Output file for export')

    args = parser.parse_args()

    # Default to quick analysis if no specific mode chosen
    if not any([args.quick, args.full, args.circular, args.coupling]):
        args.quick = True

    analyzer = DependencyAnalyzer()

    # Run the requested analysis
    if args.circular:
        results = analyzer.circular_analysis()
    elif args.coupling:
        results = analyzer.coupling_analysis(args.threshold)
    elif args.full:
        results = analyzer.full_analysis(args.threshold)
    else:  # quick
        results = analyzer.quick_analysis()

    # Print results
    print("\n" + "="*80)
    print("DEPENDENCY ANALYSIS RESULTS")
    print("="*80)

    if 'recommendations' in results:
        print("\n💡 RECOMMENDATIONS:")
        for rec in results['recommendations']:
            print(f"   {rec}")

    # Export if requested
    if args.export:
        analyzer.export_results(results, args.export, args.output)

    # Return appropriate exit code
    if results.get('type') == 'quick':
        sys.exit(0 if results.get('circular_dependencies_clean', True) else 1)
    elif 'circular_dependencies' in results:
        sys.exit(0 if not results['circular_dependencies'] else 1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
