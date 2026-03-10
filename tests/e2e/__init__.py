"""AIO Voice Agent end-to-end test suite.

Tests in this package validate live AIO features in two modes:
  - Unit mode (default): mocked components, no external calls
  - Integration mode: live Railway + DB + Composio (requires --run-integration flag)

Run unit tests:  python -m pytest tests/e2e/ -v
Run all tests:   python -m pytest tests/e2e/ --run-integration -v
"""
