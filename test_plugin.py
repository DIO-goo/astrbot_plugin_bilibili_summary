"""
插件测试脚本
用于验证插件的基本功能
"""
import re
from main import BilibiliSummaryPlugin


def test_url_parsing():
    """测试URL解析功能"""
    print("=== 测试URL解析功能 ===")
    
    # 创建一个模拟的插件实例（仅用于测试URL解析）
    class MockConfig:
        def get(self, key, default=None):
            return default
    
    class MockContext:
        pass
    
    plugin = BilibiliSummaryPlugin(MockContext(), MockConfig())
    
    # 测试用例
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
        status = "✅" if result == expected else "❌"
        print(f"{status} 输入: '{input_url}' -> 输出: '{result}' (期望: '{expected}')")


def test_link_extraction():
    """测试链接提取功能"""
    print("\n=== 测试链接提取功能 ===")
    
    class MockConfig:
        def get(self, key, default=None):
            return default
    
    class MockContext:
        pass
    
    plugin = BilibiliSummaryPlugin(MockContext(), MockConfig())
    
    # 测试用例
    test_texts = [
        "看看这个视频 https://www.bilibili.com/video/BV1jv7YzJED2",
        "BV1jv7YzJED2 这个视频不错",
        "分享一个视频 https://b23.tv/abc123",
        "av123456 老视频了",
        "没有bilibili链接的文本",
        "多个链接 BV1jv7YzJED2 和 https://www.bilibili.com/video/BV2abc123def",
    ]
    
    for text in test_texts:
        links = plugin.extract_links_from_text(text)
        print(f"文本: '{text}'")
        print(f"提取到的链接: {links}")
        print()


def test_regex_patterns():
    """测试正则表达式模式"""
    print("=== 测试正则表达式模式 ===")
    
    patterns = [
        (r'BV[a-zA-Z0-9]{10}', "BV号模式"),
        (r'av\d+', "AV号模式"),
        (r'https?://(?:www\.)?bilibili\.com/video/[^\s\'"<>]+', "标准bilibili链接"),
        (r'https?://b23\.tv/[^\s\'"<>]+', "短链接模式"),
    ]
    
    test_strings = [
        "BV1jv7YzJED2",
        "av123456",
        "https://www.bilibili.com/video/BV1jv7YzJED2",
        "https://b23.tv/abc123",
        "invalid_string",
    ]
    
    for pattern, name in patterns:
        print(f"\n{name}: {pattern}")
        for test_str in test_strings:
            match = re.search(pattern, test_str, re.IGNORECASE)
            status = "✅" if match else "❌"
            print(f"  {status} '{test_str}' -> {match.group() if match else 'No match'}")


if __name__ == "__main__":
    print("Bilibili Summary Plugin 测试")
    print("=" * 50)
    
    try:
        test_url_parsing()
        test_link_extraction()
        test_regex_patterns()
        print("\n✅ 所有基础测试完成")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()