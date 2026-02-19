#!/usr/bin/env python3
"""
Federation Platform - Schema Generator CLI
Main entry point for generating department database schemas

Usage:
    python generate-schema.py --department=Legal --department-id=legal
    python generate-schema.py --department=HR --department-id=hr --apply
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict
import argparse


def render_template(template_path: str, context: Dict[str, str], output_path: str) -> None:
    """
    Render Jinja2-style template with context variables

    Args:
        template_path: Path to template file
        context: Dictionary of template variables
        output_path: Path to save rendered output
    """
    with open(template_path, 'r') as f:
        template_content = f.read()

    # Simple template substitution (replace {{ variable }})
    rendered = template_content
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)

    with open(output_path, 'w') as f:
        f.write(rendered)

    print(f"Generated: {output_path}")


def generate_schema(department_name: str, department_id: str, output_dir: str) -> str:
    """
    Generate department schema SQL from template

    Args:
        department_name: Human-readable department name
        department_id: Department slug (e.g., 'hr', 'legal')
        output_dir: Directory to save generated SQL

    Returns:
        Path to generated SQL file
    """
    schema_name = f"{department_id}_tenant"
    role_name = f"{department_id}_role"
    timestamp = datetime.now().isoformat()

    context = {
        'department_name': department_name,
        'department_id': department_id,
        'department_schema': schema_name,
        'department_role': role_name,
        'timestamp': timestamp
    }

    # Render schema template
    template_path = Path(__file__).parent / 'schema-template.sql.j2'
    output_file = Path(output_dir) / f'schema_{department_id}_tenant.sql'

    render_template(str(template_path), context, str(output_file))

    return str(output_file)


def generate_rls_policies(department_id: str, output_dir: str) -> str:
    """
    Generate RLS policies using rls-policies.py

    Args:
        department_id: Department slug
        output_dir: Directory to save generated SQL

    Returns:
        Path to generated RLS SQL file
    """
    from rls_policies import RLSPolicyGenerator

    schema_name = f"{department_id}_tenant"
    output_file = Path(output_dir) / f'rls_policies_{department_id}.sql'

    generator = RLSPolicyGenerator(department_id, schema_name)
    generator.export_policies_to_sql(str(output_file))

    print(f"Generated: {output_file}")
    return str(output_file)


def apply_schema(schema_file: str, db_config: Dict[str, str], department_id: str,
                department_name: str) -> bool:
    """
    Apply generated schema to database

    Args:
        schema_file: Path to schema SQL file
        db_config: Database connection config
        department_id: Department slug
        department_name: Human-readable name

    Returns:
        True if successful
    """
    from migration_runner import MigrationRunner

    # Move schema file to migrations directory
    migrations_dir = Path(__file__).parent / 'migrations'
    migrations_dir.mkdir(exist_ok=True)

    migration_file = migrations_dir / f'001_create_schema_{department_id}.sql'

    # Copy schema file to migrations
    import shutil
    shutil.copy(schema_file, migration_file)

    print(f"\nApplying schema to database...")
    print(f"  Department: {department_name} ({department_id})")
    print(f"  Schema: {department_id}_tenant")

    runner = MigrationRunner(db_config, str(migrations_dir))
    result = runner.apply_migrations(department_id, department_name)

    if result.success:
        print(f"\n✓ Schema applied successfully!")
        print(f"  Applied {result.applied_count} migrations")
        print(f"  Duration: {result.duration_seconds:.2f}s")
        return True
    else:
        print(f"\n✗ Schema application failed!")
        print(f"  Error: {result.error_message}")
        if result.failed_migrations:
            print(f"  Failed migrations: {', '.join(result.failed_migrations)}")
        return False


def validate_schema(department_id: str, db_config: Dict[str, str]) -> bool:
    """
    Validate generated schema

    Args:
        department_id: Department slug
        db_config: Database connection config

    Returns:
        True if validation passed
    """
    from schema_validator import SchemaValidator

    print(f"\nValidating schema for {department_id}...")

    validator = SchemaValidator(db_config)
    result = validator.validate_department_schema(department_id)

    print(result.summary())

    return result.passed


def main():
    parser = argparse.ArgumentParser(
        description='Generate department database schema for Federation Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate schema SQL only
  python generate-schema.py --department="Legal Department" --department-id=legal

  # Generate and apply to database
  python generate-schema.py --department=HR --department-id=hr --apply \\
    --db-name=federation --db-user=postgres --db-password=secret

  # Generate, apply, and validate
  python generate-schema.py --department=Sales --department-id=sales \\
    --apply --validate --db-name=federation --db-user=postgres --db-password=secret

  # Generate RLS policies only
  python generate-schema.py --department=IT --department-id=it --rls-only
        """
    )

    # Required arguments
    parser.add_argument('--department', required=True,
                       help='Human-readable department name (e.g., "Legal Department")')
    parser.add_argument('--department-id', required=True,
                       help='Department slug (lowercase, no spaces, e.g., "legal")')

    # Optional actions
    parser.add_argument('--apply', action='store_true',
                       help='Apply schema to database after generation')
    parser.add_argument('--validate', action='store_true',
                       help='Validate schema after applying')
    parser.add_argument('--rls-only', action='store_true',
                       help='Generate RLS policies only (skip schema)')

    # Database connection (required if --apply or --validate)
    parser.add_argument('--db-host', default='localhost',
                       help='Database host (default: localhost)')
    parser.add_argument('--db-port', type=int, default=5432,
                       help='Database port (default: 5432)')
    parser.add_argument('--db-name',
                       help='Database name (required for --apply or --validate)')
    parser.add_argument('--db-user',
                       help='Database user (required for --apply or --validate)')
    parser.add_argument('--db-password',
                       help='Database password (required for --apply or --validate)')

    # Output options
    parser.add_argument('--output-dir', default='generated',
                       help='Directory for generated SQL files (default: generated/)')

    args = parser.parse_args()

    # Validate department_id format
    if not args.department_id.replace('_', '').replace('-', '').isalnum():
        print("Error: --department-id must be alphanumeric (with optional _ or -)")
        sys.exit(1)

    if not args.department_id.islower():
        print("Error: --department-id must be lowercase")
        sys.exit(1)

    # Check database config if applying or validating
    if args.apply or args.validate:
        if not all([args.db_name, args.db_user, args.db_password]):
            print("Error: --db-name, --db-user, --db-password required for --apply or --validate")
            sys.exit(1)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Database config
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    } if args.db_name else None

    # GENERATE SCHEMA
    print("=" * 70)
    print("Federation Platform - Schema Generator")
    print("=" * 70)
    print(f"Department: {args.department}")
    print(f"Department ID: {args.department_id}")
    print(f"Schema: {args.department_id}_tenant")
    print("=" * 70)
    print()

    if args.rls_only:
        # Generate RLS policies only
        rls_file = generate_rls_policies(args.department_id, str(output_dir))
        print(f"\n✓ RLS policies generated: {rls_file}")
        sys.exit(0)

    # Generate main schema
    schema_file = generate_schema(args.department, args.department_id, str(output_dir))
    print(f"✓ Schema SQL generated: {schema_file}")

    # Generate RLS policies
    rls_file = generate_rls_policies(args.department_id, str(output_dir))
    print(f"✓ RLS policies generated: {rls_file}")

    # APPLY SCHEMA (optional)
    if args.apply:
        if not db_config:
            print("\nError: Database configuration missing")
            sys.exit(1)

        success = apply_schema(schema_file, db_config, args.department_id, args.department)
        if not success:
            sys.exit(1)

    # VALIDATE SCHEMA (optional)
    if args.validate:
        if not db_config:
            print("\nError: Database configuration missing")
            sys.exit(1)

        success = validate_schema(args.department_id, db_config)
        if not success:
            sys.exit(1)

    # SUMMARY
    print("\n" + "=" * 70)
    print("✓ Schema Generation Complete")
    print("=" * 70)
    print(f"\nGenerated files:")
    print(f"  - Schema SQL: {schema_file}")
    print(f"  - RLS Policies: {rls_file}")

    if args.apply:
        print(f"\n✓ Schema applied to database")
        print(f"  Schema: {args.department_id}_tenant")
        print(f"  Tables: 24")

    if args.validate:
        print(f"\n✓ Schema validation passed")

    print("\nNext steps:")
    if not args.apply:
        print("  1. Review generated SQL files")
        print("  2. Apply schema: python generate-schema.py --department-id={} --apply".format(
            args.department_id
        ))
    if not args.validate:
        print("  3. Validate schema: python generate-schema.py --department-id={} --validate".format(
            args.department_id
        ))
    print("  4. Test RLS policies: psql -d {} -f tests/test-rls.sql".format(
        args.db_name if args.db_name else '<database>'
    ))

    print("\n")


if __name__ == '__main__':
    main()
