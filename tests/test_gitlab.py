"""Tests for the GitLab identity extractor module.

Unit tests use mocked HTTP (no network required).
Integration tests are marked @pytest.mark.integration and make real HTTP calls.

Run unit tests only:  pytest tests/test_gitlab.py -v -m "not integration"
Run integration only: pytest tests/test_gitlab.py -v -m integration
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Unit tests — mocked HTTP
# ---------------------------------------------------------------------------
class TestGitLabUnit:
    COMMIT_URL = (
        "https://gitlab.com/gitlab-org/gitlab-foss/-/commit/"
        "c6da9d7f1b804966d13abd8aab4e87b0913af4b2"
    )
    NESTED_COMMIT_URL = (
        "https://gitlab.com/group/subgroup/project/-/commit/"
        "abc1234def5678901234567890abcdef12345678"
    )
    PROFILE_URL = "https://gitlab.com/gitlab-bot"

    PATCH_BODY = (
        "From c6da9d7f1b804966d13abd8aab4e87b0913af4b2 Mon Sep 17 00:00:00 2001\n"
        "From: GitLab Bot <gitlab-bot@gitlab.com>\n"
        "Date: Sat, 19 Apr 2026 10:00:00 +0000\n"
        "Subject: Add latest changes\n\n"
        "diff --git a/README.md b/README.md\n"
    )

    USERS_RESPONSE = [
        {
            "id": 1283152,
            "username": "gitlab-bot",
            "name": "GitLab Bot",
            "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/1283152/avatar.png",
            "public_email": None,
        }
    ]

    USER_DETAIL_RESPONSE = {
        "id": 1283152,
        "username": "gitlab-bot",
        "name": "GitLab Bot",
        "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/1283152/avatar.png",
        "public_email": None,
    }

    @patch("sharetrace.modules.gitlab.requests")
    def test_commit_happy_path(self, mock_requests):
        """Commit URL returns name and email parsed from .patch mbox header."""
        resp = MagicMock(status_code=200, text=self.PATCH_BODY)
        mock_requests.get.return_value = resp

        from sharetrace.modules.gitlab import gitlab
        result = gitlab(self.COMMIT_URL)

        assert "data" in result
        assert result["data"]["name"] == "GitLab Bot"
        assert result["data"]["email"] == "gitlab-bot@gitlab.com"
        assert result["data"]["commit_sha"] == "c6da9d7f1b804966d13abd8aab4e87b0913af4b2"
        assert result["data"]["project"] == "gitlab-org/gitlab-foss"
        assert "is_noreply" not in result["data"]

    @patch("sharetrace.modules.gitlab.requests")
    def test_commit_404(self, mock_requests):
        """404 from GitLab returns a descriptive error."""
        mock_requests.get.return_value = MagicMock(status_code=404, text="Not Found")

        from sharetrace.modules.gitlab import gitlab
        result = gitlab(self.COMMIT_URL)

        assert "error" in result
        assert "not found" in result["error"].lower() or "private" in result["error"].lower()

    @patch("sharetrace.modules.gitlab.requests")
    def test_commit_nested_groups(self, mock_requests):
        """Commit URL with nested group/subgroup/project is parsed correctly."""
        patch_body = (
            "From abc1234def5678901234567890abcdef12345678 Mon Sep 17 00:00:00 2001\n"
            "From: Alice Dev <alice@example.com>\n"
            "Date: Fri, 18 Apr 2026 12:00:00 +0000\n"
            "Subject: Nested group commit\n\n"
            "diff --git a/foo b/foo\n"
        )
        resp = MagicMock(status_code=200, text=patch_body)
        mock_requests.get.return_value = resp

        from sharetrace.modules.gitlab import gitlab
        result = gitlab(self.NESTED_COMMIT_URL)

        assert "data" in result
        assert result["data"]["name"] == "Alice Dev"
        assert result["data"]["email"] == "alice@example.com"
        assert result["data"]["project"] == "group/subgroup/project"

    @patch("sharetrace.modules.gitlab.requests")
    def test_profile_happy_path(self, mock_requests):
        """Profile URL returns username, display_name, user_id, avatar_url, public_email."""
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = self.USERS_RESPONSE
        detail_resp = MagicMock(status_code=200)
        detail_resp.json.return_value = self.USER_DETAIL_RESPONSE
        mock_requests.get.side_effect = [search_resp, detail_resp]

        from sharetrace.modules.gitlab import gitlab
        result = gitlab(self.PROFILE_URL)

        assert "data" in result
        assert result["data"]["username"] == "gitlab-bot"
        assert result["data"]["display_name"] == "GitLab Bot"
        assert result["data"]["user_id"] == 1283152
        assert result["data"]["avatar_url"].startswith("https://")
        assert "public_email" in result["data"]  # present even if None

    @patch("sharetrace.modules.gitlab.requests")
    def test_profile_not_found(self, mock_requests):
        """Empty array from /users?username= returns user-not-found error."""
        resp = MagicMock(status_code=200)
        resp.json.return_value = []
        mock_requests.get.return_value = resp

        from sharetrace.modules.gitlab import gitlab
        result = gitlab("https://gitlab.com/nonexistent-user-zzz99999")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_invalid_url(self):
        """Non-GitLab URLs are rejected with an error dict."""
        from sharetrace.modules.gitlab import gitlab
        result = gitlab("https://example.com/some/path")
        assert "error" in result

    def test_reserved_path_rejected(self):
        """Reserved paths like /explore, /admin must not be treated as usernames."""
        from sharetrace.modules.gitlab import gitlab
        for reserved in ["explore", "admin", "help", "api", "-", "users"]:
            result = gitlab(f"https://gitlab.com/{reserved}")
            assert "error" in result, f"Expected error for reserved path /{reserved}"

    @patch("sharetrace.modules.gitlab.requests")
    def test_commit_noreply_flagged(self, mock_requests):
        """Noreply GitLab email sets is_noreply flag."""
        body = (
            "From abc1234 Mon Sep 17 00:00:00 2001\n"
            "From: Ghost User <12345+ghost@users.noreply.gitlab.com>\n"
            "Date: Fri, 18 Apr 2026 12:00:00 +0000\n"
            "Subject: Ghost commit\n\n"
        )
        resp = MagicMock(status_code=200, text=body)
        mock_requests.get.return_value = resp

        from sharetrace.modules.gitlab import gitlab
        result = gitlab(self.COMMIT_URL)

        assert "data" in result
        assert result["data"]["is_noreply"] is True
        assert result["data"]["email"].endswith("users.noreply.gitlab.com")

    @patch("sharetrace.modules.gitlab.requests")
    def test_commit_rate_limited(self, mock_requests):
        """429 from GitLab returns a rate-limit error."""
        mock_requests.get.return_value = MagicMock(status_code=429, text="Too Many Requests")

        from sharetrace.modules.gitlab import gitlab
        result = gitlab(self.COMMIT_URL)

        assert "error" in result
        assert "rate" in result["error"].lower()

    @patch("sharetrace.modules.gitlab.requests")
    def test_commit_request_exception(self, mock_requests):
        """Network-level exception is surfaced as an error dict."""
        mock_requests.get.side_effect = Exception("Connection refused")

        from sharetrace.modules.gitlab import gitlab
        result = gitlab(self.COMMIT_URL)

        assert "error" in result
        assert "Request failed" in result["error"]


# ---------------------------------------------------------------------------
# Integration tests — real HTTP calls
# ---------------------------------------------------------------------------
class TestGitLabIntegration:
    """Real HTTP integration tests against gitlab.com public API.

    Commit: gitlab-org/gitlab-foss SHA c6da9d7f — a bot commit, always public.
    Profile: gitlab-bot — a permanent machine account on gitlab.com.
    """

    @pytest.mark.integration
    def test_commit_real_http(self):
        """Fetch a real GitLab commit patch and assert name+email are extracted."""
        from sharetrace.modules.gitlab import gitlab
        url = (
            "https://gitlab.com/gitlab-org/gitlab-foss/-/commit/"
            "c6da9d7f1b804966d13abd8aab4e87b0913af4b2"
        )
        try:
            result = gitlab(url)
        except Exception as exc:
            pytest.skip(f"GitLab unreachable: {exc}")

        if "error" in result:
            pytest.skip(f"GitLab returned error: {result['error']}")

        data = result["data"]
        assert data["name"], "name must be non-empty"
        assert data["email"], "email must be non-empty"
        assert "@" in data["email"], "email must contain @"
        assert data["commit_sha"] == "c6da9d7f1b804966d13abd8aab4e87b0913af4b2"
        assert data["project"] == "gitlab-org/gitlab-foss"

    @pytest.mark.integration
    def test_profile_real_http(self):
        """Fetch a real GitLab user profile and assert key fields are present."""
        from sharetrace.modules.gitlab import gitlab
        url = "https://gitlab.com/gitlab-bot"
        try:
            result = gitlab(url)
        except Exception as exc:
            pytest.skip(f"GitLab unreachable: {exc}")

        if "error" in result:
            pytest.skip(f"GitLab returned error: {result['error']}")

        data = result["data"]
        assert data["username"] == "gitlab-bot"
        assert data["display_name"], "display_name must be non-empty"
        assert isinstance(data["user_id"], int)
        assert data["avatar_url"].startswith("https://")
        assert "public_email" in data  # key present even when value is None
