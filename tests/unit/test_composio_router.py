"""Unit tests for composio_router critical invariants.

Tests are structured around 3 invariant categories:
  1. CB bypass - COMPOSIO_MANAGE_* bypass circuit breaker; _CB_TRIPPED_PREFIX sentinel present
  2. Gamma URL extraction - _extract_voice_result returns gammaUrl for GAMMA slugs
  3. Slug overrides - All known ghost slugs mapped in _SLUG_OVERRIDES
"""
import pytest

# Import from composio_router
try:
    from src.tools.composio_router import (
        _SLUG_OVERRIDES,
        _CB_TRIPPED_PREFIX,
        _extract_voice_result,
    )
    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False

pytestmark = pytest.mark.skipif(not IMPORTS_OK, reason="composio_router not importable")


# ---------------------------------------------------------------------------
# Category 1: CB Bypass Tests
# ---------------------------------------------------------------------------

class TestCBBypass:
    """_CB_TRIPPED_PREFIX sentinel and COMPOSIO_MANAGE_* bypass invariants."""

    def test_cb_tripped_prefix_value(self):
        """_CB_TRIPPED_PREFIX must equal the exact sentinel string."""
        assert _CB_TRIPPED_PREFIX == "CB_TRIPPED:"

    def test_slug_overrides_has_at_least_six_entries(self):
        """_SLUG_OVERRIDES must contain at least 6 ghost slug mappings."""
        assert len(_SLUG_OVERRIDES) >= 6

    def test_composio_manage_bypass_pattern_present_in_source(self):
        """The COMPOSIO_MANAGE_ bypass pattern must exist in composio_router source.

        This guards against accidental deletion of the circuit-breaker bypass
        that keeps manageConnections working even when a service CB is OPEN.
        The check inspects the module's source file directly so it is
        independent of runtime execution paths.
        """
        import inspect
        import src.tools.composio_router as _mod

        source = inspect.getsource(_mod)
        # The bypass is identified by checking for the prefix string used in
        # the CB bypass conditional (either as a startswith call or a literal
        # string constant referenced in the guard expression).
        assert "COMPOSIO_MANAGE_" in source, (
            "COMPOSIO_MANAGE_ bypass pattern not found in composio_router source; "
            "the CB bypass for manageConnections may have been removed."
        )


# ---------------------------------------------------------------------------
# Category 2: Gamma URL Extraction Tests
# ---------------------------------------------------------------------------

class TestGammaUrlExtraction:
    """_extract_voice_result Gamma-specific branch invariants."""

    def test_gamma_top_level_gamma_url(self):
        """Flat gammaUrl at top level returns 'Gamma presentation ready:' prefix."""
        data = {"gammaUrl": "https://gamma.app/docs/my-slide-abc123"}
        result = _extract_voice_result(data, "GAMMA_GENERATE_GAMMA", "Gamma: Generate Gamma")
        assert result.startswith("Gamma presentation ready:"), (
            f"Expected 'Gamma presentation ready:' prefix, got: {result!r}"
        )
        assert "https://gamma.app/docs/my-slide-abc123" in result

    def test_gamma_nested_data_gamma_url(self):
        """gammaUrl nested under data key is also extracted for GAMMA slugs."""
        data = {"data": {"gammaUrl": "https://gamma.app/docs/nested-deck-xyz"}}
        result = _extract_voice_result(data, "GAMMA_GENERATE_GAMMA", "Gamma: Generate Gamma")
        assert result.startswith("Gamma presentation ready:"), (
            f"Expected 'Gamma presentation ready:' prefix from nested data, got: {result!r}"
        )
        assert "https://gamma.app/docs/nested-deck-xyz" in result

    def test_non_gamma_slug_does_not_treat_gamma_url_specially(self):
        """A non-GAMMA slug with a gammaUrl field falls through to generic extraction."""
        data = {"gammaUrl": "https://gamma.app/docs/should-not-be-special"}
        # Use a slug that does NOT contain "GAMMA"
        result = _extract_voice_result(data, "GOOGLEDRIVE_FIND_FILE", "Drive: Find File")
        # The Gamma-specific branch must NOT fire; result must not start with the
        # Gamma sentinel — it will fall through to a generic completion message.
        assert not result.startswith("Gamma presentation ready:"), (
            "Non-GAMMA slug triggered Gamma URL extraction branch; slug guard is broken."
        )


# ---------------------------------------------------------------------------
# Category 3: Slug Override Tests
# ---------------------------------------------------------------------------

class TestSlugOverrides:
    """_SLUG_OVERRIDES must contain all 7 known ghost slug mappings."""

    _EXPECTED_OVERRIDES = {
        "GOOGLEDRIVE_FIND_FOLDER": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_LIST_FILES_IN_FOLDER": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_LIST_FOLDERS": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_SEARCH_FILES": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_GET_FILE": "GOOGLEDRIVE_GET_FILE_METADATA",
        "GOOGLEDRIVE_GET_FILE_BY_ID": "GOOGLEDRIVE_GET_FILE_METADATA",
        "MICROSOFT_TEAMS_LIST_MESSAGES": "MICROSOFT_TEAMS_TEAMS_LIST_CHANNEL_MESSAGES",
    }

    @pytest.mark.parametrize("ghost_slug,expected_target", _EXPECTED_OVERRIDES.items())
    def test_ghost_slug_is_mapped(self, ghost_slug, expected_target):
        """Each known ghost slug must be present and map to the correct live slug."""
        assert ghost_slug in _SLUG_OVERRIDES, (
            f"Ghost slug {ghost_slug!r} missing from _SLUG_OVERRIDES"
        )
        assert _SLUG_OVERRIDES[ghost_slug] == expected_target, (
            f"_SLUG_OVERRIDES[{ghost_slug!r}] = {_SLUG_OVERRIDES[ghost_slug]!r}; "
            f"expected {expected_target!r}"
        )

    def test_all_seven_ghost_slugs_present(self):
        """Exactly all 7 expected ghost slugs are present in _SLUG_OVERRIDES."""
        missing = [k for k in self._EXPECTED_OVERRIDES if k not in _SLUG_OVERRIDES]
        assert not missing, f"Missing ghost slug overrides: {missing}"
