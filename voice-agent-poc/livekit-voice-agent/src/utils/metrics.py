"""Latency tracking and metrics collection."""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LatencyTracker:
    """Track latency across pipeline stages."""

    _stages: Dict[str, float] = field(default_factory=dict)
    _completed: Dict[str, float] = field(default_factory=dict)

    def start(self, stage: str) -> None:
        """Start timing a stage."""
        self._stages[stage] = time.perf_counter()

    def end(self, stage: str) -> float:
        """End timing a stage and return elapsed milliseconds."""
        if stage not in self._stages:
            logger.warning(f"Stage '{stage}' was not started")
            return 0.0

        elapsed_ms = (time.perf_counter() - self._stages[stage]) * 1000
        self._completed[stage] = elapsed_ms
        del self._stages[stage]

        logger.debug(f"Stage '{stage}' completed", latency_ms=round(elapsed_ms, 1))
        return elapsed_ms

    def get_summary(self) -> Dict[str, float]:
        """Get summary of all completed stages."""
        return self._completed.copy()

    def reset(self) -> None:
        """Reset all tracking."""
        self._stages.clear()
        self._completed.clear()


@dataclass
class MetricsCollector:
    """Collect and report metrics."""

    latencies: Dict[str, list] = field(default_factory=dict)

    def record_latency(self, stage: str, value_ms: float) -> None:
        """Record a latency measurement."""
        if stage not in self.latencies:
            self.latencies[stage] = []
        self.latencies[stage].append(value_ms)

    def get_percentiles(self, stage: str) -> Dict[str, float]:
        """Get P50, P90, P99 for a stage."""
        if stage not in self.latencies or not self.latencies[stage]:
            return {}

        values = sorted(self.latencies[stage])
        n = len(values)

        return {
            "p50": values[int(n * 0.5)],
            "p90": values[int(n * 0.9)],
            "p99": values[int(n * 0.99)] if n >= 100 else values[-1],
            "count": n,
        }
