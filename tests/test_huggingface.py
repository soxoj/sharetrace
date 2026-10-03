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

    @patch("sharetrace.modules.huggingface.requests")
    def test_denylist_path(self, mock_requests):
        """Reserved first-segment paths must be rejected before any HTTP call.

        `spaces` and `datasets` are deliberately absent: they namespace someone
        else's repo rather than being service pages, and are covered by
        TestOwnerExtraction instead. The mock enforces the "before any HTTP
        call" half of this promise, which the assertion alone never did.
        """
        from sharetrace.modules.huggingface import huggingface

        for reserved in ["models", "docs", "blog",
                         "api", "pricing", "login", "join", "settings",
                         "new", "tasks", "chat"]:
            result = huggingface(f"https://huggingface.co/{reserved}/something")
            assert "error" in result, f"Expected error for denylist path: {reserved}"

        mock_requests.get.assert_not_called()


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


# ---------------------------------------------------------------------------
# Spaces, datasets, deep paths and organizations
# ---------------------------------------------------------------------------
def _resp(status, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload or {}
    return r


class TestOwnerExtraction:
    """Everything after the owner is noise; the owner may sit behind a prefix."""

    USER = {"user": "google-bert", "fullname": "BERT", "type": "user",
            "numFollowers": 12, "orgs": []}

    @pytest.mark.parametrize("url,expected_api_name", [
        ("https://huggingface.co/karpathy", "karpathy"),
        ("https://huggingface.co/google/flan-t5-base", "google"),
        # Deep paths: the repo browser, discussions and commits all name the owner.
        ("https://huggingface.co/google/flan-t5-base/tree/main", "google"),
        ("https://huggingface.co/google/flan-t5-base/discussions/3", "google"),
        # Prefixed namespaces: the owner is the segment after the prefix.
        ("https://huggingface.co/spaces/gradio/hello_world", "gradio"),
        ("https://huggingface.co/datasets/google/fleurs", "google"),
        ("https://huggingface.co/spaces/gradio/hello_world/discussions", "gradio"),
        # HF redirects /datasets/<name> to /<name>/datasets, so this names an owner too.
        ("https://huggingface.co/spaces/gradio", "gradio"),
        ("https://huggingface.co/datasets/squad", "squad"),
        ("https://huggingface.co/google/flan-t5-base?library=transformers", "google"),
    ])
    @patch("sharetrace.modules.huggingface.requests")
    def test_owner_is_the_one_looked_up(self, mock_requests, url, expected_api_name):
        mock_requests.get.return_value = _resp(200, self.USER)

        from sharetrace.modules.huggingface import huggingface
        assert "data" in huggingface(url)

        called = mock_requests.get.call_args[0][0]
        assert called == f"https://huggingface.co/api/users/{expected_api_name}/overview"

    @pytest.mark.parametrize("url,fragment", [
        ("https://huggingface.co/datasets", "listing page"),
        ("https://huggingface.co/spaces", "listing page"),
        # models/<owner>/<repo> is a 404 on HF; model URLs carry no prefix.
        ("https://huggingface.co/models/google/flan-t5-base", "reserved"),
        ("https://huggingface.co/docs/transformers/index", "reserved"),
        ("https://huggingface.co/", "no owner"),
    ])
    @patch("sharetrace.modules.huggingface.requests")
    def test_paths_without_an_owner_say_so_and_never_fetch(self, mock_requests, url, fragment):
        from sharetrace.modules.huggingface import huggingface
        result = huggingface(url)
        assert fragment in result["error"]
        mock_requests.get.assert_not_called()

    @patch("sharetrace.modules.huggingface.requests")
    def test_a_lookalike_host_is_rejected(self, mock_requests):
        from sharetrace.modules.huggingface import huggingface
        assert "error" in huggingface("https://nothuggingface.co/karpathy")
        mock_requests.get.assert_not_called()


class TestOrganizations:
    """Organizations 404 on the users endpoint — which is why `google` failed."""

    ORG = {"name": "google", "fullname": "Google", "numFollowers": 67339,
           "avatarUrl": "https://cdn-avatars.huggingface.co/v1/google.png",
           "details": "Google ❤️ Open Source AI"}

    @patch("sharetrace.modules.huggingface.requests")
    def test_an_org_is_found_on_the_second_endpoint(self, mock_requests):
        mock_requests.get.side_effect = [_resp(404), _resp(200, self.ORG)]

        from sharetrace.modules.huggingface import huggingface
        data = huggingface("https://huggingface.co/google/flan-t5-base")["data"]

        assert data["username"] == "google"
        assert data["fullname"] == "Google"
        assert data["account_type"] == "org"
        assert data["num_followers"] == 67339
        assert data["orgs"] == []
        assert data["profile_url"] == "https://huggingface.co/google"

        urls = [c[0][0] for c in mock_requests.get.call_args_list]
        assert urls == [
            "https://huggingface.co/api/users/google/overview",
            "https://huggingface.co/api/organizations/google/overview",
        ]

    @patch("sharetrace.modules.huggingface.requests")
    def test_a_user_never_costs_a_second_request(self, mock_requests):
        mock_requests.get.return_value = _resp(200, {"user": "karpathy", "type": "user"})

        from sharetrace.modules.huggingface import huggingface
        huggingface("https://huggingface.co/karpathy")
        assert mock_requests.get.call_count == 1

    @patch("sharetrace.modules.huggingface.requests")
    def test_missing_on_both_endpoints_is_not_found(self, mock_requests):
        mock_requests.get.side_effect = [_resp(404), _resp(404)]

        from sharetrace.modules.huggingface import huggingface
        assert huggingface("https://huggingface.co/nobody")["error"] == "Hugging Face user not found"
