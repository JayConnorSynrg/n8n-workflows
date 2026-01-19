"""
Enterprise Security Report Generator - End-to-End Tests

Tests the complete security reporting pipeline including:
- Risk score calculation
- Data normalization from multiple sources
- Report generation
- Webhook payload handling
"""

import json
import os
import pytest
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def github_security_payload() -> dict[str, Any]:
    """Sample GitHub Actions security scan payload."""
    return {
        "scan_type": "comprehensive_security_scan",
        "repository": "synrgscaling/workflows",
        "branch": "main",
        "commit": "abc123def456",
        "timestamp": "2026-01-18T22:00:00Z",
        "triggered_by": "push",
        "run_url": "https://github.com/synrgscaling/workflows/actions/runs/12345",
        "scan_results": {
            "secrets": "success",
            "dependencies": "failure",
            "sast": "success",
            "infrastructure": "success"
        },
        "overall_status": "FAILED",
        "overall_severity": "HIGH",
        "findings": [
            {
                "severity": "CRITICAL",
                "title": "Hardcoded API Key",
                "description": "API key found in source code",
                "location": "config.js:42",
                "recommendation": "Move to environment variables"
            },
            {
                "severity": "HIGH",
                "title": "Vulnerable Dependency",
                "description": "lodash@4.17.20 has known vulnerabilities",
                "location": "package.json",
                "recommendation": "Upgrade to lodash@4.17.21"
            },
            {
                "severity": "MEDIUM",
                "title": "SQL Injection Risk",
                "description": "User input not sanitized",
                "location": "api/users.js:156",
                "recommendation": "Use parameterized queries"
            }
        ]
    }


@pytest.fixture
def railway_deployment_response() -> dict[str, Any]:
    """Sample Railway GraphQL API response."""
    return {
        "data": {
            "me": {
                "projects": {
                    "edges": [
                        {
                            "node": {
                                "id": "project-123",
                                "name": "voice-agent-production",
                                "deployments": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": "deploy-abc",
                                                "status": "SUCCESS",
                                                "createdAt": "2026-01-18T21:00:00Z"
                                            }
                                        },
                                        {
                                            "node": {
                                                "id": "deploy-def",
                                                "status": "FAILED",
                                                "createdAt": "2026-01-18T20:00:00Z"
                                            }
                                        },
                                        {
                                            "node": {
                                                "id": "deploy-ghi",
                                                "status": "SUCCESS",
                                                "createdAt": "2026-01-18T19:00:00Z"
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def recall_bot_response() -> dict[str, Any]:
    """Sample Recall.ai API response."""
    return {
        "results": [
            {
                "id": "bot-001",
                "status": "done",
                "meeting_url": "https://teams.microsoft.com/meeting/123",
                "created_at": "2026-01-18T20:00:00Z",
                "duration_minutes": 45
            },
            {
                "id": "bot-002",
                "status": "failed",
                "meeting_url": "https://teams.microsoft.com/meeting/456",
                "created_at": "2026-01-18T19:00:00Z",
                "error_message": "Connection timeout"
            },
            {
                "id": "bot-003",
                "status": "done",
                "meeting_url": "https://zoom.us/j/789",
                "created_at": "2026-01-18T18:00:00Z",
                "duration_minutes": 30
            }
        ],
        "count": 3
    }


# ============================================================================
# Risk Scoring Tests
# ============================================================================

class TestRiskScoring:
    """Tests for the risk scoring algorithm."""

    def calculate_risk_score(
        self,
        critical_count: int = 0,
        high_count: int = 0,
        medium_count: int = 0,
        railway_failures: int = 0,
        recall_failures: int = 0
    ) -> int:
        """
        Risk scoring algorithm (matches n8n workflow implementation).

        Weights:
        - CRITICAL findings: 25 points each
        - HIGH findings: 10 points each
        - MEDIUM findings: 3 points each
        - Railway deployment failures: 5 points each
        - Recall.ai bot failures: 3 points each
        """
        score = (
            (critical_count * 25) +
            (high_count * 10) +
            (medium_count * 3) +
            (railway_failures * 5) +
            (recall_failures * 3)
        )
        return min(100, score)

    def determine_severity(self, risk_score: int) -> str:
        """Determine severity level from risk score."""
        if risk_score >= 50:
            return "CRITICAL"
        elif risk_score >= 25:
            return "HIGH"
        elif risk_score >= 10:
            return "MEDIUM"
        else:
            return "LOW"

    def test_risk_score_no_findings(self):
        """Risk score should be 0 with no findings."""
        score = self.calculate_risk_score()
        assert score == 0
        assert self.determine_severity(score) == "LOW"

    def test_risk_score_critical_finding(self):
        """Single critical finding should result in HIGH risk."""
        score = self.calculate_risk_score(critical_count=1)
        assert score == 25
        assert self.determine_severity(score) == "HIGH"

    def test_risk_score_multiple_criticals(self):
        """Two critical findings should result in CRITICAL risk."""
        score = self.calculate_risk_score(critical_count=2)
        assert score == 50
        assert self.determine_severity(score) == "CRITICAL"

    def test_risk_score_mixed_findings(self):
        """Mixed findings should be calculated correctly."""
        # 1 critical (25) + 2 high (20) + 3 medium (9) = 54
        score = self.calculate_risk_score(
            critical_count=1,
            high_count=2,
            medium_count=3
        )
        assert score == 54
        assert self.determine_severity(score) == "CRITICAL"

    def test_risk_score_max_cap(self):
        """Risk score should be capped at 100."""
        score = self.calculate_risk_score(critical_count=10)
        assert score == 100

    def test_risk_score_with_railway_failures(self):
        """Railway failures should contribute to risk score."""
        score = self.calculate_risk_score(railway_failures=2)
        assert score == 10
        assert self.determine_severity(score) == "MEDIUM"

    def test_risk_score_with_recall_failures(self):
        """Recall.ai failures should contribute to risk score."""
        score = self.calculate_risk_score(recall_failures=3)
        assert score == 9
        assert self.determine_severity(score) == "LOW"

    def test_risk_score_all_sources(self):
        """Combined sources should calculate correctly."""
        # 1 critical (25) + 1 railway failure (5) + 2 recall failures (6) = 36
        score = self.calculate_risk_score(
            critical_count=1,
            railway_failures=1,
            recall_failures=2
        )
        assert score == 36
        assert self.determine_severity(score) == "HIGH"


# ============================================================================
# Data Normalization Tests
# ============================================================================

class TestDataNormalization:
    """Tests for data normalization from multiple sources."""

    def normalize_github_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitHub Actions security scan data."""
        findings = payload.get("findings", [])

        return {
            "source": "github",
            "repository": payload.get("repository", ""),
            "branch": payload.get("branch", ""),
            "commit": payload.get("commit", ""),
            "timestamp": payload.get("timestamp", ""),
            "critical_count": len([f for f in findings if f.get("severity") == "CRITICAL"]),
            "high_count": len([f for f in findings if f.get("severity") == "HIGH"]),
            "medium_count": len([f for f in findings if f.get("severity") == "MEDIUM"]),
            "low_count": len([f for f in findings if f.get("severity") == "LOW"]),
            "total_findings": len(findings),
            "scan_results": payload.get("scan_results", {}),
            "run_url": payload.get("run_url", "")
        }

    def normalize_railway_data(self, response: dict[str, Any]) -> dict[str, Any]:
        """Normalize Railway deployment data."""
        projects = response.get("data", {}).get("me", {}).get("projects", {}).get("edges", [])

        total_deployments = 0
        failed_deployments = 0
        last_deploy = None

        for project in projects:
            deployments = project.get("node", {}).get("deployments", {}).get("edges", [])
            for deploy in deployments:
                node = deploy.get("node", {})
                total_deployments += 1
                if node.get("status") == "FAILED":
                    failed_deployments += 1
                if last_deploy is None:
                    last_deploy = node.get("createdAt")

        return {
            "source": "railway",
            "total_deployments": total_deployments,
            "failed_deployments": failed_deployments,
            "success_rate": round((total_deployments - failed_deployments) / total_deployments * 100, 1) if total_deployments > 0 else 100,
            "last_deploy": last_deploy
        }

    def normalize_recall_data(self, response: dict[str, Any]) -> dict[str, Any]:
        """Normalize Recall.ai bot data."""
        bots = response.get("results", [])

        total_sessions = len(bots)
        failed_sessions = len([b for b in bots if b.get("status") == "failed"])
        total_duration = sum(b.get("duration_minutes", 0) for b in bots)

        return {
            "source": "recall",
            "total_sessions": total_sessions,
            "failed_sessions": failed_sessions,
            "success_rate": round((total_sessions - failed_sessions) / total_sessions * 100, 1) if total_sessions > 0 else 100,
            "total_duration_minutes": total_duration
        }

    def test_normalize_github_data(self, github_security_payload):
        """GitHub data should be normalized correctly."""
        result = self.normalize_github_data(github_security_payload)

        assert result["source"] == "github"
        assert result["repository"] == "synrgscaling/workflows"
        assert result["critical_count"] == 1
        assert result["high_count"] == 1
        assert result["medium_count"] == 1
        assert result["total_findings"] == 3

    def test_normalize_railway_data(self, railway_deployment_response):
        """Railway data should be normalized correctly."""
        result = self.normalize_railway_data(railway_deployment_response)

        assert result["source"] == "railway"
        assert result["total_deployments"] == 3
        assert result["failed_deployments"] == 1
        assert result["success_rate"] == 66.7

    def test_normalize_recall_data(self, recall_bot_response):
        """Recall.ai data should be normalized correctly."""
        result = self.normalize_recall_data(recall_bot_response)

        assert result["source"] == "recall"
        assert result["total_sessions"] == 3
        assert result["failed_sessions"] == 1
        assert result["success_rate"] == 66.7
        assert result["total_duration_minutes"] == 75


# ============================================================================
# Report Generation Tests
# ============================================================================

class TestReportGeneration:
    """Tests for security report generation."""

    def generate_recommendations(
        self,
        critical_count: int,
        high_count: int,
        railway_failures: int,
        recall_failures: int
    ) -> list[dict[str, str]]:
        """Generate recommendations based on findings."""
        recommendations = []

        if critical_count > 0:
            recommendations.append({
                "priority": "P0",
                "description": "IMMEDIATE: Rotate all exposed secrets and credentials"
            })

        if high_count > 0:
            recommendations.append({
                "priority": "P1",
                "description": "URGENT: Update vulnerable dependencies within 24 hours"
            })

        if railway_failures > 0:
            recommendations.append({
                "priority": "P2",
                "description": "Review Railway deployment failures and fix configuration"
            })

        if recall_failures > 0:
            recommendations.append({
                "priority": "P2",
                "description": "Investigate Recall.ai bot failures and connection issues"
            })

        if not recommendations:
            recommendations.append({
                "priority": "INFO",
                "description": "No critical issues found. Continue regular monitoring."
            })

        return recommendations

    def test_recommendations_critical_finding(self):
        """Critical findings should generate P0 recommendation."""
        recs = self.generate_recommendations(
            critical_count=1,
            high_count=0,
            railway_failures=0,
            recall_failures=0
        )
        assert len(recs) == 1
        assert recs[0]["priority"] == "P0"
        assert "secrets" in recs[0]["description"].lower()

    def test_recommendations_multiple_issues(self):
        """Multiple issues should generate multiple recommendations."""
        recs = self.generate_recommendations(
            critical_count=1,
            high_count=2,
            railway_failures=1,
            recall_failures=1
        )
        assert len(recs) == 4
        priorities = [r["priority"] for r in recs]
        assert "P0" in priorities
        assert "P1" in priorities
        assert priorities.count("P2") == 2

    def test_recommendations_no_issues(self):
        """No issues should generate info recommendation."""
        recs = self.generate_recommendations(
            critical_count=0,
            high_count=0,
            railway_failures=0,
            recall_failures=0
        )
        assert len(recs) == 1
        assert recs[0]["priority"] == "INFO"


# ============================================================================
# Webhook Payload Tests
# ============================================================================

class TestWebhookPayload:
    """Tests for webhook payload structure validation."""

    def validate_github_payload(self, payload: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate GitHub Actions payload structure."""
        errors = []
        required_fields = ["scan_type", "repository", "timestamp"]

        for field in required_fields:
            if field not in payload:
                errors.append(f"Missing required field: {field}")

        if "scan_type" in payload:
            valid_types = ["secrets", "dependencies", "sast", "infrastructure", "comprehensive_security_scan"]
            if payload["scan_type"] not in valid_types:
                errors.append(f"Invalid scan_type: {payload['scan_type']}")

        return len(errors) == 0, errors

    def test_valid_github_payload(self, github_security_payload):
        """Valid payload should pass validation."""
        is_valid, errors = self.validate_github_payload(github_security_payload)
        assert is_valid
        assert len(errors) == 0

    def test_missing_required_field(self):
        """Missing required field should fail validation."""
        payload = {"scan_type": "secrets"}
        is_valid, errors = self.validate_github_payload(payload)
        assert not is_valid
        assert len(errors) == 2  # Missing repository and timestamp

    def test_invalid_scan_type(self):
        """Invalid scan type should fail validation."""
        payload = {
            "scan_type": "invalid_type",
            "repository": "test/repo",
            "timestamp": "2026-01-18T00:00:00Z"
        }
        is_valid, errors = self.validate_github_payload(payload)
        assert not is_valid
        assert any("Invalid scan_type" in e for e in errors)


# ============================================================================
# Integration Tests
# ============================================================================

class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def process_security_report(
        self,
        github_data: dict[str, Any],
        railway_data: dict[str, Any],
        recall_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process complete security report from all sources.
        This mirrors the n8n workflow data normalization node.
        """
        # Normalize data
        normalizer = TestDataNormalization()
        github_normalized = normalizer.normalize_github_data(github_data)
        railway_normalized = normalizer.normalize_railway_data(railway_data)
        recall_normalized = normalizer.normalize_recall_data(recall_data)

        # Calculate risk score
        scorer = TestRiskScoring()
        risk_score = scorer.calculate_risk_score(
            critical_count=github_normalized["critical_count"],
            high_count=github_normalized["high_count"],
            medium_count=github_normalized["medium_count"],
            railway_failures=railway_normalized["failed_deployments"],
            recall_failures=recall_normalized["failed_sessions"]
        )
        severity = scorer.determine_severity(risk_score)

        # Generate recommendations
        generator = TestReportGeneration()
        recommendations = generator.generate_recommendations(
            critical_count=github_normalized["critical_count"],
            high_count=github_normalized["high_count"],
            railway_failures=railway_normalized["failed_deployments"],
            recall_failures=recall_normalized["failed_sessions"]
        )

        return {
            "company_name": "SYNRG Enterprise",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "risk_score": 100 - risk_score,  # Invert for "health score"
            "severity": severity,
            "compliance_status": "COMPLIANT" if risk_score < 20 else "NON-COMPLIANT",
            "github": github_normalized,
            "railway": railway_normalized,
            "recall": recall_normalized,
            "recommendations": recommendations
        }

    def test_full_integration(
        self,
        github_security_payload,
        railway_deployment_response,
        recall_bot_response
    ):
        """Test complete report processing pipeline."""
        report = self.process_security_report(
            github_data=github_security_payload,
            railway_data=railway_deployment_response,
            recall_data=recall_bot_response
        )

        # Verify report structure
        assert report["company_name"] == "SYNRG Enterprise"
        assert "timestamp" in report
        assert 0 <= report["risk_score"] <= 100

        # Verify severity
        assert report["severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        # Verify data sources
        assert report["github"]["source"] == "github"
        assert report["railway"]["source"] == "railway"
        assert report["recall"]["source"] == "recall"

        # Verify recommendations exist
        assert len(report["recommendations"]) > 0

    def test_integration_with_no_issues(self):
        """Test report with no security issues."""
        github_clean = {
            "scan_type": "comprehensive_security_scan",
            "repository": "test/repo",
            "timestamp": "2026-01-18T00:00:00Z",
            "findings": []
        }

        railway_healthy = {
            "data": {
                "me": {
                    "projects": {
                        "edges": [
                            {
                                "node": {
                                    "deployments": {
                                        "edges": [
                                            {"node": {"status": "SUCCESS", "createdAt": "2026-01-18T00:00:00Z"}}
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

        recall_healthy = {
            "results": [
                {"id": "bot-1", "status": "done", "duration_minutes": 30}
            ],
            "count": 1
        }

        report = self.process_security_report(
            github_data=github_clean,
            railway_data=railway_healthy,
            recall_data=recall_healthy
        )

        assert report["risk_score"] == 100  # Full health
        assert report["severity"] == "LOW"
        assert report["compliance_status"] == "COMPLIANT"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
