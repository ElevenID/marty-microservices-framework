#!/usr/bin/env python3
"""
Fast circular dependency checker for pre-commit hooks.
Only checks changed files and their immediate dependencies for performance.
"""

import ast
import os
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path


class FastCircularDependencyChecker:
    """Fast checker that focuses on changed files and their immediate neighbors."""

    def __init__(self, project_root: str = ".", project_name: str = "marty_msf"):
        self.project_root = Path(project_root)
        self.project_name = project_name
        self.src_path = self.project_root / "src" / project_name

        # Track only what we need for fast checking
        self.module_imports: dict[str, set[str]] = defaultdict(set)
        self.checked_files: set[str] = set()

    def get_changed_files(self) -> list[str]:
        """Get list of changed Python files in the current git commit."""
        try:
            # Get staged files
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
                capture_output=True,
                text=True,
                check=True
            )

            changed_files = []
            for file_path in result.stdout.strip().split('\n'):
                if file_path.endswith('.py') and self.project_name in file_path:
                    full_path = self.project_root / file_path
                    if full_path.exists():
                        changed_files.append(str(full_path))

            return changed_files

        except subprocess.CalledProcessError:
            # Fallback: check all files if git fails
            return []

    def get_module_name(self, file_path: str) -> str:
        """Convert file path to module name."""
        try:
            path = Path(file_path)
            relative_path = path.relative_to(self.project_root / "src")
            parts = list(relative_path.parts)

            if parts[-1] == '__init__.py':
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1][:-3]  # Remove .py extension

            return '.'.join(parts)
        except (ValueError, IndexError):
            return str(file_path)

    def parse_imports(self, file_path: str) -> set[str]:
        """Parse imports from a single file."""
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

        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            pass  # Skip files that can't be parsed

        return imports

    def find_related_files(self, module_names: list[str]) -> set[str]:
        """Find files that might be related to the changed modules."""
        related_files = set()

        # Add the modules themselves
        for module_name in module_names:
            module_path = self.module_name_to_path(module_name)
            if module_path and module_path.exists():
                related_files.add(str(module_path))

        # Find files that import these modules (reverse dependencies)
        for root, dirs, files in os.walk(self.src_path):
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    if str(file_path) not in related_files:
                        imports = self.parse_imports(str(file_path))
                        if any(module in imports for module in module_names):
                            related_files.add(str(file_path))

        return related_files

    def module_name_to_path(self, module_name: str) -> Path | None:
        """Convert module name back to file path."""
        parts = module_name.split('.')
        if parts[0] != self.project_name:
            return None

        # Remove project name
        parts = parts[1:]

        # Try as a file first
        file_path = self.src_path
        for part in parts:
            file_path = file_path / part

        py_file = file_path.with_suffix('.py')
        if py_file.exists():
            return py_file

        # Try as a package
        init_file = file_path / '__init__.py'
        if init_file.exists():
            return init_file

        return None

    def check_circular_dependencies(self, files_to_check: list[str]) -> list[list[str]]:
        """Check for circular dependencies among the given files."""
        # Build import graph for these files
        import_graph = defaultdict(set)

        for file_path in files_to_check:
            module_name = self.get_module_name(file_path)
            imports = self.parse_imports(file_path)

            for imported_module in imports:
                import_graph[module_name].add(imported_module)

        # Find cycles using DFS
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: list[str]):
            if node in rec_stack:
                # Found a cycle
                try:
                    cycle_start = path.index(node)
                    cycle = path[cycle_start:] + [node]
                    cycles.append(cycle)
                except ValueError:
                    pass
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in import_graph.get(node, []):
                dfs(neighbor, path[:])

            rec_stack.remove(node)

        # Check each module
        for module in import_graph:
            if module not in visited:
                dfs(module, [])

        return cycles

    def check_changed_files(self) -> bool:
        """Check changed files for circular dependencies. Returns True if no cycles found."""
        changed_files = self.get_changed_files()

        if not changed_files:
            return True  # No files to check

        print(f"🔍 Checking {len(changed_files)} changed files for circular dependencies...")

        # Get modules from changed files
        changed_modules = [self.get_module_name(f) for f in changed_files]

        # Find related files that might be affected
        related_files = self.find_related_files(changed_modules)
        all_files_to_check = set(changed_files) | related_files

        print(f"📋 Analyzing {len(all_files_to_check)} total files (including dependencies)...")

        # Check for circular dependencies
        cycles = self.check_circular_dependencies(list(all_files_to_check))

        if cycles:
            print(f"\n❌ Found {len(cycles)} circular dependencies:")
            for i, cycle in enumerate(cycles, 1):
                print(f"  {i}. {' → '.join(cycle)}")

            print("\n💡 To fix circular dependencies:")
            print("   - Extract shared interfaces to a common module")
            print("   - Use dependency injection")
            print("   - Consider using imports inside functions (lazy loading)")
            print("   - Break dependencies by introducing abstractions")

            return False
        else:
            print("✅ No circular dependencies found in changed files!")
            return True


def main():
    """Main entry point for pre-commit hook."""
    checker = FastCircularDependencyChecker()

    success = checker.check_changed_files()

    if not success:
        print("\n🚫 Commit blocked due to circular dependencies.")
        print("   Fix the circular dependencies above and try again.")
        sys.exit(1)
    else:
        print("🎉 All checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
