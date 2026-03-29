"""Unit tests for individual parser modules with mocked HTTP responses."""
import json
import base64
import struct
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Microsoft (no HTTP, pure parsing)
# ---------------------------------------------------------------------------
class TestMicrosoft:
    @pytest.mark.parametrize("url,expected_email", [
        (
            "https://company-my.sharepoint.com/:f:/g/personal/john_doe_company_com/EaBcDeFgHiJ",
            "john.doe@company.com",
        ),
        (
            "https://org-my.sharepoint.com/:x:/g/personal/alice_smith_org_net/SomeHash",
            "alice.smith@org.net",
        ),
    ])
    def test_valid_sharepoint_urls(self, url, expected_email):
        from sharetrace.modules.microsoft import microsoft
        result = microsoft(url)
        assert "data" in result
        assert result["data"]["email"] == expected_email

    def test_invalid_url(self):
        from sharetrace.modules.microsoft import microsoft
        result = microsoft("https://example.com/something")
        assert "error" in result


# ---------------------------------------------------------------------------
# Telegram (no HTTP, base64 decode)
# ---------------------------------------------------------------------------
class TestTelegram:
    def test_decode_invite_link(self):
        from sharetrace.modules.telegram import telegram
        user_id = 123456789
        payload = struct.pack('<I', user_id) + b'\x00' * 12
        hash_str = base64.urlsafe_b64encode(payload).decode().rstrip('=')
        url = f"https://t.me/joinchat/{hash_str}"

        result = telegram(url)
        assert "data" in result
        assert result["data"]["user_id"] == user_id

    def test_invalid_url(self):
        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/somechannel")
        assert "error" in result


# ---------------------------------------------------------------------------
# ChatGPT
# ---------------------------------------------------------------------------
class TestChatGPT:
    @patch("sharetrace.modules.chatgpt.requests")
    def test_extract_name(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.text = '<meta property="og:description" content="Shared by John Doe via ChatGPT"'
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.chatgpt import chatgpt
        result = chatgpt("https://chatgpt.com/share/12345678-abcd-1234-abcd-123456789abc")
        assert result["data"]["name"] == "John Doe"

    @patch("sharetrace.modules.chatgpt.requests")
    def test_no_meta_tag(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.text = '<html><body>No meta here</body></html>'
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.chatgpt import chatgpt
        result = chatgpt("https://chatgpt.com/share/12345678-abcd-1234-abcd-123456789abc")
        assert "error" in result

    def test_invalid_url(self):
        from sharetrace.modules.chatgpt import chatgpt
        result = chatgpt("https://chatgpt.com/other/page")
        assert "error" in result


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------
class TestClaude:
    @patch("sharetrace.modules.claude.CloudScraper")
    def test_extract_creator(self, mock_scraper_cls):
        mock_scraper = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "creator": {
                "full_name": "Jane Smith",
                "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_scraper.get.return_value = mock_resp
        mock_scraper_cls.return_value = mock_scraper

        from sharetrace.modules.claude import claude
        result = claude("https://claude.ai/share/12345678-abcd-1234-abcd-123456789abc")
        assert result["data"]["name"] == "Jane Smith"
        assert result["data"]["user_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    @patch("sharetrace.modules.claude.CloudScraper")
    def test_no_creator(self, mock_scraper_cls):
        mock_scraper = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"some_other_key": "value"}
        mock_resp.raise_for_status = MagicMock()
        mock_scraper.get.return_value = mock_resp
        mock_scraper_cls.return_value = mock_scraper

        from sharetrace.modules.claude import claude
        result = claude("https://claude.ai/share/12345678-abcd-1234-abcd-123456789abc")
        assert "error" in result


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------
class TestDiscord:
    @patch("sharetrace.modules.discord.requests")
    def test_extract_inviter(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "inviter": {
                "id": "123456789012345678",
                "username": "testuser",
                "global_name": "Test User",
                "avatar": "abc123"
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.discord import discord
        result = discord("https://discord.gg/testCode")
        assert result["data"]["user_id"] == "123456789012345678"
        assert result["data"]["username"] == "testuser"
        assert result["data"]["name"] == "Test User"
        assert "avatar_url" in result["data"]
        assert "created_at" in result["data"]

    @patch("sharetrace.modules.discord.requests")
    def test_no_inviter(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"guild": {"name": "Test Server"}}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.discord import discord
        result = discord("https://discord.gg/testCode")
        assert "error" in result

    @patch("sharetrace.modules.discord.requests")
    def test_animated_avatar(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "inviter": {
                "id": "123456789012345678",
                "username": "testuser",
                "global_name": "Test User",
                "avatar": "a_abc123"
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.discord import discord
        result = discord("https://discord.gg/testCode")
        assert result["data"]["avatar_url"].endswith(".gif")


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------
class TestInstagram:
    @patch("sharetrace.modules.instagram.requests")
    def test_extract_user_legacy_shid(self, mock_requests):
        user_json = json.dumps({
            "username": "testuser",
            "id": "12345",
            "full_name": "Test User",
            "profile_pic_url": "https://example.com/pic.jpg"
        })
        html = f'"user_for_shid_logged_out": {user_json}'
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.instagram import instagram
        result = instagram("https://www.instagram.com/reel/ABC123/")
        assert result["data"]["username"] == "testuser"
        assert result["data"]["user_id"] == "12345"
        assert result["data"]["name"] == "Test User"

    @patch("sharetrace.modules.instagram.requests")
    def test_extract_user_sharer_key(self, mock_requests):
        user_json = json.dumps({
            "username": "shareruser",
            "id": "67890",
            "full_name": "Sharer User",
            "profile_pic_url": "https://example.com/sharer.jpg"
        })
        html = f'"sharer": {user_json}'
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.instagram import instagram
        result = instagram("https://www.instagram.com/p/ABC123/")
        assert result["data"]["username"] == "shareruser"
        assert result["data"]["user_id"] == "67890"
        assert result["data"]["name"] == "Sharer User"

    @patch("sharetrace.modules.instagram.requests")
    def test_no_user_data(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.text = "<html>nothing here</html>"
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.instagram import instagram
        result = instagram("https://www.instagram.com/p/ABC123/")
        assert "error" in result


# ---------------------------------------------------------------------------
# Perplexity
# ---------------------------------------------------------------------------
class TestPerplexity:
    @patch("sharetrace.modules.perplexity.requests")
    def test_extract_author(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "success",
            "entries": [{
                "author_username": "researcher",
                "author_image": "https://example.com/avatar.jpg",
                "author_id": "user_abc123"
            }]
        }
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.perplexity import perplexity
        result = perplexity("https://www.perplexity.ai/search/test-search-abc123")
        assert result["data"]["username"] == "researcher"
        assert result["data"]["user_id"] == "user_abc123"

    @patch("sharetrace.modules.perplexity.requests")
    def test_failed_status(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "error"}
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.perplexity import perplexity
        result = perplexity("https://www.perplexity.ai/search/test-search-abc123")
        assert "error" in result


# ---------------------------------------------------------------------------
# Pinterest
# ---------------------------------------------------------------------------
class TestPinterest:
    @patch("sharetrace.modules.pinterest.requests")
    def test_extract_sender(self, mock_requests):
        # First call: redirect with invite_code
        redirect_resp = MagicMock()
        redirect_resp.headers = {
            "Location": "https://www.pinterest.com/pin/12345/sent/?invite_code=abcdef123456"
        }

        # Second call: API response with sender data
        api_resp = MagicMock()
        api_resp.json.return_value = {
            "resource_response": {
                "data": {
                    "sender": {
                        "username": "pinuser",
                        "id": "999888777",
                        "full_name": "Pin User",
                        "image_large_url": "https://example.com/avatar.jpg"
                    }
                }
            }
        }

        mock_requests.get.side_effect = [redirect_resp, api_resp]

        from sharetrace.modules.pinterest import pinterest
        result = pinterest("https://pin.it/AbC1dEf")
        assert result["data"]["username"] == "pinuser"
        assert result["data"]["user_id"] == "999888777"

    @patch("sharetrace.modules.pinterest.requests")
    def test_no_invite_code(self, mock_requests):
        redirect_resp = MagicMock()
        redirect_resp.headers = {"Location": "https://www.pinterest.com/pin/12345/"}
        mock_requests.get.return_value = redirect_resp

        from sharetrace.modules.pinterest import pinterest
        result = pinterest("https://pin.it/AbC1dEf")
        assert "error" in result


# ---------------------------------------------------------------------------
# Substack
# ---------------------------------------------------------------------------
class TestSubstack:
    @patch("sharetrace.modules.substack.requests")
    def test_extract_referring_user(self, mock_requests):
        preload_data = json.dumps({
            "referringUser": {
                "id": 12345,
                "name": "Substacker",
                "handle": "substacker",
                "previous_name": None,
                "photo_url": "https://example.com/photo.jpg",
                "bio": "Writer",
                "profile_set_up_at": "2023-01-01T00:00:00Z",
                "reader_installed_at": None
            }
        })
        # Substack stores it as escaped JSON inside JS
        escaped = preload_data.replace('"', '\\"')
        html = f'window._preloads = JSON.parse("{escaped}")'

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.substack import substack
        result = substack("https://substack.com/@testuser/note/12345")
        assert result["data"]["name"] == "Substacker"
        assert result["data"]["handle"] == "substacker"

    @patch("sharetrace.modules.substack.requests")
    def test_no_preloads(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.text = "<html>nothing</html>"
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.substack import substack
        result = substack("https://substack.com/@testuser/note/12345")
        assert "error" in result


# ---------------------------------------------------------------------------
# Suno
# ---------------------------------------------------------------------------
class TestSuno:
    @patch("sharetrace.modules.suno.requests")
    def test_extract_sharer(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "success": True,
            "sharer_handle": "musicmaker",
            "sharer_display_name": "Music Maker",
            "sharer_avatar_url": "https://example.com/avatar.jpg"
        }
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.suno import suno
        result = suno("https://suno.com/s/abc123XYZ")
        assert result["data"]["username"] == "musicmaker"
        assert result["data"]["name"] == "Music Maker"

    @patch("sharetrace.modules.suno.requests")
    def test_failed_response(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": False}
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.suno import suno
        result = suno("https://suno.com/s/abc123XYZ")
        assert "error" in result


# ---------------------------------------------------------------------------
# TikTok
# ---------------------------------------------------------------------------
class TestTikTok:
    @patch("sharetrace.modules.tiktok.requests")
    def test_extract_share_user(self, mock_requests):
        share_user_json = json.dumps({
            "shareUser": {
                "id": "7777777",
                "uniqueId": "tiktoker",
                "nickname": "TikToker",
                "avatarLarger": "https://example.com/avatar.jpg",
                "signature": "Hello!",
                "followerCount": 1000,
                "followingCount": 50,
                "videoCount": 100,
                "heartCount": 50000,
                "privateAccount": False,
                "dmAvailable": True
            }
        })

        html = f'''
        "webapp.reflow.global.shareUser": {share_user_json}
        "share_region" : "US"
        "utm_medium" : "android"
        "utm_source" : "copy"
        "timestamp" : "1700000000"
        '''

        mock_session = MagicMock()
        first_resp = MagicMock()
        first_resp.url = "https://www.tiktok.com/@user/video/123"
        second_resp = MagicMock()
        second_resp.text = html
        mock_session.get.side_effect = [first_resp, second_resp]
        mock_requests.Session.return_value = mock_session

        from sharetrace.modules.tiktok import tiktok
        result = tiktok("https://vm.tiktok.com/ZMhABC123/")

        assert result["data"]["user_id"] == "7777777"
        assert result["data"]["username"] == "tiktoker"
        assert result["data"]["country"] == "United States"
        assert result["data"]["device"] == "android"
        assert result["data"]["share_method"] == "copy"
        assert result["data"]["shared_at"] is not None

    def test_invalid_url(self):
        from sharetrace.modules.tiktok import tiktok
        result = tiktok("https://tiktok.com/@someuser")
        assert "error" in result
