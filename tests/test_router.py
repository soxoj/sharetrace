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
        ("https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit", "gdoc"),
        ("https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/", "gdoc"),
        ("https://docs.google.com/presentation/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/", "gdoc"),
        ("https://docs.google.com/drawings/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/", "gdoc"),
        ("https://docs.google.com/forms/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/", "gdoc"),
        ("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/view", "gdoc"),
        ("https://script.google.com/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit", "gdoc"),
        ("https://jamboard.google.com/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/viewer", "gdoc"),
        ("https://www.google.com/maps/d/edit?mid=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms", "gdoc"),
        ("https://github.com/torvalds/linux/commit/1da177e4c3f41524e886b7f1b8a0c1fc7321cac2", "github"),
        ("https://github.com/torvalds/linux/pull/42/commits/1da177e4c3f41524e886b7f1b8a0c1fc7321cac2", "github"),
        ("https://github.com/torvalds/", "github"),
        ("https://github.com/torvalds", "github"),
        ("https://www.github.com/torvalds", "github"),
        ("https://github.com/torvalds?tab=repositories", "github"),
        # GitLab
        ("https://gitlab.com/gitlab-org/gitlab-foss/-/commit/c6da9d7f1b804966d13abd8aab4e87b0913af4b2", "gitlab"),
        ("https://gitlab.com/group/subgroup/project/-/commit/abcdef1234567", "gitlab"),
        ("https://gitlab.com/gitlab-bot", "gitlab"),
        ("https://gitlab.com/gitlab-bot/", "gitlab"),
        ("https://www.gitlab.com/gitlab-bot", "gitlab"),
        # Hugging Face
        ("https://huggingface.co/karpathy", "huggingface"),
        ("https://huggingface.co/karpathy/llm.c", "huggingface"),
        ("https://www.huggingface.co/julien-c", "huggingface"),
        # LinkedIn
        ("https://www.linkedin.com/in/reidhoffman", "linkedin"),
        ("https://linkedin.com/in/satyanadella", "linkedin"),
        ("https://www.linkedin.com/posts/reidhoffman_some-slug-abc123-activity-123456", "linkedin"),
        ("https://www.linkedin.com/pulse/article-slug-here", "linkedin"),
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
        "https://docs.google.com/",
        "https://www.google.com/maps/place/xyz",
        "https://github.com/",
        "https://github.com/torvalds/linux",
        "https://github.com/torvalds/linux/issues/1",
        "https://github.com/torvalds/linux/commit/",
        "https://github.com/torvalds/linux/commit/xyz",
        "https://github.com/foo-",          # trailing hyphen not allowed
        "https://github.com/-foo",          # leading hyphen not allowed
        # GitLab negatives — too-deep paths that aren't commit URLs
        "https://gitlab.com/gitlab-org/gitlab-foss",      # project URL, not commit, not bare profile
        "https://gitlab.com/",                             # empty path
        # LinkedIn negatives — unsupported sub-routes
        "https://www.linkedin.com/company/microsoft",
        "https://www.linkedin.com/feed/",
        "https://www.linkedin.com/",
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
                    "perplexity", "pinterest", "substack", "suno", "telegram", "claude", "gdoc", "github",
                    "gitlab", "huggingface", "linkedin"]
        for p in expected:
            assert p in platforms, f"{p} missing from supported platforms"
