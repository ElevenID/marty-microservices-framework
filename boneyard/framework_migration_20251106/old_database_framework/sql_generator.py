"""
Database SQL Generation Utilities

This module provides utilities to generate valid PostgreSQL SQL, avoiding common
syntax errors like inline INDEX declarations and unquoted JSONB values.
"""

import json
import re
from typing import Any


class SQLGenerator:
    """Utilities for generating valid PostgreSQL SQL."""

    @staticmethod
    def format_jsonb_value(value: Any) -> str:
        """
        Format a value for insertion into a JSONB column.

        Args:
            value: The value to format (can be dict, list, str, int, bool, etc.)

        Returns:
            Properly JSON-quoted string for PostgreSQL JSONB
        """
        if isinstance(value, str):
            # If it's already a JSON string, validate and return as-is
            try:
                json.loads(value)
                return value
            except json.JSONDecodeError:
                # It's a plain string, need to JSON-encode it
                return json.dumps(value)
        else:
            # For objects, arrays, numbers, booleans, null
            return json.dumps(value)

    @staticmethod
    def create_table_with_indexes(
        table_name: str,
        columns: list[str],
        indexes: list[dict[str, str | list[str]]] | None = None,
        constraints: list[str] | None = None
    ) -> str:
        """
        Generate CREATE TABLE statement with separate CREATE INDEX statements.

        Args:
            table_name: Name of the table
            columns: List of column definitions
            indexes: List of index definitions, each with 'name', 'columns', and optional 'type'
            constraints: List of table constraints (PRIMARY KEY, UNIQUE, etc.)

        Returns:
            Complete SQL with CREATE TABLE followed by CREATE INDEX statements
        """
        sql_parts = []

        # Build CREATE TABLE statement
        create_table_sql = f"CREATE TABLE {table_name} (\n"
        all_definitions = columns.copy()

        if constraints:
            all_definitions.extend(constraints)

        create_table_sql += ",\n".join(f"    {definition}" for definition in all_definitions)
        create_table_sql += "\n);"
        sql_parts.append(create_table_sql)        # Add CREATE INDEX statements
        if indexes:
            for index in indexes:
                index_name = index['name']
                index_columns = index['columns']
                index_type = index.get('type', 'btree')

                if isinstance(index_columns, list):
                    columns_str = ", ".join(index_columns)
                else:
                    columns_str = index_columns

                index_sql = f"CREATE INDEX {index_name} ON {table_name} USING {index_type}({columns_str});"
                sql_parts.append(index_sql)

        return "\n\n".join(sql_parts)

    @staticmethod
    def generate_insert_with_jsonb(
        table_name: str,
        columns: list[str],
        values: list[list[Any]]
    ) -> str:
        """
        Generate INSERT statement with properly formatted JSONB values.

        Args:
            table_name: Name of the table
            columns: List of column names
            values: List of value rows, where each row is a list of values

        Returns:
            INSERT statement with properly quoted JSONB values
        """
        if not values:
            return f"-- No data to insert into {table_name}"

        columns_str = ", ".join(columns)
        insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES\n"

        value_rows = []
        for row in values:
            formatted_values = []
            for value in row:
                if value is None:
                    formatted_values.append("NULL")
                elif isinstance(value, str) and not value.startswith("'"):
                    # Assume it's a regular string value, not a function call
                    formatted_values.append(f"'{value}'")
                else:
                    # Keep as-is (for numbers, function calls like NOW(), etc.)
                    formatted_values.append(str(value))

            value_rows.append(f"  ({', '.join(formatted_values)})")

        insert_sql += ",\n".join(value_rows) + ";"
        return insert_sql

    @staticmethod
    def fix_mysql_index_syntax(sql_content: str) -> str:
        """
        Fix MySQL-style inline INDEX declarations in CREATE TABLE statements.

        Converts:
            CREATE TABLE orders (
                id UUID PRIMARY KEY,
                status VARCHAR(100),
                INDEX idx_status (status)
            );

        To:
            CREATE TABLE orders (
                id UUID PRIMARY KEY,
                status VARCHAR(100)
            );
            CREATE INDEX idx_status ON orders(status);

        Args:
            sql_content: SQL content that may contain MySQL-style INDEX syntax

        Returns:
            Fixed SQL with separate CREATE INDEX statements
        """
        # Pattern to match CREATE TABLE statements with inline INDEX declarations
        table_pattern = r'CREATE TABLE\s+(\w+)\s*\((.*?)\);'
        index_pattern = r',?\s*INDEX\s+(\w+)\s*\(([^)]+)\)'

        def fix_table(match):
            table_name = match.group(1)
            table_content = match.group(2)

            # Find all INDEX declarations
            indexes = []
            index_matches = list(re.finditer(index_pattern, table_content, re.IGNORECASE))

            if not index_matches:
                # No inline indexes, return as-is
                return match.group(0)

            # Remove INDEX declarations from table content
            clean_content = table_content
            for index_match in reversed(index_matches):  # Reverse to maintain positions
                index_name = index_match.group(1)
                index_columns = index_match.group(2)
                indexes.append((index_name, index_columns))

                # Remove the INDEX declaration
                start, end = index_match.span()
                clean_content = clean_content[:start] + clean_content[end:]

            # Clean up any trailing commas
            clean_content = re.sub(r',\s*$', '', clean_content.strip())

            # Build the result
            fixed_table_sql = f"CREATE TABLE {table_name} (\n{clean_content}\n);"

            # Add CREATE INDEX statements
            for index_name, index_columns in reversed(indexes):  # Reverse to maintain original order
                fixed_table_sql += f"\nCREATE INDEX {index_name} ON {table_name}({index_columns});"

            return fixed_table_sql

        return re.sub(table_pattern, fix_table, sql_content, flags=re.DOTALL | re.IGNORECASE)

    @staticmethod
    def validate_postgresql_syntax(sql_content: str) -> list[str]:
        """
        Validate SQL for common PostgreSQL compatibility issues.

        Returns:
            List of validation warnings/errors
        """
        result_issues = []

        # Check for MySQL-style inline INDEX declarations
        if re.search(r'CREATE TABLE.*INDEX\s+\w+\s*\([^)]+\)', sql_content, re.DOTALL | re.IGNORECASE):
            result_issues.append("Found MySQL-style inline INDEX declarations. Use separate CREATE INDEX statements.")

        # Check for unquoted JSON values in INSERT statements
        jsonb_pattern = r"INSERT INTO.*\([^)]*config_value[^)]*\).*VALUES.*'([^']*)'(?![^(]*\))"
        matches = re.findall(jsonb_pattern, sql_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            if match and not match.startswith(('"', '[', '{')) and match not in ('true', 'false', 'null'):
                try:
                    # Try to parse as JSON
                    json.loads(match)
                except json.JSONDecodeError:
                    result_issues.append(f"Potentially unquoted JSON value for JSONB: '{match}'. Should be JSON-quoted.")

        return result_issues
# Example usage and tests
if __name__ == "__main__":
    generator = SQLGenerator()

    # Test JSONB formatting
    print("JSONB formatting tests:")
    print(f"String: {generator.format_jsonb_value('sandbox')}")
    print(f"Object: {generator.format_jsonb_value({'enabled': True, 'timeout': 30})}")
    print(f"Array: {generator.format_jsonb_value(['option1', 'option2'])}")
    print(f"Number: {generator.format_jsonb_value(42)}")
    print(f"Boolean: {generator.format_jsonb_value(True)}")

    # Test table creation with indexes
    print("\nTable creation with indexes:")
    table_sql = generator.create_table_with_indexes(
        table_name="orders",
        columns=[
            "id UUID PRIMARY KEY DEFAULT uuid_generate_v4()",
            "order_id VARCHAR(255) UNIQUE NOT NULL",
            "status VARCHAR(100) NOT NULL",
            "correlation_id VARCHAR(255) NOT NULL",
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ],
        indexes=[
            {"name": "idx_orders_correlation_id", "columns": ["correlation_id"]},
            {"name": "idx_orders_status", "columns": ["status"]},
            {"name": "idx_orders_created_at", "columns": ["created_at"], "type": "btree"}
        ]
    )
    print(table_sql)

    # Test MySQL syntax fixing
    print("\nMySQL syntax fixing:")
    mysql_sql = """
    CREATE TABLE orders (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        order_id VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(100) NOT NULL,
        correlation_id VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_orders_correlation_id (correlation_id),
        INDEX idx_orders_status (status)
    );
    """
    fixed_sql = generator.fix_mysql_index_syntax(mysql_sql)
    print(fixed_sql)

    # Test validation
    print("\nValidation issues:")
    validation_issues = generator.validate_postgresql_syntax(mysql_sql)
    for issue in validation_issues:
        print(f"- {issue}")
