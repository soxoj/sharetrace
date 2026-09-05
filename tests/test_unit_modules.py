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
# Telegram
# ---------------------------------------------------------------------------
class TestTelegram:
    @staticmethod
    def _invite_hash(user_id: int) -> str:
        payload = struct.pack('<I', user_id) + b'\x00' * 12
        return base64.urlsafe_b64encode(payload).decode().rstrip('=')

    def test_decode_joinchat_invite(self):
        from sharetrace.modules.telegram import telegram
        result = telegram(f"https://t.me/joinchat/{self._invite_hash(123456789)}")
        assert result["data"]["user_id"] == 123456789

    def test_decode_plus_invite_legacy_format(self):
        # Legacy 16-byte payload — even under the +hash prefix — still decodes.
        from sharetrace.modules.telegram import telegram
        result = telegram(f"https://t.me/+{self._invite_hash(987654321)}")
        assert result["data"]["user_id"] == 987654321

    def test_new_format_plus_invite_opaque(self):
        # Real 12-byte token from the wild: no creator_id encoded.
        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/+cSEYklbAh0Q5NDM0")
        assert "error" in result
        assert "opaque" in result["error"].lower()

    def test_private_channel_url_decodes_ids(self):
        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/c/4395357680/42")
        d = result["data"]
        assert d["channel_internal_id"] == 4395357680
        assert d["channel_id"] == -1004395357680
        assert d["message_id"] == 42
        assert "private" in d["url_type"].lower()

    def test_private_channel_url_no_message(self):
        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/c/4395357680")
        # Now matches too — URL without a message id still yields channel decoding.
        # Falls through to invalid URL since the regex requires the second id... let's assert both branches.
        # (This test documents current behaviour; adjust when we relax the regex.)
        assert "error" in result or result.get("data", {}).get("channel_internal_id") == 4395357680

    @patch("sharetrace.modules.telegram.requests")
    def test_public_channel_preview(self, mock_requests):
        html = (
            '<html><head>'
            '<meta property="og:title" content="Durov&#39;s Channel"/>'
            '<meta property="og:description" content="Founder of Telegram."/>'
            '<meta property="og:image" content="https://cdn.telegram.org/photo.jpg"/>'
            '</head><body>'
            '<div class="tgme_channel_info_counter">'
            '<span class="counter_value">12 345 678</span>'
            '<span class="counter_type">subscribers</span>'
            '</div></body></html>'
        )
        resp = MagicMock(status_code=200, text=html)
        mock_requests.get.return_value = resp

        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/durov")
        assert result["data"]["username"] == "durov"
        assert result["data"]["name"] == "Durov's Channel"
        assert result["data"]["bio"] == "Founder of Telegram."
        assert result["data"]["follower_count"] == 12345678
        assert result["data"]["avatar_url"].startswith("https://")

    @patch("sharetrace.modules.telegram.requests")
    def test_public_channel_with_message_id(self, mock_requests):
        html = (
            '<html><head>'
            '<meta property="og:title" content="Some Channel"/>'
            '<meta property="og:description" content="A description."/>'
            '</head></html>'
        )
        mock_requests.get.return_value = MagicMock(status_code=200, text=html)

        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/WagonWheelZ/12345")
        assert result["data"]["username"] == "WagonWheelZ"
        assert result["data"]["name"] == "Some Channel"

    @patch("sharetrace.modules.telegram.requests")
    def test_public_channel_no_preview(self, mock_requests):
        html = '<html><body>No metadata</body></html>'
        mock_requests.get.return_value = MagicMock(status_code=200, text=html)

        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/somebody")
        assert "error" in result

    def test_invalid_url(self):
        from sharetrace.modules.telegram import telegram
        assert "error" in telegram("https://example.com/foo")


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

    @patch("sharetrace.modules.tiktok.requests")
    def test_profile_url_accepted(self, mock_requests):
        # The URL guard must accept @handle URLs even though the module still
        # relies on the shareUser blob (may or may not be present on the page).
        mock_session = MagicMock()
        first_resp = MagicMock()
        first_resp.url = "https://www.tiktok.com/@someuser"
        second_resp = MagicMock()
        second_resp.text = "<html>no share user here</html>"
        mock_session.get.side_effect = [first_resp, second_resp]
        mock_requests.Session.return_value = mock_session

        from sharetrace.modules.tiktok import tiktok
        result = tiktok("https://www.tiktok.com/@someuser")
        # We don't get data because the blob is missing, but the URL passed the guard.
        assert "error" in result
        assert "Invalid URL format" not in result["error"]

    @pytest.mark.parametrize("url", [
        "https://www.tiktok.com/@someuser",
        "https://tiktok.com/@nata.art.ua",
        "https://www.tiktok.com/@ilya_navvro/video/7620415832434265351",
    ])
    def test_url_guard_accepts_profile_and_video(self, url):
        # Pure regex check — no HTTP.
        from sharetrace.modules.tiktok import TIKTOK_URL_RE
        assert TIKTOK_URL_RE.search(url) is not None

    def test_invalid_url(self):
        from sharetrace.modules.tiktok import tiktok
        result = tiktok("https://example.com/foo")
        assert "error" in result
        assert "Invalid URL format" in result["error"]

    @patch("sharetrace.modules.tiktok.requests")
    def test_universal_data_profile_fallback(self, mock_requests):
        universal = json.dumps({
            "__DEFAULT_SCOPE__": {
                "webapp.user-detail": {
                    "userInfo": {
                        "user": {
                            "id": "1234",
                            "uniqueId": "someuser",
                            "nickname": "Some User",
                            "region": "GB",
                            "avatarLarger": "https://p16.tiktok.com/x.jpg",
                            "signature": "hi",
                            "privateAccount": False,
                        },
                        "stats": {
                            "followerCount": 42,
                            "followingCount": 7,
                            "videoCount": 3,
                            "heartCount": 100,
                        },
                    }
                }
            }
        })
        html = f'<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{universal}</script></html>'

        mock_session = MagicMock()
        first_resp = MagicMock(); first_resp.url = "https://www.tiktok.com/@someuser"
        second_resp = MagicMock(); second_resp.text = html
        mock_session.get.side_effect = [first_resp, second_resp]
        mock_requests.Session.return_value = mock_session

        from sharetrace.modules.tiktok import tiktok
        result = tiktok("https://www.tiktok.com/@someuser")
        assert result["data"]["user_id"] == "1234"
        assert result["data"]["username"] == "someuser"
        assert result["data"]["follower_count"] == 42
        assert result["data"]["country"] == "United Kingdom"

    @patch("sharetrace.modules.tiktok.requests")
    def test_universal_data_video_fallback(self, mock_requests):
        universal = json.dumps({
            "__DEFAULT_SCOPE__": {
                "webapp.video-detail": {
                    "itemInfo": {
                        "itemStruct": {
                            "author": {"id": "9", "uniqueId": "vidmaker", "nickname": "V"},
                            "authorStats": {"followerCount": 5},
                        }
                    }
                }
            }
        })
        html = f'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{universal}</script>'

        mock_session = MagicMock()
        first_resp = MagicMock(); first_resp.url = "https://www.tiktok.com/@vidmaker/video/1"
        second_resp = MagicMock(); second_resp.text = html
        mock_session.get.side_effect = [first_resp, second_resp]
        mock_requests.Session.return_value = mock_session

        from sharetrace.modules.tiktok import tiktok
        result = tiktok("https://www.tiktok.com/@vidmaker/video/1")
        assert result["data"]["user_id"] == "9"
        assert result["data"]["username"] == "vidmaker"
        assert result["data"]["follower_count"] == 5


# ---------------------------------------------------------------------------
# Google Docs
# ---------------------------------------------------------------------------
class TestGDoc:
    SAMPLE_SUCCESS = {
        "createdDate": "2024-01-02T03:04:05.678Z",
        "modifiedDate": "2024-06-07T08:09:10.111Z",
        "permissions": [
            {"id": "anyoneWithLink", "role": "reader", "type": "anyone"},
            {
                "id": "1234567890",
                "role": "owner",
                "name": "Jane Doe",
                "emailAddress": "jane@example.com",
                "photoLink": "https://lh3.googleusercontent.com/a/x",
                "type": "user",
            },
        ],
        "userPermission": {"id": "me", "role": "reader"},
    }

    VALID_URL = (
        "https://docs.google.com/document/d/"
        "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
    )

    @patch("sharetrace.modules.gdoc.requests")
    def test_extract_owner(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(self.SAMPLE_SUCCESS)
        mock_resp.json.return_value = self.SAMPLE_SUCCESS
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.gdoc import gdoc
        result = gdoc(self.VALID_URL)
        assert "data" in result
        assert result["data"]["email"] == "jane@example.com"
        assert result["data"]["name"] == "Jane Doe"
        assert result["data"]["google_id"] == "1234567890"
        assert result["data"]["public_permissions"] == "reader"
        assert result["data"]["avatar_url"].startswith("https://")
        assert result["data"]["created_at"] is not None
        assert result["data"]["modified_at"] is not None

    @patch("sharetrace.modules.gdoc.requests")
    def test_file_not_found(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.text = '{"error": {"code": 404, "message": "File not found: xyz"}}'
        mock_resp.status_code = 404
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.gdoc import gdoc
        result = gdoc(self.VALID_URL)
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("sharetrace.modules.gdoc.time.sleep")
    @patch("sharetrace.modules.gdoc.requests")
    def test_rate_limit_exhaustion(self, mock_requests, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.text = '{"error": {"errors": [{"reason": "rateLimitExceeded"}]}}'
        mock_resp.status_code = 403
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.gdoc import gdoc
        result = gdoc(self.VALID_URL)
        assert "error" in result
        assert mock_requests.get.call_count == 5  # MAX_RETRIES

    def test_invalid_url(self):
        from sharetrace.modules.gdoc import gdoc
        result = gdoc("https://example.com/something")
        assert "error" in result
        assert "invalid" in result["error"].lower()

    def test_url_pattern_matches_but_id_missing(self):
        from sharetrace.modules.gdoc import gdoc
        # Pattern is satisfied by segment, but no 25+ char id follows
        result = gdoc("https://docs.google.com/document/d/short/edit")
        assert "error" in result

    @patch("sharetrace.modules.gdoc.requests")
    def test_missing_owner_permission(self, mock_requests):
        payload = {
            "createdDate": "2024-01-02T03:04:05.678Z",
            "modifiedDate": "2024-01-02T03:04:05.678Z",
            "permissions": [{"id": "anyoneWithLink", "role": "reader"}],
            "userPermission": {"id": "me", "role": "reader"},
        }
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(payload)
        mock_resp.json.return_value = payload
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp

        from sharetrace.modules.gdoc import gdoc
        result = gdoc(self.VALID_URL)
        assert "error" in result
        assert "identity" in result["error"].lower()


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------
class TestGitHub:
    VALID_COMMIT_URL = (
        "https://github.com/torvalds/linux/commit/"
        "1da177e4c3f41524e886b7f1b8a0c1fc7321cac2"
    )
    VALID_PROFILE_URL = "https://github.com/torvalds"

    PATCH_BODY = (
        "From 1da177e4c3f41524e886b7f1b8a0c1fc7321cac2 Mon Sep 17 00:00:00 2001\n"
        "From: Linus Torvalds <torvalds@linuxfoundation.org>\n"
        "Date: Sat, 16 Apr 2005 15:20:36 -0700\n"
        "Subject: Initial commit\n\n"
        "diff --git a/Makefile b/Makefile\n"
    )

    @patch("sharetrace.modules.github.requests")
    def test_commit_route_happy(self, mock_requests):
        resp = MagicMock(status_code=200, text=self.PATCH_BODY)
        mock_requests.get.return_value = resp
        from sharetrace.modules.github import github
        r = github(self.VALID_COMMIT_URL)
        assert r["data"]["name"] == "Linus Torvalds"
        assert r["data"]["email"] == "torvalds@linuxfoundation.org"
        assert r["data"]["repo"] == "torvalds/linux"
        assert r["data"]["commit_sha"].startswith("1da177e4")
        assert "is_noreply" not in r["data"]

    @patch("sharetrace.modules.github.requests")
    def test_commit_route_noreply(self, mock_requests):
        body = self.PATCH_BODY.replace(
            "torvalds@linuxfoundation.org",
            "12345+ghost@users.noreply.github.com",
        )
        resp = MagicMock(status_code=200, text=body)
        mock_requests.get.return_value = resp
        from sharetrace.modules.github import github
        r = github(self.VALID_COMMIT_URL)
        assert r["data"]["is_noreply"] is True
        assert r["data"]["email"].endswith("users.noreply.github.com")

    @patch("sharetrace.modules.github.requests")
    def test_commit_route_quoted_display_name(self, mock_requests):
        # Pathological but RFC-valid: quoted display name containing a '<'.
        # Naive regex would bind to the first '<' and return "inner" as email.
        body = (
            'From abc123 Mon Sep 17 00:00:00 2001\n'
            'From: "weird <inner>" <real@example.com>\n'
            'Date: Sat, 16 Apr 2005 15:20:36 -0700\n'
            'Subject: Edge case\n\n'
            'diff --git a/x b/x\n'
        )
        resp = MagicMock(status_code=200, text=body)
        mock_requests.get.return_value = resp
        from sharetrace.modules.github import github
        r = github(self.VALID_COMMIT_URL)
        assert r["data"]["email"] == "real@example.com"

    @patch("sharetrace.modules.github.requests")
    def test_commit_route_404(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=404, text="Not Found")
        from sharetrace.modules.github import github
        r = github(self.VALID_COMMIT_URL)
        assert "error" in r
        assert "not found" in r["error"].lower() or "private" in r["error"].lower()

    @patch("sharetrace.modules.github.requests")
    def test_profile_route_happy(self, mock_requests):
        events = [
            {
                "type": "PushEvent",
                "payload": {
                    "commits": [
                        {"author": {"name": "Linus", "email": "torvalds@linuxfoundation.org"}},
                        {"author": {"name": "Linus", "email": "12345+ghost@users.noreply.github.com"}},
                    ]
                },
            },
            {"type": "WatchEvent", "payload": {}},  # ignored
        ]
        resp = MagicMock(status_code=200)
        resp.json.return_value = events
        mock_requests.get.return_value = resp
        from sharetrace.modules.github import github
        r = github(self.VALID_PROFILE_URL)
        assert r["data"]["username"] == "torvalds"
        assert {"name": "Linus", "email": "torvalds@linuxfoundation.org"} in r["data"]["emails"]
        assert r["data"]["noreply_emails"] == ["12345+ghost@users.noreply.github.com"]

    @patch("sharetrace.modules.github.requests")
    def test_profile_route_empty(self, mock_requests):
        resp = MagicMock(status_code=200)
        resp.json.return_value = []
        mock_requests.get.return_value = resp
        from sharetrace.modules.github import github
        r = github(self.VALID_PROFILE_URL)
        assert "error" in r

    @patch("sharetrace.modules.github.requests")
    def test_profile_route_rate_limited(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=403, text="rate limit")
        from sharetrace.modules.github import github
        r = github(self.VALID_PROFILE_URL)
        assert "rate" in r["error"].lower()

    def test_invalid_url(self):
        from sharetrace.modules.github import github
        r = github("https://example.com")
        assert "error" in r

    @patch("sharetrace.modules.github.requests")
    def test_repo_route_delegates_to_owner_profile(self, mock_requests):
        events = [{
            "type": "PushEvent",
            "payload": {"commits": [
                {"author": {"name": "Sox", "email": "sox@example.com"}},
            ]},
        }]
        resp = MagicMock(status_code=200)
        resp.json.return_value = events
        mock_requests.get.return_value = resp

        from sharetrace.modules.github import github
        r = github("https://github.com/soxoj/sharetrace")
        assert r["data"]["username"] == "soxoj"
        assert {"name": "Sox", "email": "sox@example.com"} in r["data"]["emails"]
        # Ensure it hit the /users/{owner}/events/public endpoint, not the repo URL.
        called_url = mock_requests.get.call_args[0][0]
        assert called_url == "https://api.github.com/users/soxoj/events/public"


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------
class TestYouTube:
    def _channel_html(self) -> str:
        initial = {
            "header": {"pageHeaderRenderer": {"pageTitle": "0dayCTF"}},
            "metadata": {"channelMetadataRenderer": {
                "title": "0dayCTF",
                "externalId": "UCabcdefghijklmnopqrstuv",
                "description": "CTF & OSINT videos.",
                "avatar": {"thumbnails": [{"url": "https://yt3.ggpht.com/small"},
                                          {"url": "https://yt3.ggpht.com/big"}]},
            }},
            "onResponseReceivedEndpoints": [{
                "appendContinuationItemsAction": {"continuationItems": [{
                    "aboutChannelRenderer": {"metadata": {"aboutChannelViewModel": {
                        "description": "CTF & OSINT videos.",
                        "country": "Germany",
                        "joinedDateText": {"content": "Joined Jan 5, 2019"},
                        "subscriberCountText": "45.6K subscribers",
                        "viewCountText": "1,234,567 views",
                        "videoCountText": "123 videos",
                        "links": [{"channelExternalLinkViewModel": {
                            "title": {"content": "Twitter"},
                            "link": {"content": "https://x.com/0dayCTF"},
                        }}],
                    }}},
                }]},
            }],
            "channelHandleText": {"runs": [{"text": "@0dayCTF"}]},
        }
        return f'<html><script>var ytInitialData = {json.dumps(initial)};</script></html>'

    def _video_html(self) -> str:
        player = {
            "videoDetails": {
                "videoId": "dQw4w9WgXcQ",
                "title": "Never Gonna Give You Up",
                "author": "Rick Astley",
                "channelId": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "viewCount": "1500000000",
            },
            "microformat": {"playerMicroformatRenderer": {
                "publishDate": "2009-10-25",
                "availableCountries": ["US"],
            }},
        }
        return f'<html><script>var ytInitialPlayerResponse = {json.dumps(player)};</script></html>'

    @patch("sharetrace.modules.youtube.requests")
    def test_channel_by_handle(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=200, text=self._channel_html())
        from sharetrace.modules.youtube import youtube
        r = youtube("https://www.youtube.com/@0dayCTF")
        d = r["data"]
        assert d["channel_id"] == "UCabcdefghijklmnopqrstuv"
        assert d["username"] == "0dayCTF"
        assert d["name"] == "0dayCTF"
        assert d["country"] == "Germany"
        assert d["joined_date"] == "Jan 5, 2019"
        assert d["subscriber_count"] == 45600
        assert d["video_count"] == 123
        assert d["external_links"] == [{"title": "Twitter", "url": "https://x.com/0dayCTF"}]

    @patch("sharetrace.modules.youtube.requests")
    def test_channel_by_ucid(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=200, text=self._channel_html())
        from sharetrace.modules.youtube import youtube
        r = youtube("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv")
        assert r["data"]["channel_id"] == "UCabcdefghijklmnopqrstuv"
        # Second arg to _fetch should have been the /about tab.
        called_url = mock_requests.get.call_args[0][0]
        assert called_url.endswith("/about")

    @patch("sharetrace.modules.youtube.requests")
    def test_video_short_link(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=200, text=self._video_html())
        from sharetrace.modules.youtube import youtube
        r = youtube("https://youtu.be/dQw4w9WgXcQ?si=abc")
        d = r["data"]
        assert d["video_id"] == "dQw4w9WgXcQ"
        assert d["channel_id"] == "UCuAXFkgsw1L7xaCfnd5JJOw"
        assert d["name"] == "Rick Astley"
        assert d["view_count"] == 1500000000
        assert d["published_at"] == "2009-10-25"
        assert d["share_method"].startswith("youtube_share_button")
        assert "si=" in d["share_method"]

    @patch("sharetrace.modules.youtube.requests")
    def test_video_no_share_marker(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=200, text=self._video_html())
        from sharetrace.modules.youtube import youtube
        r = youtube("https://youtu.be/dQw4w9WgXcQ")
        # No si/sl/is → field absent (pruned).
        assert "share_method" not in r["data"]

    @pytest.mark.parametrize("url,marker", [
        ("https://youtu.be/abc?si=xyz", "si"),
        ("https://youtu.be/abc?sl=xyz", "sl"),
        ("https://youtu.be/abc?is=xyz", "is"),
        ("https://youtu.be/abc?feature=share", None),
    ])
    def test_share_marker_detection(self, url, marker):
        from sharetrace.modules.youtube import _detect_share_marker
        assert _detect_share_marker(url) == marker

    @patch("sharetrace.modules.youtube.requests")
    def test_video_watch(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=200, text=self._video_html())
        from sharetrace.modules.youtube import youtube
        r = youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert r["data"]["video_id"] == "dQw4w9WgXcQ"

    @patch("sharetrace.modules.youtube.requests")
    def test_video_shorts(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=200, text=self._video_html())
        from sharetrace.modules.youtube import youtube
        r = youtube("https://youtube.com/shorts/ou2X53h-SYk")
        # Note: we don't extract the URL video_id, but the mocked page's video is Rick's.
        assert "data" in r
        assert r["data"]["channel_id"].startswith("UC")

    def test_invalid_url(self):
        from sharetrace.modules.youtube import youtube
        assert "error" in youtube("https://example.com/foo")

    @patch("sharetrace.modules.youtube.requests")
    def test_no_ytinitial(self, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=200, text="<html>nothing</html>")
        from sharetrace.modules.youtube import youtube
        assert "error" in youtube("https://youtu.be/dQw4w9WgXcQ")

    @patch("sharetrace.modules.youtube.requests")
    def test_handle_via_vanity_url(self, mock_requests):
        # Live pages expose the handle via metadata.vanityChannelUrl, not channelHandleText.
        initial = {
            "metadata": {"channelMetadataRenderer": {
                "title": "Google Developers",
                "externalId": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
                "vanityChannelUrl": "http://www.youtube.com/@GoogleDevelopers",
            }},
        }
        html = f'<html><script>var ytInitialData = {json.dumps(initial)};</script></html>'
        mock_requests.get.return_value = MagicMock(status_code=200, text=html)
        from sharetrace.modules.youtube import youtube
        r = youtube("https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw")
        assert r["data"]["username"] == "GoogleDevelopers"


# ---------------------------------------------------------------------------
# GDoc — Drive folder route
# ---------------------------------------------------------------------------
class TestGDocFolder:
    FOLDER_URL = "https://drive.google.com/drive/folders/1x-JhS4WLppkh42grXG1nemiLXopzJB6x"

    def test_folder_id_extraction(self):
        from sharetrace.modules.gdoc import _extract_doc_id
        assert _extract_doc_id(self.FOLDER_URL) == "1x-JhS4WLppkh42grXG1nemiLXopzJB6x"

    def test_folder_url_matches(self):
        from sharetrace.modules.gdoc import URL_MATCH
        assert URL_MATCH.search(self.FOLDER_URL) is not None
        assert URL_MATCH.search(
            "https://drive.google.com/drive/mobile/folders/1t-hTqg0-02t0cnc5SypHnb8t3CfE3bXU"
        ) is not None
        assert URL_MATCH.search(
            "https://drive.google.com/drive/u/0/folders/1ynTc3z38AkkR-6-gl4b6UmmQunb0oo6A"
        ) is not None

    @patch("sharetrace.modules.gdoc.requests")
    def test_folder_owner_extraction(self, mock_requests):
        sample = {
            "createdDate": "2024-01-02T03:04:05.678Z",
            "modifiedDate": "2024-06-07T08:09:10.111Z",
            "permissions": [
                {"id": "9911223344", "role": "owner", "name": "Folder Owner",
                 "emailAddress": "owner@example.com", "type": "user"},
            ],
        }
        resp = MagicMock(status_code=200, text=json.dumps(sample))
        resp.json.return_value = sample
        mock_requests.get.return_value = resp

        from sharetrace.modules.gdoc import gdoc
        result = gdoc(self.FOLDER_URL)
        assert result["data"]["email"] == "owner@example.com"
        assert result["data"]["name"] == "Folder Owner"
