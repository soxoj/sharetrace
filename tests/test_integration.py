"""Integration tests that make real HTTP requests.

Run with: pytest tests/test_integration.py -v
Skip with: pytest -m "not integration"

WARNING: These tests depend on external services and real URLs.
They may fail if links expire, platforms change their APIs, or
network is unavailable.
"""
import pytest

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Microsoft (offline parsing — always works)
# ---------------------------------------------------------------------------
class TestMicrosoftIntegration:
    def test_sharepoint_url(self):
        from sharetrace.modules.microsoft import microsoft
        result = microsoft("https://company-my.sharepoint.com/:f:/g/personal/john_doe_contoso_com/EaBcDeFgHiJkLmN")
        assert result == {"data": {"email": "john.doe@contoso.com"}}

    def test_sharepoint_complex_domain(self):
        from sharetrace.modules.microsoft import microsoft
        result = microsoft("https://org-my.sharepoint.com/:x:/g/personal/alice_bob_example_org/SomeHash")
        assert result == {"data": {"email": "alice.bob@example.org"}}


# ---------------------------------------------------------------------------
# Telegram (offline decoding — always works)
# ---------------------------------------------------------------------------
class TestTelegramIntegration:
    def test_synthetic_joinchat(self):
        import base64
        import struct
        from sharetrace.modules.telegram import telegram

        user_id = 123456789
        payload = struct.pack('<I', user_id) + b'\x00' * 12
        hash_str = base64.urlsafe_b64encode(payload).decode().rstrip('=')

        result = telegram(f"https://t.me/joinchat/{hash_str}")
        assert result == {"data": {"user_id": 123456789}}

    def test_real_joinchat(self):
        """Real joinchat link found at https://github.com/ferdium/ferdium-app/issues/1027"""
        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/joinchat/BxLzSUMe29j595QsAK3l0A")
        assert result == {"data": {"user_id": 1240666631}}

    def test_aaaaa_link_decodes_to_zero(self):
        """Links starting with AAAAA decode to user_id=0 and contain no useful data."""
        from sharetrace.modules.telegram import telegram
        result = telegram("https://t.me/joinchat/AAAAAFPnF5hQ6wA3uwqi6w")
        assert result == {"data": {"user_id": 0}}


# ---------------------------------------------------------------------------
# TikTok (real HTTP)
# Source: https://www.reddit.com/r/MonsterHunter/comments/1qzalgu/
# ---------------------------------------------------------------------------
class TestTikTokIntegration:
    def test_share_link(self):
        from sharetrace.modules.tiktok import tiktok
        try:
            result = tiktok("https://vt.tiktok.com/ZSm1NoGph/")
        except Exception:
            pytest.skip("TikTok unavailable")
        if "error" in result:
            pytest.skip(f"TikTok returned error: {result['error']}")

        data = result["data"]
        assert data["user_id"] == "7604491261622928405"
        assert data["username"] == "pokke.mho"
        assert data["nickname"] == "pokke"
        assert data["profile"] == "https://www.tiktok.com/@pokke.mho"
        assert data["country"] == "Peru"
        assert data["device"] == "android"
        assert data["share_method"] == "copy"
        assert data["shared_at"] == "2026-02-08 14:35:36"
        assert data["private_account"] is False
        assert data["dm_available"] is True
        assert isinstance(data["follower_count"], int)
        assert isinstance(data["video_count"], int)
        assert isinstance(data["heart_count"], int)
        assert data["avatar_url"].startswith("https://")


# ---------------------------------------------------------------------------
# Discord (real HTTP)
# discord-developers — long-lived public invite with known inviter
# ---------------------------------------------------------------------------
class TestDiscordIntegration:
    def test_invite_link(self):
        from sharetrace.modules.discord import discord
        try:
            result = discord("https://discord.gg/discord-developers")
        except Exception:
            pytest.skip("Discord API unavailable")
        if "error" in result:
            pytest.skip(f"Discord returned error: {result['error']}")

        data = result["data"]
        assert data["name"] == "Janet Cousins"
        assert data["created_at"] == "2015-01-01 00:00:00"


# ---------------------------------------------------------------------------
# Pinterest (real HTTP)
# Source: https://www.reddit.com/r/snails/comments/1ejwo0s/
# Source: https://www.reddit.com/r/selfpublish/comments/1ot539r/
# ---------------------------------------------------------------------------
class TestPinterestIntegration:
    @pytest.mark.parametrize("url,expected", [
        ("https://pin.it/5HWcLf5Kp", {
            "username": "lisagodden07",
            "user_id": "665829263567562400",
            "name": "Lisa Godden",
            "profile_url": "https://www.pinterest.com/lisagodden07/",
        }),
        ("https://pin.it/2lupYg3V5", {
            "username": "nfrankcaddel",
            "user_id": "908319956003886342",
            "name": "Frankie Caddel",
            "profile_url": "https://www.pinterest.com/nfrankcaddel/",
        }),
    ])
    def test_share_link(self, url, expected):
        from sharetrace.modules.pinterest import pinterest
        try:
            result = pinterest(url)
        except Exception:
            pytest.skip("Pinterest API unavailable")
        if "error" in result:
            pytest.skip(f"Pinterest returned error: {result['error']}")

        data = result["data"]
        assert data["username"] == expected["username"]
        assert data["user_id"] == expected["user_id"]
        assert data["name"] == expected["name"]
        assert data["profile_url"] == expected["profile_url"]
        assert data["avatar_url"].startswith("https://")


# ---------------------------------------------------------------------------
# Substack (real HTTP)
# Source: https://www.reddit.com/r/Substack/comments/1i94mlu/
# Source: https://www.reddit.com/r/Substack/comments/1o41zn9/
# ---------------------------------------------------------------------------
class TestSubstackIntegration:
    @pytest.mark.parametrize("url,expected", [
        (
            "https://substack.com/@yanagy/note/c-87419026?r=4o8c5e&utm_medium=ios&utm_source=notes-share-action",
            {
                "user_id": 282564482,
                "name": "Rebecca Ferguson",
                "handle": "becfergo",
                "profile_url": "https://substack.com/@becfergo",
                "profile_set_up_at": "2024-11-02T04:43:40.996Z",
            },
        ),
        (
            "https://substack.com/@szin/note/c-165345424?r=3bw75c&utm_source=notes-share-action&utm_medium=web",
            {
                "user_id": 201376560,
                "name": "Szin",
                "handle": "szin",
                "profile_url": "https://substack.com/@szin",
                "profile_set_up_at": "2024-01-29T13:22:02.223Z",
            },
        ),
    ])
    def test_share_link(self, url, expected):
        from sharetrace.modules.substack import substack
        try:
            result = substack(url)
        except Exception:
            pytest.skip("Substack unavailable")
        if "error" in result:
            pytest.skip(f"Substack returned error: {result['error']}")

        data = result["data"]
        assert data["user_id"] == expected["user_id"]
        assert data["name"] == expected["name"]
        assert data["handle"] == expected["handle"]
        assert data["profile_url"] == expected["profile_url"]
        assert data["profile_set_up_at"] == expected["profile_set_up_at"]
        assert data["photo_url"].startswith("https://")
        assert isinstance(data["bio"], str)
        assert len(data["bio"]) > 0


# ---------------------------------------------------------------------------
# Claude AI (real HTTP)
# Source: https://www.reddit.com/r/ClaudeAI/comments/1s3m6vs/
# Source: https://www.reddit.com/r/claudexplorers/comments/1qrxd8g/
# ---------------------------------------------------------------------------
class TestClaudeIntegration:
    @pytest.mark.parametrize("url,expected_user_id", [
        ("https://claude.ai/share/421c4c9c-d2c5-480f-8901-beb0fe3f7f92", "56e016a2-08de-4b31-bd8d-0fc04abc904d"),
        ("https://claude.ai/share/d2455011-cc87-417c-bfc5-489a4a6430d6", "b30bef9a-0d0c-46ca-99a1-cc993d7cff26"),
    ])
    def test_share_link(self, url, expected_user_id):
        from sharetrace.modules.claude import claude
        try:
            result = claude(url)
        except Exception:
            pytest.skip("Claude API unavailable")
        if "error" in result:
            pytest.skip(f"Claude returned error: {result['error']}")

        data = result["data"]
        assert data["name"] == "Joe"
        assert data["user_id"] == expected_user_id


# ---------------------------------------------------------------------------
# Suno (real HTTP) — verified working links
# ---------------------------------------------------------------------------
class TestSunoIntegration:
    @pytest.mark.parametrize("url,expected", [
        ("https://suno.com/s/DhNlguMvnrUiPRvC", {
            "username": "zaphod_42007",
            "name": "Zaphod_42007",
            "avatar_url": "https://cdn1.suno.ai/933b9d38.webp",
            "profile_url": "https://suno.com/@zaphod_42007/",
        }),
        ("https://suno.com/s/yu8ZwZ4J1mT3KjXF", {
            "username": "floggingmars",
            "name": "FloggingMARS",
            "avatar_url": "https://cdn1.suno.ai/33732e75.webp",
            "profile_url": "https://suno.com/@floggingmars/",
        }),
        ("https://suno.com/s/fF8GbSM1FfJrAhxH", {
            "username": "lyricalgold",
            "name": "Tressa",
            "avatar_url": "https://cdn1.suno.ai/b8cbf9d2.webp",
            "profile_url": "https://suno.com/@lyricalgold/",
        }),
    ])
    def test_share_link(self, url, expected):
        from sharetrace.modules.suno import suno
        try:
            result = suno(url)
        except Exception:
            pytest.skip("Suno API unavailable")
        if "error" in result:
            pytest.skip(f"Suno returned error: {result['error']}")

        data = result["data"]
        assert data["username"] == expected["username"]
        assert data["name"] == expected["name"]
        assert data["avatar_url"] == expected["avatar_url"]
        assert data["profile_url"] == expected["profile_url"]


# ---------------------------------------------------------------------------
# Perplexity (real HTTP)
# Source: https://www.reddit.com/r/conspiracy/comments/1r64yog/
# Source: https://www.reddit.com/r/LocalLLaMA/comments/1lgq7xy/
# ---------------------------------------------------------------------------
class TestPerplexityIntegration:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.perplexity.ai/search/e474531e-cd5e-4ec5-bd29-3f98b487f45d", {
            "username": "trickydick",
            "user_id": "885a2734-fdff-4c15-a90a-b646808c481a",
        }),
        ("https://www.perplexity.ai/search/choose-the-number-between-1-an-ogpHCCs2SNmoiiVGpLKI2A", {
            "username": "075bct006a46226",
            "user_id": "e3ec0850-8463-40dd-ba86-28293ce587fa",
        }),
    ])
    def test_search_link(self, url, expected):
        from sharetrace.modules.perplexity import perplexity
        try:
            result = perplexity(url)
        except Exception:
            pytest.skip("Perplexity API unavailable")
        if "error" in result:
            pytest.skip(f"Perplexity returned error: {result['error']}")

        data = result["data"]
        assert data["username"] == expected["username"]
        assert data["user_id"] == expected["user_id"]


# ---------------------------------------------------------------------------
# ChatGPT (real HTTP) — share links expire frequently, og:description may be absent
# Source: https://www.reddit.com/r/OpenAI/comments/1q4e4zn/
# ---------------------------------------------------------------------------
class TestChatGPTIntegration:
    @pytest.mark.parametrize("url,expected_name", [
        ("https://chatgpt.com/share/69224d40-e048-800a-9780-e00ca84fd543", "Rebecca Brewer"),
        ("https://chatgpt.com/share/684adf05-5d38-8008-a870-c8e7bfb4ecb9", "David Manouchehri"),
    ])
    def test_share_link(self, url, expected_name):
        from sharetrace.modules.chatgpt import chatgpt
        try:
            result = chatgpt(url)
        except Exception:
            pytest.skip("ChatGPT unavailable")
        if "error" in result:
            pytest.skip(f"ChatGPT returned error: {result['error']}")

        assert result["data"]["name"] == expected_name


# ---------------------------------------------------------------------------
# Instagram (real HTTP) — requires shid data which expires
# Source: https://www.reddit.com/r/VideoEditors_forhire/comments/1jdy4hy/
# ---------------------------------------------------------------------------
class TestInstagramIntegration:
    def test_share_link_structure(self):
        """Instagram sharer data expires quickly, so only verify structure."""
        from sharetrace.modules.instagram import instagram
        # Any public post URL — sharer data may or may not be present
        url = "https://www.instagram.com/p/CmUv48DLvxd/"
        try:
            result = instagram(url)
        except Exception:
            pytest.skip("Instagram unavailable")
        assert "data" in result or "error" in result
        if "data" in result:
            assert isinstance(result["data"]["username"], str)
            assert isinstance(result["data"]["user_id"], str)
            assert result["data"]["profile_url"].startswith("https://www.instagram.com/")


# ---------------------------------------------------------------------------
# Full pipeline test via parse_url
# ---------------------------------------------------------------------------
class TestParseUrlIntegration:
    def test_unsupported_url(self):
        from sharetrace import parse_url
        result = parse_url("https://google.com")
        assert result == {"error": "Unsupported platform or invalid URL"}

    def test_microsoft_via_parse_url(self):
        from sharetrace import parse_url
        result = parse_url("https://company-my.sharepoint.com/:f:/g/personal/john_doe_contoso_com/EaBcDeFgHiJ")
        assert result == {"data": {"email": "john.doe@contoso.com"}}

    def test_suno_via_parse_url(self):
        from sharetrace import parse_url
        try:
            result = parse_url("https://suno.com/s/DhNlguMvnrUiPRvC")
        except Exception:
            pytest.skip("Suno API unavailable")
        if "error" in result:
            pytest.skip(f"Suno returned error: {result['error']}")

        assert result["data"]["username"] == "zaphod_42007"
        assert result["data"]["name"] == "Zaphod_42007"
        assert result["data"]["profile_url"] == "https://suno.com/@zaphod_42007/"
