#!/usr/bin/env python3
"""
Global Replacement Helper Script

This script helps identify and replace global variable patterns with
typed service alternatives in the MMF codebase.
"""

import os
import re
import sys
from pathlib import Path


def find_global_patterns(directory: str) -> dict[str, list[tuple[str, int, str]]]:
    """Find all global patterns in Python files."""
    patterns = {"global_statements": [], "global_variables": [], "singleton_patterns": []}

    # Regex patterns
    global_stmt_pattern = re.compile(r"^\s*global\s+(\w+)", re.MULTILINE)
    global_var_pattern = re.compile(r"^(\w+)\s*:\s*.*\|\s*None\s*=\s*None", re.MULTILINE)
    singleton_pattern = re.compile(r"_(\w+)_manager\s*:\s*.*\|\s*None\s*=\s*None", re.MULTILINE)

    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        dirs[:] = [
            d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "node_modules"]
        ]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Find global statements
                    for match in global_stmt_pattern.finditer(content):
                        line_num = content[: match.start()].count("\n") + 1
                        patterns["global_statements"].append(
                            (file_path, line_num, match.group(0).strip())
                        )

                    # Find global variables
                    for match in global_var_pattern.finditer(content):
                        line_num = content[: match.start()].count("\n") + 1
                        patterns["global_variables"].append(
                            (file_path, line_num, match.group(0).strip())
                        )

                    # Find singleton patterns
                    for match in singleton_pattern.finditer(content):
                        line_num = content[: match.start()].count("\n") + 1
                        patterns["singleton_patterns"].append(
                            (file_path, line_num, match.group(0).strip())
                        )

                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    return patterns


def generate_replacement_suggestions(patterns: dict[str, list[tuple[str, int, str]]]) -> list[str]:
    """Generate replacement suggestions for found patterns."""
    suggestions = []

    suggestions.append("# Global Replacement Suggestions\n")
    suggestions.append("## Summary")
    suggestions.append(f"Found {len(patterns['global_statements'])} global statements")
    suggestions.append(f"Found {len(patterns['global_variables'])} global variables")
    suggestions.append(f"Found {len(patterns['singleton_patterns'])} singleton patterns")
    suggestions.append("")

    # Group by file for easier review
    files_with_globals = {}
    for pattern_type, items in patterns.items():
        for file_path, line_num, content in items:
            if file_path not in files_with_globals:
                files_with_globals[file_path] = []
            files_with_globals[file_path].append((pattern_type, line_num, content))

    for file_path, items in files_with_globals.items():
        rel_path = os.path.relpath(file_path)
        suggestions.append(f"## File: {rel_path}")
        suggestions.append("")

        for pattern_type, line_num, content in items:
            suggestions.append(f"**Line {line_num}** ({pattern_type}): `{content}`")

            if pattern_type == "global_statements":
                var_name = content.split()[-1]
                suggestions.append(
                    f"  → Replace with service registry: `get_service({var_name.title()}Service)`"
                )
            elif pattern_type == "global_variables":
                var_name = content.split(":")[0].strip()
                if "config" in var_name.lower():
                    suggestions.append(
                        f"  → Replace with ConfigService: `register_singleton(ConfigService, {var_name})`"
                    )
                elif "manager" in var_name.lower():
                    suggestions.append(
                        f"  → Replace with ManagerService: `register_singleton(ManagerService, {var_name})`"
                    )
                else:
                    suggestions.append("  → Replace with TypedSingleton or service registry")
            elif pattern_type == "singleton_patterns":
                suggestions.append("  → Replace with ManagerService pattern")

            suggestions.append("")

        suggestions.append("")

    return suggestions


def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python global_replacement_helper.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)

    print(f"Scanning {directory} for global patterns...")
    patterns = find_global_patterns(directory)

    print(f"Found {sum(len(items) for items in patterns.values())} total patterns")

    suggestions = generate_replacement_suggestions(patterns)

    # Write suggestions to file
    output_file = "global_replacement_suggestions.md"
    with open(output_file, "w") as f:
        f.write("\n".join(suggestions))

    print(f"Replacement suggestions written to {output_file}")

    # Print summary to console
    print("\n" + suggestions[0])
    for line in suggestions[1:8]:  # Print just the summary
        print(line)


if __name__ == "__main__":
    main()
