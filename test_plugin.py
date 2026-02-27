"""
插件测试脚本
用于验证插件的基本功能
"""
import re
from unittest.mock import MagicMock
from main import BilibiliSummaryPlugin


class MockConfig:
    """模拟配置对象，返回所有配置项的默认值"""
    def get(self, key, default=None):
        return default


def _make_plugin() -> BilibiliSummaryPlugin:
    """创建用于测试的插件实例"""
    context = MagicMock()
    return BilibiliSummaryPlugin(context, MockConfig())


def test_url_parsing():
    """测试URL解析功能"""
    print("=== 测试URL解析功能 ===")

    plugin = _make_plugin()

    test_cases = [
        ("BV1jv7YzJED2", "BV1jv7YzJED2"),
        ("https://www.bilibili.com/video/BV1jv7YzJED2", "BV1jv7YzJED2"),
        ("https://m.bilibili.com/video/BV1jv7YzJED2", "BV1jv7YzJED2"),
        ("av123456", "av123456"),
        ("https://www.bilibili.com/video/av123456", "av123456"),
        ("1jv7YzJED2", "BV1jv7YzJED2"),
        ("123456", "av123456"),
        ("invalid_url", None),
        ("", None),
    ]

    for input_url, expected in test_cases:
        result = plugin.parse_bilibili_url(input_url)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: '{input_url}' -> '{result}' (expected: '{expected}')")
        assert result == expected, (
            f"parse_bilibili_url('{input_url}'): got '{result}', expected '{expected}'"
        )

    print("  URL解析测试全部通过\n")


def test_link_extraction():
    """测试链接提取功能"""
    print("=== 测试链接提取功能 ===")

    plugin = _make_plugin()

    # 应能提取到链接的用例
    cases_with_links = [
        ("看看这个视频 https://www.bilibili.com/video/BV1jv7YzJED2", ["BV1jv7YzJED2"]),
        ("BV1jv7YzJED2 这个视频不错", ["BV1jv7YzJED2"]),
        ("分享一个视频 https://b23.tv/abc123", ["b23.tv"]),
        ("av123456 老视频了", ["av123456"]),
    ]

    for text, expected_substrings in cases_with_links:
        links = plugin.extract_links_from_text(text)
        print(f"  '{text}' -> {links}")
        assert len(links) > 0, f"Should extract links from: '{text}'"
        for substr in expected_substrings:
            assert any(substr in link for link in links), (
                f"Expected '{substr}' in extracted links {links} from '{text}'"
            )

    # 不应提取到链接的用例
    no_link_text = "没有bilibili链接的文本"
    links = plugin.extract_links_from_text(no_link_text)
    print(f"  '{no_link_text}' -> {links}")
    assert len(links) == 0, f"Should not extract links from: '{no_link_text}'"

    print("  链接提取测试全部通过\n")


def test_regex_patterns():
    """测试正则表达式模式"""
    print("=== 测试正则表达式模式 ===")

    patterns = {
        r'BV[a-zA-Z0-9]{10}': ["BV1jv7YzJED2"],
        r'av\d+': ["av123456"],
        r'https?://(?:www\.)?bilibili\.com/video/[^\s\'"<>]+': [
            "https://www.bilibili.com/video/BV1jv7YzJED2"
        ],
        r'https?://b23\.tv/[^\s\'"<>]+': ["https://b23.tv/abc123"],
    }

    should_not_match = "invalid_string"

    for pattern, positive_cases in patterns.items():
        for test_str in positive_cases:
            match = re.search(pattern, test_str, re.IGNORECASE)
            print(f"  PASS: /{pattern}/ matches '{test_str}'")
            assert match, f"Pattern '{pattern}' should match '{test_str}'"

        match = re.search(pattern, should_not_match, re.IGNORECASE)
        assert not match, f"Pattern '{pattern}' should NOT match '{should_not_match}'"

    print("  正则模式测试全部通过\n")


if __name__ == "__main__":
    print("Bilibili Summary Plugin 测试")
    print("=" * 50)

    test_url_parsing()
    test_link_extraction()
    test_regex_patterns()

    print("All tests passed.")
