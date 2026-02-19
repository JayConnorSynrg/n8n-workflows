#!/usr/bin/env python3
"""
Migration Runner for Federation Platform
Handles database schema migration execution, rollback, and validation
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class MigrationResult:
    """Result of migration execution"""
    success: bool
    applied_count: int
    failed_migrations: List[str]
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class RollbackResult:
    """Result of migration rollback"""
    success: bool
    rolled_back_count: int
    error_message: Optional[str] = None


class MigrationRunner:
    """Execute and manage database migrations for department schemas"""

    def __init__(self, db_config: Dict[str, str], migrations_dir: str = "migrations"):
        """
        Initialize migration runner

        Args:
            db_config: Database connection configuration
            migrations_dir: Directory containing migration SQL files
        """
        self.db_config = db_config
        self.migrations_dir = Path(migrations_dir)
        self.rollback_dir = self.migrations_dir / "rollback"
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config.get('port', 5432),
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            self.conn.autocommit = False
            self.cursor = self.conn.cursor()
            print(f"Connected to database: {self.db_config['database']}")
        except Exception as e:
            raise Exception(f"Failed to connect to database: {e}")

    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("Database connection closed")

    def get_pending_migrations(self, department_id: str) -> List[str]:
        """
        Get list of migrations not yet applied to a department schema

        Args:
            department_id: Department identifier

        Returns:
            List of migration file names (sorted)
        """
        # Get all migration files
        migration_files = sorted([
            f.name for f in self.migrations_dir.glob('*.sql')
            if f.is_file() and not f.name.startswith('.')
        ])

        # Get applied migrations from tracking table
        schema_name = f"{department_id}_tenant"

        try:
            self.cursor.execute(f"""
                SELECT migration_name FROM federation.schema_migrations
                WHERE department_id = %s
                ORDER BY applied_at
            """, (department_id,))

            applied = {row[0] for row in self.cursor.fetchall()}
            pending = [m for m in migration_files if m not in applied]

            print(f"Found {len(pending)} pending migrations for {department_id}")
            return pending

        except psycopg2.Error as e:
            # If tracking table doesn't exist, all migrations are pending
            print(f"Migration tracking table not found: {e}")
            return migration_files

    def create_migration_tracking_table(self):
        """Create migration tracking table in federation schema"""
        try:
            self.cursor.execute("""
                CREATE SCHEMA IF NOT EXISTS federation;

                CREATE TABLE IF NOT EXISTS federation.schema_migrations (
                    id SERIAL PRIMARY KEY,
                    department_id VARCHAR(100) NOT NULL,
                    migration_name VARCHAR(255) NOT NULL,
                    applied_at TIMESTAMPTZ DEFAULT NOW(),
                    duration_seconds NUMERIC(10,3),
                    CONSTRAINT unique_dept_migration UNIQUE(department_id, migration_name)
                );

                CREATE INDEX IF NOT EXISTS idx_schema_migrations_dept
                    ON federation.schema_migrations(department_id);
            """)
            self.conn.commit()
            print("Migration tracking table created/verified")
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Failed to create migration tracking table: {e}")

    def execute_migration(self, migration_file: str, department_id: str,
                         context: Dict[str, str]) -> bool:
        """
        Execute a single migration file with Jinja2 template substitution

        Args:
            migration_file: Name of migration SQL file
            department_id: Department identifier
            context: Template context variables

        Returns:
            True if successful, False otherwise
        """
        migration_path = self.migrations_dir / migration_file

        try:
            # Read migration file
            with open(migration_path, 'r') as f:
                migration_sql = f.read()

            # Simple template substitution (replace {{ variable }})
            for key, value in context.items():
                migration_sql = migration_sql.replace(f"{{{{ {key} }}}}", value)

            # Execute migration
            start_time = datetime.now()
            self.cursor.execute(migration_sql)
            duration = (datetime.now() - start_time).total_seconds()

            # Record migration in tracking table
            self.cursor.execute("""
                INSERT INTO federation.schema_migrations
                (department_id, migration_name, duration_seconds)
                VALUES (%s, %s, %s)
            """, (department_id, migration_file, duration))

            self.conn.commit()
            print(f"✓ Applied migration: {migration_file} ({duration:.2f}s)")
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"✗ Failed migration: {migration_file}")
            print(f"  Error: {e}")
            return False

    def apply_migrations(self, department_id: str, department_name: str) -> MigrationResult:
        """
        Apply all pending migrations for a department schema

        Args:
            department_id: Department identifier (e.g., 'hr')
            department_name: Human-readable name (e.g., 'Human Resources')

        Returns:
            MigrationResult with execution details
        """
        start_time = datetime.now()

        try:
            self.connect()
            self.create_migration_tracking_table()

            # Get pending migrations
            pending = self.get_pending_migrations(department_id)

            if not pending:
                print(f"No pending migrations for {department_id}")
                return MigrationResult(
                    success=True,
                    applied_count=0,
                    failed_migrations=[]
                )

            # Prepare template context
            schema_name = f"{department_id}_tenant"
            role_name = f"{department_id}_role"
            context = {
                'department_id': department_id,
                'department_name': department_name,
                'department_schema': schema_name,
                'department_role': role_name,
                'timestamp': datetime.now().isoformat()
            }

            # Apply migrations
            applied = 0
            failed = []

            for migration_file in pending:
                if self.execute_migration(migration_file, department_id, context):
                    applied += 1
                else:
                    failed.append(migration_file)
                    # Stop on first failure
                    break

            duration = (datetime.now() - start_time).total_seconds()

            if failed:
                return MigrationResult(
                    success=False,
                    applied_count=applied,
                    failed_migrations=failed,
                    error_message=f"Migration failed: {failed[0]}",
                    duration_seconds=duration
                )
            else:
                print(f"\n✓ All migrations applied successfully ({applied} total)")
                return MigrationResult(
                    success=True,
                    applied_count=applied,
                    failed_migrations=[],
                    duration_seconds=duration
                )

        except Exception as e:
            return MigrationResult(
                success=False,
                applied_count=0,
                failed_migrations=[],
                error_message=str(e)
            )
        finally:
            self.disconnect()

    def get_rollback_migrations(self, department_id: str, target_version: int) -> List[str]:
        """
        Get list of migrations to rollback to reach target version

        Args:
            department_id: Department identifier
            target_version: Target migration version (0 = rollback all)

        Returns:
            List of rollback file names (reverse chronological order)
        """
        try:
            self.cursor.execute(f"""
                SELECT migration_name FROM federation.schema_migrations
                WHERE department_id = %s
                ORDER BY applied_at DESC
                LIMIT %s
            """, (department_id, 100))  # Safety limit

            applied = [row[0] for row in self.cursor.fetchall()]

            # Filter to migrations after target version
            if target_version > 0:
                # Assumes migration files start with version number (001_, 002_, etc.)
                rollback_list = [
                    m for m in applied
                    if int(m.split('_')[0]) > target_version
                ]
            else:
                rollback_list = applied

            # Get corresponding rollback files
            rollback_files = []
            for migration in rollback_list:
                rollback_file = self.rollback_dir / migration.replace('.sql', '_rollback.sql')
                if rollback_file.exists():
                    rollback_files.append(rollback_file.name)
                else:
                    print(f"Warning: Rollback file not found for {migration}")

            return rollback_files

        except Exception as e:
            print(f"Error getting rollback migrations: {e}")
            return []

    def execute_rollback(self, rollback_file: str, department_id: str,
                        context: Dict[str, str]) -> bool:
        """
        Execute a single rollback migration

        Args:
            rollback_file: Name of rollback SQL file
            department_id: Department identifier
            context: Template context variables

        Returns:
            True if successful, False otherwise
        """
        rollback_path = self.rollback_dir / rollback_file

        try:
            # Read rollback file
            with open(rollback_path, 'r') as f:
                rollback_sql = f.read()

            # Template substitution
            for key, value in context.items():
                rollback_sql = rollback_sql.replace(f"{{{{ {key} }}}}", value)

            # Execute rollback
            self.cursor.execute(rollback_sql)

            # Remove migration from tracking table
            migration_name = rollback_file.replace('_rollback.sql', '.sql')
            self.cursor.execute("""
                DELETE FROM federation.schema_migrations
                WHERE department_id = %s AND migration_name = %s
            """, (department_id, migration_name))

            self.conn.commit()
            print(f"✓ Rolled back: {rollback_file}")
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"✗ Failed rollback: {rollback_file}")
            print(f"  Error: {e}")
            return False

    def rollback_migrations(self, department_id: str, target_version: int = 0) -> RollbackResult:
        """
        Rollback migrations to a specific version

        Args:
            department_id: Department identifier
            target_version: Target version (0 = rollback all, drops schema)

        Returns:
            RollbackResult with execution details
        """
        try:
            self.connect()

            schema_name = f"{department_id}_tenant"
            role_name = f"{department_id}_role"

            context = {
                'department_id': department_id,
                'department_schema': schema_name,
                'department_role': role_name
            }

            if target_version == 0:
                # Nuclear option: drop entire schema
                print(f"WARNING: Dropping schema {schema_name} entirely")
                response = input("Are you sure? (yes/no): ")
                if response.lower() != 'yes':
                    print("Rollback cancelled")
                    return RollbackResult(success=False, rolled_back_count=0,
                                        error_message="Cancelled by user")

                self.cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
                self.cursor.execute("""
                    DELETE FROM federation.schema_migrations
                    WHERE department_id = %s
                """, (department_id,))
                self.conn.commit()

                print(f"✓ Schema {schema_name} dropped successfully")
                return RollbackResult(success=True, rolled_back_count=1)

            else:
                # Rollback specific migrations
                rollbacks = self.get_rollback_migrations(department_id, target_version)

                if not rollbacks:
                    print(f"No migrations to rollback for {department_id}")
                    return RollbackResult(success=True, rolled_back_count=0)

                rolled_back = 0
                for rollback_file in rollbacks:
                    if self.execute_rollback(rollback_file, department_id, context):
                        rolled_back += 1
                    else:
                        break

                print(f"\n✓ Rolled back {rolled_back} migrations")
                return RollbackResult(success=True, rolled_back_count=rolled_back)

        except Exception as e:
            return RollbackResult(
                success=False,
                rolled_back_count=0,
                error_message=str(e)
            )
        finally:
            self.disconnect()


def main():
    """CLI interface for migration runner"""
    import argparse

    parser = argparse.ArgumentParser(description='Run database migrations for department schemas')
    parser.add_argument('command', choices=['apply', 'rollback', 'status'],
                       help='Migration command')
    parser.add_argument('--department-id', required=True,
                       help='Department ID (e.g., hr, accounting)')
    parser.add_argument('--department-name',
                       help='Department name (required for apply)')
    parser.add_argument('--target-version', type=int, default=0,
                       help='Target version for rollback (0=drop schema)')
    parser.add_argument('--db-host', default='localhost', help='Database host')
    parser.add_argument('--db-port', type=int, default=5432, help='Database port')
    parser.add_argument('--db-name', required=True, help='Database name')
    parser.add_argument('--db-user', required=True, help='Database user')
    parser.add_argument('--db-password', required=True, help='Database password')

    args = parser.parse_args()

    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }

    runner = MigrationRunner(db_config)

    if args.command == 'apply':
        if not args.department_name:
            print("Error: --department-name required for apply command")
            sys.exit(1)

        result = runner.apply_migrations(args.department_id, args.department_name)

        if result.success:
            print(f"\n✓ SUCCESS: Applied {result.applied_count} migrations")
            print(f"  Duration: {result.duration_seconds:.2f}s")
            sys.exit(0)
        else:
            print(f"\n✗ FAILED: {result.error_message}")
            print(f"  Applied: {result.applied_count}")
            print(f"  Failed: {', '.join(result.failed_migrations)}")
            sys.exit(1)

    elif args.command == 'rollback':
        result = runner.rollback_migrations(args.department_id, args.target_version)

        if result.success:
            print(f"\n✓ SUCCESS: Rolled back {result.rolled_back_count} migrations")
            sys.exit(0)
        else:
            print(f"\n✗ FAILED: {result.error_message}")
            sys.exit(1)

    elif args.command == 'status':
        try:
            runner.connect()
            pending = runner.get_pending_migrations(args.department_id)
            print(f"\nMigration status for {args.department_id}:")
            print(f"  Pending migrations: {len(pending)}")
            if pending:
                print("\n  Files:")
                for m in pending:
                    print(f"    - {m}")
            runner.disconnect()
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
