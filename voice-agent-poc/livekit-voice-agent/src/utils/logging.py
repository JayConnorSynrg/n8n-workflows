"""Structured logging configuration with OpenTelemetry tracing support."""
import logging
import os
import sys
from typing import Optional

import structlog

# OpenTelemetry imports (optional - gracefully degrade if not installed)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None


def setup_otel_tracing(service_name: str = "synrg-voice-agent") -> Optional[object]:
    """Initialize OpenTelemetry tracing for security monitoring.

    Args:
        service_name: Name of the service for trace identification

    Returns:
        Tracer instance or None if OTEL not available
    """
    if not OTEL_AVAILABLE:
        return None

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return None

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: os.getenv("SERVICE_VERSION", "1.0.0"),
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv("ENVIRONMENT", "development"),
        })

        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        return trace.get_tracer(service_name)
    except Exception:
        return None


class SecurityEventLogger:
    """Log security-relevant events for compliance reporting.

    This logger adds structured security audit events that can be
    collected and analyzed for compliance reporting.
    """

    def __init__(self, logger: structlog.BoundLogger):
        """Initialize with a structlog logger.

        Args:
            logger: Configured structlog logger instance
        """
        self.logger = logger

    def log_session_start(self, session_id: str, participant_count: int, room_name: str = "") -> None:
        """Log voice session initiation.

        Args:
            session_id: Unique session identifier
            participant_count: Number of participants in session
            room_name: LiveKit room name
        """
        self.logger.info(
            "session_started",
            session_id=session_id,
            participant_count=participant_count,
            room_name=room_name,
            event_type="security_audit",
            audit_category="session_lifecycle"
        )

    def log_session_end(self, session_id: str, duration_seconds: float, error: Optional[str] = None) -> None:
        """Log voice session termination.

        Args:
            session_id: Unique session identifier
            duration_seconds: Session duration
            error: Error message if session ended abnormally
        """
        self.logger.info(
            "session_ended",
            session_id=session_id,
            duration_seconds=duration_seconds,
            error=error,
            event_type="security_audit",
            audit_category="session_lifecycle"
        )

    def log_data_access(self, session_id: str, data_type: str, operation: str = "read") -> None:
        """Log data access for audit trail.

        Args:
            session_id: Unique session identifier
            data_type: Type of data accessed (e.g., "transcript", "audio", "user_info")
            operation: Type of operation (read, write, delete)
        """
        self.logger.info(
            "data_accessed",
            session_id=session_id,
            data_type=data_type,
            operation=operation,
            event_type="security_audit",
            audit_category="data_access"
        )

    def log_external_api_call(self, session_id: str, api_name: str, endpoint: str, success: bool) -> None:
        """Log external API interactions.

        Args:
            session_id: Unique session identifier
            api_name: Name of the external API (e.g., "n8n", "openai", "recall")
            endpoint: API endpoint called
            success: Whether the call succeeded
        """
        self.logger.info(
            "external_api_call",
            session_id=session_id,
            api_name=api_name,
            endpoint=endpoint,
            success=success,
            event_type="security_audit",
            audit_category="api_integration"
        )

    def log_error(self, session_id: str, error_type: str, details: str, severity: str = "error") -> None:
        """Log error events for security monitoring.

        Args:
            session_id: Unique session identifier
            error_type: Classification of error (e.g., "auth_failure", "rate_limit", "connection")
            details: Error details/message
            severity: Error severity (warning, error, critical)
        """
        log_method = getattr(self.logger, severity, self.logger.error)
        log_method(
            "error_occurred",
            session_id=session_id,
            error_type=error_type,
            details=details,
            event_type="security_audit",
            audit_category="error_monitoring"
        )

    def log_auth_event(self, session_id: str, auth_type: str, success: bool, user_identity: str = "") -> None:
        """Log authentication/authorization events.

        Args:
            session_id: Unique session identifier
            auth_type: Type of auth (e.g., "token_validation", "room_join", "api_key")
            success: Whether auth succeeded
            user_identity: Masked or anonymized user identifier
        """
        self.logger.info(
            "auth_event",
            session_id=session_id,
            auth_type=auth_type,
            success=success,
            user_identity=user_identity,
            event_type="security_audit",
            audit_category="authentication"
        )


def setup_logging(name: Optional[str] = None, level: str = "INFO") -> structlog.BoundLogger:
    """Configure structured logging.

    Args:
        name: Logger name (usually __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured structlog logger
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    return structlog.get_logger(name)


def get_security_logger(name: Optional[str] = None, level: str = "INFO") -> SecurityEventLogger:
    """Get a security event logger for compliance auditing.

    Args:
        name: Logger name
        level: Log level

    Returns:
        SecurityEventLogger instance
    """
    base_logger = setup_logging(name, level)
    return SecurityEventLogger(base_logger)
