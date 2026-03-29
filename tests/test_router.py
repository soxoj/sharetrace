"""Unit tests for URL routing and platform detection."""
import pytest
from sharetrace.router import detect_platform, get_parser, get_supported_platforms


class TestDetectPlatform:
    @pytest.mark.parametrize("url,expected", [
        ("https://vm.tiktok.com/ZMhABC123/", "tiktok"),
        ("https://vt.tiktok.com/ZMhXYZ789/", "tiktok"),
        ("https://tiktok.com/t/ZTRabc123/", "tiktok"),
        ("https://chatgpt.com/share/12345678-abcd-1234-abcd-123456789abc", "chatgpt"),
        ("https://claude.ai/share/abcdef12-3456-7890-abcd-ef1234567890", "claude"),
        ("https://discord.com/invite/abcXYZ", "discord"),
        ("https://discord.gg/abcXYZ", "discord"),
        ("https://www.instagram.com/reel/ABC123_def/", "instagram"),
        ("https://www.instagram.com/p/ABC123_def/", "instagram"),
        ("https://company-my.sharepoint.com/:f:/g/personal/john_doe_company_com/EaBcDeFgHiJ", "microsoft"),
        ("https://www.perplexity.ai/search/some-search-slug-abc123", "perplexity"),
        ("https://pin.it/AbC1dEf", "pinterest"),
        ("https://substack.com/@someuser/note/12345", "substack"),
        ("https://suno.com/s/abc123XYZ", "suno"),
        ("https://t.me/joinchat/AAAA_BBBBccccDDDD", "telegram"),
    ])
    def test_valid_urls(self, url, expected):
        assert detect_platform(url) == expected

    @pytest.mark.parametrize("url", [
        "https://google.com",
        "https://example.com/share/123",
        "https://tiktok.com/foryou",
        "https://instagram.com/username",
        "not a url",
        "",
    ])
    def test_invalid_urls(self, url):
        assert detect_platform(url) is None


class TestGetParser:
    def test_all_platforms_have_parsers(self):
        for platform in get_supported_platforms():
            parser = get_parser(platform)
            assert parser is not None, f"No parser for {platform}"
            assert callable(parser)

    def test_unknown_platform(self):
        assert get_parser("nonexistent") is None


class TestGetSupportedPlatforms:
    def test_returns_list(self):
        platforms = get_supported_platforms()
        assert isinstance(platforms, list)
        assert len(platforms) > 0

    def test_expected_platforms(self):
        platforms = get_supported_platforms()
        expected = ["tiktok", "chatgpt", "discord", "instagram", "microsoft",
                    "perplexity", "pinterest", "substack", "suno", "telegram", "claude"]
        for p in expected:
            assert p in platforms, f"{p} missing from supported platforms"
