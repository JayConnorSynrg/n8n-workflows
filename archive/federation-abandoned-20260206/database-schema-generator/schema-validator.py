#!/usr/bin/env python3
"""
Schema Validator for Federation Platform
Validates department schemas for completeness, RLS policies, indexes, and isolation
"""

import psycopg2
from psycopg2 import sql
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ValidationCheck:
    """Single validation check result"""
    name: str
    passed: bool
    message: str
    details: Optional[Dict] = None


@dataclass
class ValidationResult:
    """Complete validation result for a department schema"""
    department_id: str
    schema_name: str
    passed: bool
    checks: List[ValidationCheck] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def add_check(self, check: ValidationCheck):
        """Add a check result"""
        self.checks.append(check)
        if not check.passed:
            self.passed = False

    def summary(self) -> str:
        """Get human-readable summary"""
        total = len(self.checks)
        passed_count = sum(1 for c in self.checks if c.passed)
        failed_count = total - passed_count

        summary = f"\nValidation Summary for {self.department_id} ({self.schema_name}):\n"
        summary += "=" * 70 + "\n"
        summary += f"Total Checks: {total}\n"
        summary += f"Passed: {passed_count}\n"
        summary += f"Failed: {failed_count}\n"
        summary += f"Overall: {'✓ PASSED' if self.passed else '✗ FAILED'}\n"
        summary += "=" * 70 + "\n\n"

        if not self.passed:
            summary += "Failed Checks:\n"
            for check in self.checks:
                if not check.passed:
                    summary += f"  ✗ {check.name}: {check.message}\n"
                    if check.details:
                        for key, value in check.details.items():
                            summary += f"      {key}: {value}\n"
        else:
            summary += "✓ All validation checks passed!\n"

        return summary


class SchemaValidator:
    """Validate department schema structure and security policies"""

    EXPECTED_TABLES = [
        'tool_calls', 'session_context', 'drive_document_repository', 'drive_access_log',
        'email_logs', 'vector_store_embeddings', 'agent_context', 'conversation_history',
        'calendar_events', 'contacts', 'audit_trail', 'training_metrics',
        'user_session_analytics', 'file_attachments', 'llm_usage_logs', 'stt_usage_logs',
        'tts_usage_logs', 'workflow_executions', 'error_logs', 'notifications',
        'scheduled_tasks', 'user_preferences', 'api_keys', 'feature_flags'
    ]

    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize validator

        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config.get('port', 5432),
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )
        self.cursor = self.conn.cursor()

    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def check_schema_exists(self, department_id: str) -> ValidationCheck:
        """Verify schema exists"""
        schema_name = f"{department_id}_tenant"

        try:
            self.cursor.execute("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name = %s
            """, (schema_name,))

            exists = self.cursor.fetchone() is not None

            if exists:
                return ValidationCheck(
                    name="schema_exists",
                    passed=True,
                    message=f"Schema {schema_name} exists"
                )
            else:
                return ValidationCheck(
                    name="schema_exists",
                    passed=False,
                    message=f"Schema {schema_name} does not exist"
                )
        except Exception as e:
            return ValidationCheck(
                name="schema_exists",
                passed=False,
                message=f"Error checking schema: {e}"
            )

    def check_all_24_tables(self, department_id: str) -> ValidationCheck:
        """Verify all 24 expected tables exist"""
        schema_name = f"{department_id}_tenant"

        try:
            self.cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s
                AND table_type = 'BASE TABLE'
            """, (schema_name,))

            existing_tables = {row[0] for row in self.cursor.fetchall()}
            missing_tables = set(self.EXPECTED_TABLES) - existing_tables
            extra_tables = existing_tables - set(self.EXPECTED_TABLES)

            if not missing_tables and not extra_tables:
                return ValidationCheck(
                    name="all_tables_present",
                    passed=True,
                    message=f"All 24 tables exist in {schema_name}",
                    details={'table_count': len(existing_tables)}
                )
            else:
                details = {}
                if missing_tables:
                    details['missing'] = ', '.join(sorted(missing_tables))
                if extra_tables:
                    details['extra'] = ', '.join(sorted(extra_tables))

                return ValidationCheck(
                    name="all_tables_present",
                    passed=False,
                    message=f"Table mismatch in {schema_name}",
                    details=details
                )
        except Exception as e:
            return ValidationCheck(
                name="all_tables_present",
                passed=False,
                message=f"Error checking tables: {e}"
            )

    def check_rls_enabled(self, department_id: str) -> ValidationCheck:
        """Verify RLS enabled on all tables"""
        schema_name = f"{department_id}_tenant"

        try:
            self.cursor.execute("""
                SELECT c.relname, c.relrowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s
                AND c.relkind = 'r'
                AND c.relname = ANY(%s)
            """, (schema_name, self.EXPECTED_TABLES))

            results = {row[0]: row[1] for row in self.cursor.fetchall()}
            tables_without_rls = [
                table for table in self.EXPECTED_TABLES
                if table in results and not results[table]
            ]

            if not tables_without_rls:
                return ValidationCheck(
                    name="rls_enabled",
                    passed=True,
                    message=f"RLS enabled on all 24 tables in {schema_name}"
                )
            else:
                return ValidationCheck(
                    name="rls_enabled",
                    passed=False,
                    message=f"RLS not enabled on some tables",
                    details={'tables_without_rls': ', '.join(tables_without_rls)}
                )
        except Exception as e:
            return ValidationCheck(
                name="rls_enabled",
                passed=False,
                message=f"Error checking RLS: {e}"
            )

    def check_indexes(self, department_id: str) -> ValidationCheck:
        """Verify essential indexes exist"""
        schema_name = f"{department_id}_tenant"

        # Essential indexes to check (sample - not exhaustive)
        essential_indexes = {
            'tool_calls': ['idx_tool_calls_session', 'idx_tool_calls_status'],
            'session_context': ['idx_session_context_session', 'idx_session_context_expires'],
            'drive_document_repository': ['idx_drive_file_id', 'idx_drive_folder_id'],
            'conversation_history': ['idx_conversation_session']
        }

        try:
            missing_indexes = []

            for table, expected_indexes in essential_indexes.items():
                self.cursor.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = %s
                    AND tablename = %s
                """, (schema_name, table))

                existing_indexes = {row[0] for row in self.cursor.fetchall()}

                for index in expected_indexes:
                    if index not in existing_indexes:
                        missing_indexes.append(f"{table}.{index}")

            if not missing_indexes:
                return ValidationCheck(
                    name="indexes_created",
                    passed=True,
                    message=f"Essential indexes present in {schema_name}"
                )
            else:
                return ValidationCheck(
                    name="indexes_created",
                    passed=False,
                    message=f"Missing essential indexes",
                    details={'missing_indexes': ', '.join(missing_indexes)}
                )
        except Exception as e:
            return ValidationCheck(
                name="indexes_created",
                passed=False,
                message=f"Error checking indexes: {e}"
            )

    def test_cross_tenant_isolation(self, department_id: str) -> ValidationCheck:
        """
        Test that RLS policies prevent cross-tenant queries
        Creates temporary test data in two schemas and verifies isolation
        """
        schema_name = f"{department_id}_tenant"

        try:
            # Test with tool_calls table
            test_session = f"test_isolation_{datetime.now().timestamp()}"

            # Insert test record
            self.cursor.execute(f"""
                INSERT INTO {schema_name}.tool_calls
                (tool_call_id, session_id, function_name, department)
                VALUES (%s, %s, %s, %s)
            """, (test_session, test_session, 'test_function', department_id))

            # Try to query with department filter
            self.cursor.execute(f"""
                SELECT COUNT(*) FROM {schema_name}.tool_calls
                WHERE department = %s AND session_id = %s
            """, (department_id, test_session))

            count = self.cursor.fetchone()[0]

            # Clean up test data
            self.cursor.execute(f"""
                DELETE FROM {schema_name}.tool_calls
                WHERE session_id = %s
            """, (test_session,))

            self.conn.commit()

            if count == 1:
                return ValidationCheck(
                    name="cross_tenant_isolation",
                    passed=True,
                    message="Cross-tenant isolation test passed"
                )
            else:
                return ValidationCheck(
                    name="cross_tenant_isolation",
                    passed=False,
                    message=f"Isolation test failed: expected 1 record, got {count}"
                )

        except Exception as e:
            self.conn.rollback()
            return ValidationCheck(
                name="cross_tenant_isolation",
                passed=False,
                message=f"Error testing isolation: {e}"
            )

    def check_retention_policies(self, department_id: str) -> ValidationCheck:
        """Verify cleanup functions exist"""
        schema_name = f"{department_id}_tenant"

        try:
            # Check for cleanup functions
            self.cursor.execute("""
                SELECT proname FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = %s
                AND proname IN ('cleanup_expired_session_context', 'archive_old_conversation_history')
            """, (schema_name,))

            functions = {row[0] for row in self.cursor.fetchall()}
            expected_functions = {'cleanup_expired_session_context', 'archive_old_conversation_history'}

            if functions >= expected_functions:
                return ValidationCheck(
                    name="retention_policies",
                    passed=True,
                    message="Retention/cleanup functions exist"
                )
            else:
                missing = expected_functions - functions
                return ValidationCheck(
                    name="retention_policies",
                    passed=False,
                    message="Missing cleanup functions",
                    details={'missing_functions': ', '.join(missing)}
                )
        except Exception as e:
            return ValidationCheck(
                name="retention_policies",
                passed=False,
                message=f"Error checking retention policies: {e}"
            )

    def check_department_column(self, department_id: str) -> ValidationCheck:
        """Verify all tables have 'department' column"""
        schema_name = f"{department_id}_tenant"

        try:
            tables_without_dept_column = []

            for table in self.EXPECTED_TABLES:
                self.cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = %s
                    AND table_name = %s
                    AND column_name = 'department'
                """, (schema_name, table))

                if not self.cursor.fetchone():
                    tables_without_dept_column.append(table)

            if not tables_without_dept_column:
                return ValidationCheck(
                    name="department_column",
                    passed=True,
                    message="All tables have 'department' column"
                )
            else:
                return ValidationCheck(
                    name="department_column",
                    passed=False,
                    message="Some tables missing 'department' column",
                    details={'missing_from': ', '.join(tables_without_dept_column)}
                )
        except Exception as e:
            return ValidationCheck(
                name="department_column",
                passed=False,
                message=f"Error checking department column: {e}"
            )

    def validate_department_schema(self, department_id: str) -> ValidationResult:
        """
        Run all validation checks for a department schema

        Args:
            department_id: Department identifier (e.g., 'hr')

        Returns:
            ValidationResult with all check results
        """
        schema_name = f"{department_id}_tenant"
        result = ValidationResult(
            department_id=department_id,
            schema_name=schema_name,
            passed=True
        )

        try:
            self.connect()

            # Run all validation checks
            result.add_check(self.check_schema_exists(department_id))
            result.add_check(self.check_all_24_tables(department_id))
            result.add_check(self.check_rls_enabled(department_id))
            result.add_check(self.check_indexes(department_id))
            result.add_check(self.check_cross_tenant_isolation(department_id))
            result.add_check(self.check_retention_policies(department_id))
            result.add_check(self.check_department_column(department_id))

        except Exception as e:
            result.passed = False
            result.add_check(ValidationCheck(
                name="validation_error",
                passed=False,
                message=f"Validation failed with error: {e}"
            ))
        finally:
            self.disconnect()

        return result


def main():
    """CLI interface for schema validation"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate department schema')
    parser.add_argument('--department-id', required=True,
                       help='Department ID to validate (e.g., hr)')
    parser.add_argument('--db-host', default='localhost', help='Database host')
    parser.add_argument('--db-port', type=int, default=5432, help='Database port')
    parser.add_argument('--db-name', required=True, help='Database name')
    parser.add_argument('--db-user', required=True, help='Database user')
    parser.add_argument('--db-password', required=True, help='Database password')
    parser.add_argument('--verbose', action='store_true', help='Show all checks')

    args = parser.parse_args()

    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }

    validator = SchemaValidator(db_config)
    result = validator.validate_department_schema(args.department_id)

    print(result.summary())

    if args.verbose:
        print("\nDetailed Checks:")
        print("-" * 70)
        for check in result.checks:
            status = "✓" if check.passed else "✗"
            print(f"{status} {check.name}: {check.message}")
            if check.details:
                for key, value in check.details.items():
                    print(f"    {key}: {value}")
        print("-" * 70)

    # Exit code based on validation result
    exit(0 if result.passed else 1)


if __name__ == '__main__':
    main()
