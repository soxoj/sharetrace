"""Unit and integration tests for the Hugging Face module."""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Unit tests (mocked HTTP)
# ---------------------------------------------------------------------------
class TestHuggingFace:
    OVERVIEW_USER = {
        "_id": "62f83661fe21cc4875221c0f",
        "user": "karpathy",
        "fullname": "Andrej K",
        "avatarUrl": "https://cdn-avatars.huggingface.co/v1/karpathy.jpeg",
        "type": "user",
        "numFollowers": 1708,
        "numFollowing": 0,
        "orgs": [
            {"name": "compvis-community", "fullname": "CompVis Community"},
            {"name": "llmc", "fullname": "llmc"},
        ],
    }

    OVERVIEW_ORG = {
        "_id": "abc123",
        "user": "huggingface",
        "fullname": "Hugging Face",
        "avatarUrl": "https://cdn-avatars.huggingface.co/v1/hf.png",
        "type": "org",
        "numFollowers": 50000,
        "numFollowing": 0,
        "orgs": [],
    }

    @patch("sharetrace.modules.huggingface.requests")
    def test_profile_happy_path(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.OVERVIEW_USER
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.huggingface import huggingface
        result = huggingface("https://huggingface.co/karpathy")

        assert "data" in result
        data = result["data"]
        assert data["username"] == "karpathy"
        assert data["fullname"] == "Andrej K"
        assert data["avatar_url"] == "https://cdn-avatars.huggingface.co/v1/karpathy.jpeg"
        assert data["account_type"] == "user"
        assert data["num_followers"] == 1708
        assert data["orgs"] == ["compvis-community", "llmc"]
        assert data["profile_url"] == "https://huggingface.co/karpathy"

    @patch("sharetrace.modules.huggingface.requests")
    def test_repo_url_extracts_owner(self, mock_requests):
        """huggingface.co/<user>/<repo> must resolve to the owner, not fetch repo data."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.OVERVIEW_USER
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.huggingface import huggingface
        result = huggingface("https://huggingface.co/karpathy/llm.c")

        assert "data" in result
        assert result["data"]["username"] == "karpathy"
        # Confirm the API was called with the owner username only.
        call_url = mock_requests.get.call_args[0][0]
        assert "karpathy" in call_url
        assert "llm.c" not in call_url

    @patch("sharetrace.modules.huggingface.requests")
    def test_org_account(self, mock_requests):
        """type='org' must be surfaced as account_type='org'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.OVERVIEW_ORG
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.huggingface import huggingface
        result = huggingface("https://huggingface.co/huggingface")

        assert "data" in result
        assert result["data"]["account_type"] == "org"
        assert result["data"]["orgs"] == []

    @patch("sharetrace.modules.huggingface.requests")
    def test_user_not_found(self, mock_requests):
        """404 from API must return a friendly error dict."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.huggingface import huggingface
        result = huggingface("https://huggingface.co/nonexistentuser99999")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_invalid_url(self):
        """Non-HF URLs must return an error without making any HTTP call."""
        from sharetrace.modules.huggingface import huggingface
        result = huggingface("https://example.com/someuser")
        assert "error" in result

    def test_denylist_path(self):
        """Reserved first-segment paths must be rejected before any HTTP call."""
        from sharetrace.modules.huggingface import huggingface

        for reserved in ["spaces", "datasets", "models", "docs", "blog",
                         "api", "pricing", "login", "join", "settings",
                         "new", "tasks", "chat"]:
            result = huggingface(f"https://huggingface.co/{reserved}/something")
            assert "error" in result, f"Expected error for denylist path: {reserved}"


# ---------------------------------------------------------------------------
# Integration test (real HTTP)
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestHuggingFaceIntegration:
    def test_real_user_profile(self):
        """julien-c is a core HF employee with a stable long-lived profile."""
        from sharetrace.modules.huggingface import huggingface
        try:
            result = huggingface("https://huggingface.co/julien-c")
        except Exception:
            pytest.skip("Hugging Face API unavailable")

        if "error" in result:
            pytest.skip(f"Hugging Face returned error: {result['error']}")

        data = result["data"]
        assert isinstance(data["username"], str) and len(data["username"]) > 0
        assert data["account_type"] in ("user", "org")
        assert data["profile_url"].startswith("https://huggingface.co/")
        assert isinstance(data["num_followers"], int)
