"""
Tests for SQL Generator and database schema fixes.
"""

import tempfile
from pathlib import Path

import pytest

from mmf_new.core.application.sql import SQLGenerator


class TestSQLGenerator:
    """Test cases for the SQL generator utility."""

    def test_format_jsonb_value_string(self):
        """Test JSONB value formatting for strings."""
        generator = SQLGenerator()

        # Plain string should be JSON-quoted
        result = generator.format_jsonb_value("sandbox")
        assert result == '"sandbox"'

        # Already JSON string should remain as-is
        result = generator.format_jsonb_value('"already_quoted"')
        assert result == '"already_quoted"'

    def test_format_jsonb_value_objects(self):
        """Test JSONB value formatting for objects and arrays."""
        generator = SQLGenerator()

        # Object
        result = generator.format_jsonb_value({"enabled": True, "timeout": 30})
        assert '"enabled": true' in result
        assert '"timeout": 30' in result

        # Array
        result = generator.format_jsonb_value(["option1", "option2"])
        assert result == '["option1", "option2"]'

        # Boolean
        result = generator.format_jsonb_value(True)
        assert result == "true"

        # Number
        result = generator.format_jsonb_value(42)
        assert result == "42"

    def test_create_table_with_indexes(self):
        """Test table creation with separate index statements."""
        generator = SQLGenerator()

        result = generator.create_table_with_indexes(
            table_name="orders",
            columns=[
                "id UUID PRIMARY KEY DEFAULT uuid_generate_v4()",
                "order_id VARCHAR(255) UNIQUE NOT NULL",
                "status VARCHAR(100) NOT NULL",
                "correlation_id VARCHAR(255) NOT NULL",
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            ],
            indexes=[
                {"name": "idx_orders_correlation_id", "columns": ["correlation_id"]},
                {"name": "idx_orders_status", "columns": ["status"]},
            ],
        )

        # Check table creation
        assert "CREATE TABLE orders (" in result
        assert "id UUID PRIMARY KEY DEFAULT uuid_generate_v4()" in result
        assert "status VARCHAR(100) NOT NULL" in result

        # Check separate index creation
        assert (
            "CREATE INDEX idx_orders_correlation_id ON orders USING btree(correlation_id);"
            in result
        )
        assert "CREATE INDEX idx_orders_status ON orders USING btree(status);" in result

        # Should not contain inline INDEX declarations
        assert "INDEX idx_orders_correlation_id (" not in result

    def test_fix_mysql_index_syntax(self):
        """Test fixing MySQL-style inline INDEX syntax."""
        generator = SQLGenerator()

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

        # Check that inline INDEX declarations are removed
        assert "INDEX idx_orders_correlation_id (" not in fixed_sql
        assert "INDEX idx_orders_status (" not in fixed_sql

        # Check that separate CREATE INDEX statements are added
        assert (
            "CREATE INDEX idx_orders_correlation_id ON orders(correlation_id);"
            in fixed_sql
        )
        assert "CREATE INDEX idx_orders_status ON orders(status);" in fixed_sql

    def test_validate_postgresql_syntax(self):
        """Test PostgreSQL syntax validation."""
        generator = SQLGenerator()

        # Valid SQL should return no issues
        valid_sql = """
        CREATE TABLE orders (
            id UUID PRIMARY KEY,
            status VARCHAR(100)
        );
        CREATE INDEX idx_orders_status ON orders(status);
        """
        issues = generator.validate_postgresql_syntax(valid_sql)
        assert len(issues) == 0

        # Invalid SQL with inline INDEX should return issues
        invalid_sql = """
        CREATE TABLE orders (
            id UUID PRIMARY KEY,
            status VARCHAR(100),
            INDEX idx_status (status)
        );
        """
        issues = generator.validate_postgresql_syntax(invalid_sql)
        assert len(issues) > 0
        assert any("MySQL-style inline INDEX" in issue for issue in issues)

    def test_generate_insert_with_jsonb(self):
        """Test INSERT statement generation with JSONB values."""
        generator = SQLGenerator()

        result = generator.generate_insert_with_jsonb(
            table_name="configuration",
            columns=["config_key", "config_value", "config_type"],
            values=[
                [
                    "'feature_flags.payment_gateway'",
                    generator.format_jsonb_value("sandbox"),
                    "'feature_flag'",
                ],
                ["'database.pool_size'", generator.format_jsonb_value(10), "'setting'"],
            ],
        )

        assert (
            "INSERT INTO configuration (config_key, config_value, config_type) VALUES"
            in result
        )
        assert "'feature_flags.payment_gateway', \"sandbox\", 'feature_flag'" in result
        assert "'database.pool_size', 10, 'setting'" in result

    def test_complex_scenario(self):
        """Test a complex scenario combining multiple fixes."""
        generator = SQLGenerator()

        # Create a complex table with both issues
        complex_sql = generator.create_table_with_indexes(
            table_name="events",
            columns=[
                "id UUID PRIMARY KEY DEFAULT uuid_generate_v4()",
                "event_type VARCHAR(100) NOT NULL",
                "event_data JSONB NOT NULL",
                "correlation_id VARCHAR(255) NOT NULL",
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            ],
            indexes=[
                {"name": "idx_events_type", "columns": ["event_type"]},
                {"name": "idx_events_correlation", "columns": ["correlation_id"]},
                {"name": "idx_events_data", "columns": ["event_data"], "type": "gin"},
            ],
            constraints=["UNIQUE(correlation_id, event_type)"],
        )

        # Generate JSONB insert
        insert_sql = generator.generate_insert_with_jsonb(
            table_name="events",
            columns=["event_type", "event_data", "correlation_id"],
            values=[
                [
                    "'order_created'",
                    generator.format_jsonb_value(
                        {"order_id": "12345", "amount": 99.99}
                    ),
                    "'corr-123'",
                ],
                [
                    "'payment_processed'",
                    generator.format_jsonb_value(
                        {"payment_id": "pay-456", "status": "success"}
                    ),
                    "'corr-124'",
                ],
            ],
        )

        # Validate the generated SQL
        issues = generator.validate_postgresql_syntax(complex_sql)
        assert len(issues) == 0

        issues = generator.validate_postgresql_syntax(insert_sql)
        assert len(issues) == 0

        # Verify the content
        assert "CREATE TABLE events (" in complex_sql
        assert (
            "CREATE INDEX idx_events_type ON events USING btree(event_type);"
            in complex_sql
        )
        assert (
            "CREATE INDEX idx_events_data ON events USING gin(event_data);"
            in complex_sql
        )
        assert "UNIQUE(correlation_id, event_type)" in complex_sql

        assert '"order_id": "12345"' in insert_sql
        assert '"amount": 99.99' in insert_sql


@pytest.fixture
def temp_sql_file():
    """Create a temporary SQL file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write(
            """
        CREATE TABLE test_table (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            INDEX idx_name (name)
        );
        """
        )
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()
    backup_path = temp_path.with_suffix(temp_path.suffix + ".bak")
    if backup_path.exists():
        backup_path.unlink()


def test_sql_file_fixing(temp_sql_file):
    """Test fixing SQL files directly."""
    generator = SQLGenerator()

    # Read original content
    original_content = temp_sql_file.read_text()
    assert "INDEX idx_name (name)" in original_content

    # Fix the syntax
    fixed_content = generator.fix_mysql_index_syntax(original_content)

    # Write back the fixed content
    temp_sql_file.write_text(fixed_content)

    # Verify the fix
    new_content = temp_sql_file.read_text()
    assert "INDEX idx_name (name)" not in new_content
    assert "CREATE INDEX idx_name ON test_table(name);" in new_content
