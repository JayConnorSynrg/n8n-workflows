#!/usr/bin/env python3
"""
RLS Policy Generator for Federation Platform
Generates PostgreSQL Row-Level Security policies for multi-tenant isolation
"""

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class RLSPolicy:
    """RLS policy definition"""
    table_name: str
    policy_name: str
    policy_type: str  # 'isolation', 'admin_bypass', 'cross_dept_read'
    sql: str


class RLSPolicyGenerator:
    """Generate Row-Level Security policies for department schemas"""

    def __init__(self, department_id: str, department_schema: str):
        self.department_id = department_id
        self.department_schema = department_schema
        self.department_role = f"{department_id}_role"

    def generate_isolation_policy(self, table_name: str) -> RLSPolicy:
        """
        Generate department isolation policy - prevents cross-department data access

        Args:
            table_name: Name of the table to protect

        Returns:
            RLSPolicy with SQL to create the policy
        """
        policy_name = f"{self.department_id}_{table_name}_isolation"
        sql = f"""
-- Isolation policy: {table_name}
ALTER TABLE {self.department_schema}.{table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY {policy_name} ON {self.department_schema}.{table_name}
    FOR ALL
    TO {self.department_role}
    USING (department = '{self.department_id}');
"""
        return RLSPolicy(
            table_name=table_name,
            policy_name=policy_name,
            policy_type='isolation',
            sql=sql
        )

    def generate_admin_policy(self, table_name: str) -> RLSPolicy:
        """
        Generate admin bypass policy - allows platform admins to see all departments

        Args:
            table_name: Name of the table

        Returns:
            RLSPolicy with SQL to create admin bypass policy
        """
        policy_name = f"admin_bypass_{table_name}"
        sql = f"""
-- Admin bypass policy: {table_name}
CREATE POLICY {policy_name} ON {self.department_schema}.{table_name}
    FOR ALL
    TO federation_admin_role
    USING (true);
"""
        return RLSPolicy(
            table_name=table_name,
            policy_name=policy_name,
            policy_type='admin_bypass',
            sql=sql
        )

    def generate_cross_dept_read_policy(self, table_name: str) -> RLSPolicy:
        """
        Generate cross-department read policy - allows read-only queries via API gateway
        Uses federation.cross_dept_permissions table to validate access

        Args:
            table_name: Name of the table

        Returns:
            RLSPolicy with SQL to create cross-department read policy
        """
        policy_name = f"{self.department_id}_{table_name}_cross_dept_read"
        sql = f"""
-- Cross-department read policy: {table_name}
CREATE POLICY {policy_name} ON {self.department_schema}.{table_name}
    FOR SELECT
    TO cross_dept_query_role
    USING (
        department = '{self.department_id}' AND
        EXISTS (
            SELECT 1 FROM federation.cross_dept_permissions
            WHERE target_department_id = '{self.department_id}'
            AND source_department_id = current_setting('app.source_department', true)
            AND permission_type = 'read'
            AND enabled = true
            AND (expires_at IS NULL OR expires_at > NOW())
        )
    );
"""
        return RLSPolicy(
            table_name=table_name,
            policy_name=policy_name,
            policy_type='cross_dept_read',
            sql=sql
        )

    def generate_no_cross_dept_write_policy(self, table_name: str) -> RLSPolicy:
        """
        Generate policy that blocks cross-department writes

        Args:
            table_name: Name of the table

        Returns:
            RLSPolicy with SQL to block cross-dept writes
        """
        policy_name = f"{self.department_id}_{table_name}_no_cross_write"
        sql = f"""
-- Block cross-department writes: {table_name}
CREATE POLICY {policy_name} ON {self.department_schema}.{table_name}
    FOR INSERT
    TO cross_dept_query_role
    USING (false);

CREATE POLICY {policy_name}_update ON {self.department_schema}.{table_name}
    FOR UPDATE
    TO cross_dept_query_role
    USING (false);

CREATE POLICY {policy_name}_delete ON {self.department_schema}.{table_name}
    FOR DELETE
    TO cross_dept_query_role
    USING (false);
"""
        return RLSPolicy(
            table_name=table_name,
            policy_name=policy_name,
            policy_type='no_cross_write',
            sql=sql
        )

    def generate_all_policies_for_table(self, table_name: str) -> List[RLSPolicy]:
        """
        Generate all RLS policies for a single table

        Args:
            table_name: Name of the table

        Returns:
            List of RLSPolicy objects
        """
        return [
            self.generate_isolation_policy(table_name),
            self.generate_admin_policy(table_name),
            self.generate_cross_dept_read_policy(table_name),
            self.generate_no_cross_dept_write_policy(table_name)
        ]

    def generate_all_policies(self) -> Dict[str, List[RLSPolicy]]:
        """
        Generate RLS policies for all 24 tables

        Returns:
            Dictionary mapping table names to list of policies
        """
        tables = [
            'tool_calls', 'session_context', 'drive_document_repository', 'drive_access_log',
            'email_logs', 'vector_store_embeddings', 'agent_context', 'conversation_history',
            'calendar_events', 'contacts', 'audit_trail', 'training_metrics',
            'user_session_analytics', 'file_attachments', 'llm_usage_logs', 'stt_usage_logs',
            'tts_usage_logs', 'workflow_executions', 'error_logs', 'notifications',
            'scheduled_tasks', 'user_preferences', 'api_keys', 'feature_flags'
        ]

        policies = {}
        for table in tables:
            policies[table] = self.generate_all_policies_for_table(table)

        return policies

    def export_policies_to_sql(self, output_file: str) -> None:
        """
        Export all policies to a SQL file

        Args:
            output_file: Path to output SQL file
        """
        all_policies = self.generate_all_policies()

        with open(output_file, 'w') as f:
            f.write(f"""-- Row-Level Security Policies
-- Department: {self.department_id}
-- Schema: {self.department_schema}
-- Generated by: rls-policies.py
-- Total tables: {len(all_policies)}

SET search_path TO {self.department_schema}, federation, public;

-- =============================================================================
-- RLS POLICY DEFINITIONS
-- =============================================================================

""")
            for table_name, policies in all_policies.items():
                f.write(f"\n-- Policies for table: {table_name}\n")
                f.write("-" * 80 + "\n\n")
                for policy in policies:
                    f.write(policy.sql)
                    f.write("\n")

            f.write(f"""
-- =============================================================================
-- POLICY VALIDATION
-- =============================================================================

-- Verify RLS enabled on all tables
DO $$
DECLARE
    table_name TEXT;
    rls_enabled BOOLEAN;
    missing_rls TEXT[] := ARRAY[]::TEXT[];
BEGIN
    FOR table_name IN
        SELECT t.table_name
        FROM information_schema.tables t
        WHERE t.table_schema = '{self.department_schema}'
        AND t.table_type = 'BASE TABLE'
    LOOP
        SELECT relrowsecurity INTO rls_enabled
        FROM pg_class
        WHERE relname = table_name
        AND relnamespace = '{self.department_schema}'::regnamespace;

        IF NOT rls_enabled THEN
            missing_rls := array_append(missing_rls, table_name);
        END IF;
    END LOOP;

    IF array_length(missing_rls, 1) > 0 THEN
        RAISE WARNING 'RLS not enabled on tables: %', array_to_string(missing_rls, ', ');
    ELSE
        RAISE NOTICE 'RLS validation passed. All tables have RLS enabled.';
    END IF;
END $$;

-- =============================================================================
-- COMPLETION
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE 'RLS policies created for schema: {self.department_schema}';
    RAISE NOTICE 'Department ID: {self.department_id}';
    RAISE NOTICE 'Total tables: {len(all_policies)}';
END $$;
""")


def main():
    """CLI interface for RLS policy generation"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate RLS policies for department schema')
    parser.add_argument('--department-id', required=True, help='Department ID (e.g., hr, accounting)')
    parser.add_argument('--schema', required=True, help='Schema name (e.g., hr_tenant)')
    parser.add_argument('--output', required=True, help='Output SQL file path')
    parser.add_argument('--policy-type', choices=['all', 'isolation', 'admin', 'cross_dept'],
                        default='all', help='Type of policies to generate')

    args = parser.parse_args()

    generator = RLSPolicyGenerator(args.department_id, args.schema)

    if args.policy_type == 'all':
        generator.export_policies_to_sql(args.output)
        print(f"Generated all RLS policies for {args.schema} -> {args.output}")
    else:
        # Generate specific policy type
        all_policies = generator.generate_all_policies()
        with open(args.output, 'w') as f:
            f.write(f"-- RLS Policies ({args.policy_type}) for {args.schema}\n\n")
            for table_name, policies in all_policies.items():
                for policy in policies:
                    if policy.policy_type == args.policy_type:
                        f.write(policy.sql)
                        f.write("\n")
        print(f"Generated {args.policy_type} policies for {args.schema} -> {args.output}")


if __name__ == '__main__':
    main()
