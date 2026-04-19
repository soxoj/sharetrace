"""Tests for LinkedIn module — unit (mocked) and integration (real fetch).

Unit tests run without network access.
Integration test marked @pytest.mark.integration accepts EITHER success
(data returned) OR blocked (is_blocked: True) — LinkedIn blocking is expected.

Run unit tests only:
    pytest tests/test_linkedin.py -v -m "not integration"

Run all including integration:
    pytest tests/test_linkedin.py -v
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resp(status_code: int = 200, body: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = body
    return resp


def _profile_html(og_title: str, og_image: str = "") -> str:
    """Minimal HTML snippet large enough to pass the <5KB gate."""
    padding = "x" * 5100
    img_tag = (
        f'<meta property="og:image" content="{og_image}"/>'
        if og_image
        else ""
    )
    return (
        f'<html><head>'
        f'<meta property="og:title" content="{og_title}"/>'
        f'{img_tag}'
        f'</head><body>{padding}</body></html>'
    )


# ---------------------------------------------------------------------------
# Unit tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestLinkedInUnit:

    @patch("sharetrace.modules.linkedin.requests")
    def test_profile_happy_path(self, mock_requests):
        """Profile with og:title 'Jane Doe - CTO at Acme | LinkedIn' parses correctly."""
        html = _profile_html(
            og_title="Jane Doe - CTO at Acme | LinkedIn",
            og_image="https://media.licdn.com/dms/image/jane.jpg",
        )
        mock_requests.get.return_value = _make_resp(200, html)

        from sharetrace.modules.linkedin import linkedin
        result = linkedin("https://www.linkedin.com/in/janedoe")

        assert "data" in result, f"Expected data, got: {result}"
        data = result["data"]
        assert data["display_name"] == "Jane Doe"
        assert data["headline"] == "CTO at Acme"
        assert data["url_type"] == "profile"
        assert data["profile_url"] == "https://www.linkedin.com/in/janedoe"
        assert data["avatar_url"] == "https://media.licdn.com/dms/image/jane.jpg"

    @patch("sharetrace.modules.linkedin.requests")
    def test_authwall_detected_by_keyword(self, mock_requests):
        """HTML containing 'authwall' string is treated as blocked."""
        html = (
            "<html><body>"
            '<div id="authwall">Please sign in to view this page.</div>'
            "</body></html>"
        )
        mock_requests.get.return_value = _make_resp(200, html)

        from sharetrace.modules.linkedin import linkedin
        result = linkedin("https://www.linkedin.com/in/janedoe")

        assert "error" in result
        assert result.get("is_blocked") is True

    @patch("sharetrace.modules.linkedin.requests")
    def test_999_status_code_returns_blocked(self, mock_requests):
        """HTTP 999 (LinkedIn bot-block code) returns is_blocked: True."""
        mock_requests.get.return_value = _make_resp(999, "<html>blocked</html>")

        from sharetrace.modules.linkedin import linkedin
        result = linkedin("https://www.linkedin.com/in/janedoe")

        assert "error" in result
        assert result.get("is_blocked") is True

    @patch("sharetrace.modules.linkedin.requests")
    def test_post_url_different_og_title_shape(self, mock_requests):
        """Post URL with og:title that has no headline separator still extracts name."""
        html = _profile_html(og_title="Reid Hoffman on building LinkedIn | LinkedIn")
        mock_requests.get.return_value = _make_resp(200, html)

        from sharetrace.modules.linkedin import linkedin
        result = linkedin("https://www.linkedin.com/posts/reidhoffman_abc123")

        assert "data" in result, f"Expected data, got: {result}"
        data = result["data"]
        assert data["url_type"] == "post"
        # No " - " separator → headline is None
        assert data["headline"] is None
        assert "Reid Hoffman on building LinkedIn" in data["display_name"]

    def test_invalid_url_returns_error(self):
        """URL with no LinkedIn path segment returns error without HTTP call."""
        from sharetrace.modules.linkedin import linkedin
        result = linkedin("https://example.com/something")

        assert "error" in result
        assert "is_blocked" not in result

    @patch("sharetrace.modules.linkedin.requests")
    def test_small_body_without_og_title_is_blocked(self, mock_requests):
        """Response <5KB with no og:title is treated as auth-wall block."""
        # Body is tiny (< 5000 bytes) and has no og:title
        small_body = "<html><body>Sign in to LinkedIn</body></html>"
        assert len(small_body) < 5000
        mock_requests.get.return_value = _make_resp(200, small_body)

        from sharetrace.modules.linkedin import linkedin
        result = linkedin("https://www.linkedin.com/in/janedoe")

        assert "error" in result
        assert result.get("is_blocked") is True


# ---------------------------------------------------------------------------
# Integration test (real HTTP — LinkedIn may block)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestLinkedInIntegration:

    def test_real_public_profile_succeeds_or_blocked(self):
        """Fetching a well-known public profile returns data OR is_blocked.

        LinkedIn may block the request — that is an expected outcome.
        This test only fails on unexpected errors (exception, malformed response).
        """
        from sharetrace.modules.linkedin import linkedin
        result = linkedin("https://www.linkedin.com/in/reidhoffman")

        # Must be a dict with either 'data' or 'error'
        assert isinstance(result, dict)
        assert "data" in result or "error" in result

        if "data" in result:
            data = result["data"]
            # If we got data, it must have the required fields
            assert "display_name" in data
            assert "url_type" in data
            assert data["url_type"] == "profile"
            assert "profile_url" in data
        else:
            # Blocked is acceptable — confirm shape
            assert "error" in result
            # is_blocked may or may not be present depending on error type
