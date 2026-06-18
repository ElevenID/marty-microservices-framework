"""
SQL generation utilities for the infrastructure layer.

This module provides utilities to generate valid PostgreSQL SQL, avoiding common
syntax errors like inline INDEX declarations and unquoted JSONB values.
"""

import json
import re
from typing import Any


class SQLGenerator:
    """Utilities for generating valid PostgreSQL SQL."""

    _IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$")

    @staticmethod
    def quote_identifier(identifier: str) -> str:
        """Validate and quote a SQL identifier."""
        if not SQLGenerator._IDENTIFIER_RE.fullmatch(identifier):
            raise ValueError(f"Invalid SQL identifier: {identifier}")
        return ".".join(f'"{part}"' for part in identifier.split("."))

    @staticmethod
    def format_sql_literal(value: Any) -> str:
        """Format a scalar or JSON value as a SQL literal."""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, int | float):
            return str(value)
        if isinstance(value, dict | list):
            value = SQLGenerator.format_jsonb_value(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

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
        constraints: list[str] | None = None,
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
        sql_parts.append(create_table_sql)

        # Add CREATE INDEX statements
        if indexes:
            for index in indexes:
                index_name = index["name"]
                index_columns = index["columns"]
                index_type = index.get("type", "btree")

                if isinstance(index_columns, list):
                    columns_str = ", ".join(index_columns)
                else:
                    columns_str = index_columns

                index_sql = (
                    f"CREATE INDEX {index_name} ON {table_name} USING {index_type}({columns_str});"
                )
                sql_parts.append(index_sql)

        return "\n\n".join(sql_parts)

    @staticmethod
    def generate_insert_with_jsonb(
        table_name: str, columns: list[str], values: list[list[Any]]
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

        quoted_table = SQLGenerator.quote_identifier(table_name)
        columns_str = ", ".join(SQLGenerator.quote_identifier(col) for col in columns)
        insert_sql = f"INSERT INTO {quoted_table} ({columns_str}) VALUES\n"  # nosec B608

        value_rows = []
        for row in values:
            formatted_values = []
            for value in row:
                formatted_values.append(SQLGenerator.format_sql_literal(value))

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
        table_pattern = r"CREATE TABLE\s+(\w+)\s*\((.*?)\);"
        index_pattern = r",?\s*INDEX\s+(\w+)\s*\(([^)]+)\)"

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
            clean_content = re.sub(r",\s*$", "", clean_content.strip())

            # Build the result
            fixed_table_sql = f"CREATE TABLE {table_name} (\n{clean_content}\n);"

            # Add CREATE INDEX statements
            for index_name, index_columns in reversed(
                indexes
            ):  # Reverse to maintain original order
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
        issues = []

        # Check for MySQL-style inline INDEX declarations
        if re.search(
            r"CREATE TABLE.*INDEX\s+\w+\s*\([^)]+\)",
            sql_content,
            re.DOTALL | re.IGNORECASE,
        ):
            issues.append(
                "Found MySQL-style inline INDEX declarations. Use separate CREATE INDEX statements."
            )

        # Check for unquoted JSON values in INSERT statements
        jsonb_pattern = r"INSERT INTO.*\([^)]*config_value[^)]*\).*VALUES.*'([^']*)'(?![^(]*\))"
        matches = re.findall(jsonb_pattern, sql_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            if (
                match
                and not match.startswith(('"', "[", "{"))
                and match not in ("true", "false", "null")
            ):
                try:
                    # Try to parse as JSON
                    json.loads(match)
                except json.JSONDecodeError:
                    issues.append(
                        f"Potentially unquoted JSON value for JSONB: '{match}'. Should be JSON-quoted."
                    )

        return issues
