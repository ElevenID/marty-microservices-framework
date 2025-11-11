#!/usr/bin/env python3
"""
Script to fix SQL syntax issues in existing files.

This script scans for SQL files and fixes common PostgreSQL compatibility issues:
- Converts MySQL-style inline INDEX declarations to separate CREATE INDEX statements
- Ensures JSONB values are properly formatted as JSON strings

Usage:
    python scripts/fix_sql_syntax.py [directory] [--dry-run]
"""

import argparse
import json
import re
import sys
from pathlib import Path


# Import the SQLGenerator class directly to avoid framework dependencies
class SQLGenerator:
    """Utility class for generating valid PostgreSQL SQL syntax."""

    def format_jsonb_value(self, value: any) -> str:
        """Format a Python value as a proper JSONB string."""
        if value is None:
            return "null"
        elif isinstance(value, str):
            # String values need to be JSON-encoded (with quotes)
            return json.dumps(value)
        elif isinstance(value, dict | list):
            # Objects and arrays need to be JSON-encoded
            return json.dumps(value)
        elif isinstance(value, bool):
            # Boolean values need to be lowercase in JSON
            return json.dumps(value)
        elif isinstance(value, int | float):
            # Numbers can be used directly
            return json.dumps(value)
        else:
            # For any other type, convert to JSON
            return json.dumps(value)

    def fix_mysql_index_syntax(self, sql_content: str) -> str:
        """Convert MySQL-style inline INDEX declarations to separate CREATE INDEX statements."""
        lines = sql_content.split("\n")
        result_lines = []
        index_statements = []
        current_table = None
        in_create_table = False

        for line in lines:
            stripped = line.strip()

            # Detect CREATE TABLE statements
            if stripped.upper().startswith("CREATE TABLE"):
                in_create_table = True
                # Extract table name
                table_match = re.search(r"CREATE TABLE\s+(\w+)", stripped, re.IGNORECASE)
                if table_match:
                    current_table = table_match.group(1)
                result_lines.append(line)
                continue

            # End of CREATE TABLE block
            if in_create_table and stripped.endswith(");"):
                in_create_table = False
                result_lines.append(line)
                # Add collected index statements after the table
                result_lines.extend(index_statements)
                index_statements = []
                current_table = None
                continue

            # Process INDEX declarations within CREATE TABLE
            if in_create_table and current_table:
                index_match = re.search(r"INDEX\s+(\w+)\s*\(([^)]+)\)", stripped, re.IGNORECASE)
                if index_match:
                    index_name = index_match.group(1)
                    index_columns = index_match.group(2)
                    # Create separate CREATE INDEX statement
                    create_index = f"CREATE INDEX {index_name} ON {current_table}({index_columns});"
                    index_statements.append(create_index)
                    # Skip this line (don't add to result)
                    continue

            # Add non-index lines as-is
            result_lines.append(line)

        return "\n".join(result_lines)

    def validate_postgresql_syntax(self, sql_content: str) -> list[str]:
        """Validate SQL content for PostgreSQL compatibility issues."""
        issues = []

        # Check for MySQL-style inline INDEX declarations
        if re.search(r"INDEX\s+\w+\s*\([^)]+\)", sql_content, re.IGNORECASE):
            issues.append(
                "Found MySQL-style inline INDEX declarations. Use separate CREATE INDEX statements."
            )

        return issues


def find_sql_files(directory: Path, patterns: list[str] = None) -> list[Path]:
    """Find all SQL files in the directory."""
    if patterns is None:
        patterns = ["*.sql", "*.sql.j2"]

    sql_files = []
    for pattern in patterns:
        sql_files.extend(directory.rglob(pattern))

    return sql_files


def fix_sql_file(file_path: Path, dry_run: bool = False) -> tuple[bool, list[str]]:
    """
    Fix SQL syntax issues in a file.

    Returns:
        (was_modified, issues_found)
    """
    generator = SQLGenerator()

    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Check for issues first
        issues = generator.validate_postgresql_syntax(content)

        if not issues:
            return False, []

        # Fix MySQL-style INDEX syntax
        if any("MySQL-style inline INDEX" in issue for issue in issues):
            content = generator.fix_mysql_index_syntax(content)

        # Check if content was modified
        was_modified = content != original_content

        if was_modified and not dry_run:
            # Create backup
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            file_path.rename(backup_path)

            # Write fixed content
            file_path.write_text(content, encoding="utf-8")

            print(f"✅ Fixed: {file_path}")
            print(f"   Backup: {backup_path}")
        elif was_modified and dry_run:
            print(f"🔧 Would fix: {file_path}")
        else:
            print(f"ℹ️  No fixes needed: {file_path}")

        return was_modified, issues

    except (OSError, UnicodeDecodeError) as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False, []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fix SQL syntax issues in MMF projects")
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan for SQL files (default: current directory)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be fixed without making changes"
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Additional file patterns to include (e.g., --include '*.ddl')",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Directories to exclude (e.g., --exclude node_modules)",
    )

    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        return 1

    print(f"🔍 Scanning for SQL files in: {directory}")

    # Build file patterns
    patterns = ["*.sql", "*.sql.j2"]
    patterns.extend(args.include)

    # Find SQL files
    sql_files = find_sql_files(directory, patterns)

    # Filter out excluded directories
    if args.exclude:
        filtered_files = []
        for file_path in sql_files:
            exclude_file = False
            for exclude_pattern in args.exclude:
                if exclude_pattern in str(file_path):
                    exclude_file = True
                    break
            if not exclude_file:
                filtered_files.append(file_path)
        sql_files = filtered_files

    if not sql_files:
        print("ℹ️  No SQL files found")
        return 0

    print(f"📁 Found {len(sql_files)} SQL file(s)")

    if args.dry_run:
        print("🧪 Running in dry-run mode (no changes will be made)")

    print()

    # Process files
    fixed_count = 0
    total_issues = []

    for file_path in sql_files:
        was_modified, issues = fix_sql_file(file_path, args.dry_run)
        if was_modified:
            fixed_count += 1
        total_issues.extend(issues)

    print()
    print("📊 Summary:")
    print(f"   Files processed: {len(sql_files)}")
    print(f"   Files {'that would be ' if args.dry_run else ''}fixed: {fixed_count}")
    print(f"   Total issues found: {len(total_issues)}")

    if total_issues:
        print("\n🔍 Issues found:")
        for issue in set(total_issues):  # Remove duplicates
            print(f"   • {issue}")

    if not args.dry_run and fixed_count > 0:
        print("\n✅ All fixes applied successfully!")
        print("💡 Tip: Test your SQL files with PostgreSQL to ensure compatibility")

    return 0


if __name__ == "__main__":
    sys.exit(main())
