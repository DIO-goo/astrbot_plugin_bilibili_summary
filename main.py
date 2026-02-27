import asyncio
import re
import json
import os
import tempfile
import hashlib
import time
from functools import reduce
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs, urlencode
import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.api.event import MessageChain
from .audio_service import AudioService

# 视频总结卡片HTML模板
VIDEO_SUMMARY_TEMPLATE = '''
<div style="
    font-family: 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', 'Helvetica Neue', Arial, sans-serif;
    width: 100%;
    min-height: 100%;
    background: linear-gradient(145deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 40px;
    color: #ffffff;
    box-sizing: border-box;
">
    <!-- 顶部标题区域 -->
    <div style="
        background: linear-gradient(135deg, #e94560 0%, #ff6b6b 100%);
        border-radius: 20px;
        padding: 36px;
        margin-bottom: 32px;
        box-shadow: 0 8px 24px rgba(233,69,96,0.4);
    ">
        <div style="
            font-size: 42px;
            font-weight: bold;
            line-height: 1.5;
            margin-bottom: 24px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        ">{{ platform_icon }} {{ title }}</div>

        <div style="
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            font-size: 28px;
            opacity: 0.95;
        ">
            <span style="
                background: rgba(255,255,255,0.25);
                padding: 10px 22px;
                border-radius: 30px;
            ">👤 {{ owner }}</span>
            <span style="
                background: rgba(255,255,255,0.25);
                padding: 10px 22px;
                border-radius: 30px;
            ">⏱️ {{ duration }}</span>
            <span style="
                background: rgba(255,255,255,0.25);
                padding: 10px 22px;
                border-radius: 30px;
            ">👀 {{ views }}</span>
            <span style="
                background: rgba(255,255,255,0.25);
                padding: 10px 22px;
                border-radius: 30px;
            ">👍 {{ likes }}</span>
        </div>
    </div>

    <!-- 总结区域 -->
    <div style="
        background: rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 36px;
        margin-bottom: 32px;
        border: 2px solid rgba(255,255,255,0.1);
    ">
        <div style="
            font-size: 38px;
            font-weight: bold;
            margin-bottom: 28px;
            padding-bottom: 16px;
            border-bottom: 3px solid #e94560;
            color: #e94560;
        ">📋 内容总结</div>

        <div style="
            font-size: 32px;
            line-height: 2;
            word-wrap: break-word;
            color: #f0f0f0;
        ">{{ summary_html }}</div>
    </div>

    <!-- 热门评论区域 -->
    {% if comments_html %}
    <div style="
        background: rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 36px;
        margin-bottom: 32px;
        border: 2px solid rgba(255,255,255,0.1);
    ">
        <div style="
            font-size: 38px;
            font-weight: bold;
            margin-bottom: 28px;
            padding-bottom: 16px;
            border-bottom: 3px solid #5b86e5;
            color: #5b86e5;
        ">💬 热门评论</div>

        <div style="
            font-size: 30px;
            line-height: 1.9;
            word-wrap: break-word;
            color: #d0d0d0;
        ">{{ comments_html }}</div>
    </div>
    {% endif %}

    <!-- 底部统计区域 -->
    <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 28px;
        color: rgba(255,255,255,0.8);
        padding: 20px 8px;
        border-top: 2px solid rgba(255,255,255,0.1);
    ">
        <span style="
            background: rgba(233,69,96,0.2);
            padding: 14px 28px;
            border-radius: 30px;
            color: #ff6b6b;
        ">📊 字幕：{{ subtitle_length }} 字</span>
        <span style="
            background: rgba(233,69,96,0.2);
            padding: 14px 28px;
            border-radius: 30px;
            color: #ff6b6b;
        ">📝 总结：{{ summary_length }} 字</span>
    </div>
</div>
'''


@register(
    "astrbot_plugin_bilibili_summary",
    "VincenttHo",
    "Bilibili视频字幕总结插件。自动检测消息中的B站视频链接，获取字幕和热门评论并生成内容总结。支持无字幕视频的音频转文字功能",
    "1.4.0",
    "https://github.com/VincenttHo/astrbot_plugin_bilibili_summary"
)
class BilibiliSummaryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config: AstrBotConfig = config
        
        # 配置参数
        self.openai_api_key: str = self.config.get("openai_api_key", "")
        self.openai_api_url: str = self.config.get("openai_api_url", "https://api.openai.com/v1/chat/completions")
        self.openai_model: str = self.config.get("openai_model", "gpt-3.5-turbo")
        self.bilibili_cookie_text: str = self.config.get("bilibili_cookie", "")
        self.bilibili_cookie_str: str = self._parse_netscape_cookies(self.bilibili_cookie_text)
        self.request_interval: float = self.config.get("request_interval", 2.0)
        self.max_subtitle_length: int = self.config.get("max_subtitle_length", 8000)
        self.summary_prompt: str = self.config.get("summary_prompt",
            "请根据以下视频字幕和简介，生成一个详细完整的视频内容总结。总结应该包含视频的主要内容、关键信息和要点，尽可能详细。请用中文回答。")

        # 音频转文字配置
        self.enable_audio_transcription: bool = self.config.get("enable_audio_transcription", True)
        self.audio_extract_duration: int = self.config.get("audio_extract_duration", 300)
        self.whisper_api_key: str = self.config.get("whisper_api_key", "")
        self.whisper_api_url: str = self.config.get("whisper_api_url", "https://api.openai.com/v1/audio/transcriptions")
        self.whisper_model: str = self.config.get("whisper_model", "whisper-1")
        self.audio_language: str = self.config.get("audio_language", "zh")
        
        # 验证配置
        if not self.openai_api_key:
            logger.warning("Bilibili Summary插件: 未配置OpenAI API密钥")
        if not self.bilibili_cookie_str:
            logger.warning("Bilibili Summary插件: 未配置Bilibili Cookie，可能无法获取字幕")
            
        # 初始化音频服务
        self.audio_service = AudioService(
            whisper_api_key=self.whisper_api_key,
            whisper_api_url=self.whisper_api_url,
            whisper_model=self.whisper_model,
            audio_language=self.audio_language
        )

        logger.info("视频总结插件: 初始化完成，支持Bilibili视频总结")
        
        # wbi签名相关缓存
        self._wbi_keys_cache = None
        self._wbi_keys_cache_time = 0
        self._wbi_keys_cache_ttl = 3600  # 缓存1小时

    @staticmethod
    def _parse_netscape_cookies(cookie_text: str) -> str:
        """解析 Netscape 格式的 Cookie 文本，提取 bilibili.com 域名的 cookie

        Netscape 格式每行：domain \\t flag \\t path \\t secure \\t expiration \\t name \\t value
        返回 'name1=value1; name2=value2' 格式的 Cookie 字符串
        """
        if not cookie_text or not cookie_text.strip():
            return ""

        cookies = []
        for line in cookie_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # #HttpOnly_ 是 Netscape cookie 的合法前缀，不能当注释跳过
            if line.startswith('#HttpOnly_'):
                line = line[len('#HttpOnly_'):]
            elif line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) < 7:
                continue
            domain = parts[0]
            name = parts[5]
            value = parts[6]
            if 'bilibili.com' in domain:
                cookies.append(f"{name}={value}")

        cookie_str = '; '.join(cookies)
        if cookie_str:
            logger.info(f"成功解析 {len(cookies)} 个 Bilibili Cookie")
        return cookie_str

    # wbi签名混淆表
    WBI_MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]
    
    def _get_mixin_key(self, orig: str) -> str:
        """对 imgKey 和 subKey 进行字符顺序打乱编码"""
        return reduce(lambda s, i: s + orig[i], self.WBI_MIXIN_KEY_ENC_TAB, '')[:32]
    
    async def _get_wbi_keys(self) -> tuple:
        """获取最新的 img_key 和 sub_key"""
        # 检查缓存是否有效
        current_time = time.time()
        if self._wbi_keys_cache and (current_time - self._wbi_keys_cache_time) < self._wbi_keys_cache_ttl:
            return self._wbi_keys_cache
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        
        if self.bilibili_cookie_str:
            headers['Cookie'] = self.bilibili_cookie_str

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.bilibili.com/x/web-interface/nav', headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # wbi_img 在未登录(code=-101)时也会返回，始终尝试提取
                        wbi_img = data.get('data', {}).get('wbi_img', {})
                        img_url = wbi_img.get('img_url', '')
                        sub_url = wbi_img.get('sub_url', '')

                        # 从URL中提取key
                        img_key = img_url.rsplit('/', 1)[-1].split('.')[0] if img_url else ''
                        sub_key = sub_url.rsplit('/', 1)[-1].split('.')[0] if sub_url else ''

                        if img_key and sub_key:
                            self._wbi_keys_cache = (img_key, sub_key)
                            self._wbi_keys_cache_time = current_time
                            logger.info("成功获取wbi keys")
                            return (img_key, sub_key)
                        else:
                            logger.warning(f"获取wbi keys失败: 响应中缺少wbi_img数据")
                    else:
                        logger.warning(f"获取wbi keys HTTP失败: {response.status}")
        except Exception as e:
            logger.error(f"获取wbi keys异常: {type(e).__name__}: {str(e)}")
        
        # 如果获取失败，返回空字符串
        return ('', '')
    
    def _encode_wbi(self, params: dict, img_key: str, sub_key: str) -> dict:
        """为请求参数进行 wbi 签名"""
        mixin_key = self._get_mixin_key(img_key + sub_key)
        curr_time = round(time.time())
        params['wts'] = curr_time
        
        # 按照 key 重排参数，并过滤非法字符
        params = dict(sorted(params.items()))
        # 过滤 value 中的 "!'()*" 字符
        params = {
            k: ''.join([char for char in str(v) if char not in "!'()*"])
            for k, v in params.items()
        }
        
        query = urlencode(params)
        wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
        params['w_rid'] = wbi_sign
        
        return params
    
    async def _get_signed_params(self, params: dict) -> dict:
        """获取带wbi签名的参数"""
        img_key, sub_key = await self._get_wbi_keys()
        if img_key and sub_key:
            return self._encode_wbi(params, img_key, sub_key)
        return params
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            self.config.save_config()
            logger.info("配置保存成功")
        except Exception as e:
            logger.error(f"保存配置失败: {type(e).__name__}: {str(e)}")
    
    def _format_summary_html(self, summary: str) -> str:
        """将总结文本格式化为带样式的HTML

        识别并高亮：
        - Markdown标题（# ## ### ####）
        - 数字序号开头的段落（如 1. 2. 3.）
        - 星号包围的重点内容（如 **重点**）
        - 破折号或横杠开头的列表项
        - 冒号结尾的标题行
        """
        import html
        import re

        # 先进行HTML转义
        summary = html.escape(summary)

        lines = summary.split('\n')
        formatted_lines = []

        # Markdown标题级别对应的样式
        heading_styles = {
            1: 'font-size: 40px; font-weight: bold; color: #ff6b6b; margin: 32px 0 16px 0; padding-bottom: 10px; border-bottom: 3px solid #e94560;',
            2: 'font-size: 38px; font-weight: bold; color: #ff6b6b; margin: 28px 0 14px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(233,69,96,0.4);',
            3: 'font-size: 36px; font-weight: bold; color: #ff8a80; margin: 24px 0 12px 0;',
            4: 'font-size: 34px; font-weight: bold; color: #ffab91; margin: 20px 0 10px 0;',
        }

        for line in lines:
            line = line.strip()

            if not line:
                formatted_lines.append('<div style="height: 16px;"></div>')
                continue

            # 处理 **文本** 格式 - 高亮显示
            line = re.sub(
                r'\*\*([^*]+)\*\*',
                r'<span style="background: linear-gradient(135deg, #e94560, #ff6b6b); color: white; padding: 4px 12px; border-radius: 8px; font-weight: bold;">\1</span>',
                line
            )

            # 处理 Markdown 标题（#### > ### > ## > #）
            heading_match = re.match(r'^(#{1,4})\s+(.+)', line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2)
                style = heading_styles.get(level, heading_styles[4])
                line = f'<div style="{style}">{content}</div>'
            # 处理数字序号开头的段落（如 1. 2. 3.）
            elif re.match(r'^(\d+)\.\s*(.+)', line):
                match = re.match(r'^(\d+)\.\s*(.+)', line)
                num = match.group(1)
                content = match.group(2)
                line = f'''<div style="
                    display: flex;
                    align-items: flex-start;
                    margin: 20px 0;
                ">
                    <span style="
                        background: linear-gradient(135deg, #e94560, #ff6b6b);
                        color: white;
                        min-width: 44px;
                        height: 44px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-weight: bold;
                        font-size: 28px;
                        margin-right: 18px;
                        flex-shrink: 0;
                        box-shadow: 0 3px 6px rgba(233,69,96,0.4);
                    ">{num}</span>
                    <span style="flex: 1; padding-top: 4px;">{content}</span>
                </div>'''
            # 处理破折号或横杠开头的列表项
            elif re.match(r'^[-–—•]\s*(.+)', line):
                match = re.match(r'^[-–—•]\s*(.+)', line)
                content = match.group(1)
                line = f'''<div style="
                    display: flex;
                    align-items: flex-start;
                    margin: 14px 0;
                    padding-left: 14px;
                ">
                    <span style="
                        color: #e94560;
                        margin-right: 14px;
                        font-size: 28px;
                        line-height: 1.4;
                    ">▸</span>
                    <span style="flex: 1;">{content}</span>
                </div>'''
            # 处理冒号结尾的标题行
            elif line.endswith('：') or line.endswith(':'):
                line = f'''<div style="
                    font-weight: bold;
                    color: #ff6b6b;
                    font-size: 36px;
                    margin: 28px 0 14px 0;
                    padding-bottom: 8px;
                    border-bottom: 2px dashed rgba(233,69,96,0.3);
                ">{line}</div>'''
            else:
                line = f'<div style="margin: 14px 0; text-indent: 0;">{line}</div>'

            formatted_lines.append(line)

        return ''.join(formatted_lines)

    def _format_comments_html(self, comments: str) -> str:
        """将评论文本格式化为带样式的HTML，每条评论独立展示"""
        import html as html_module

        lines = comments.split('\n')
        formatted = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            escaped = html_module.escape(line)
            formatted.append(f'''<div style="
                margin: 14px 0;
                padding: 16px 22px;
                background: rgba(91,134,229,0.1);
                border-left: 4px solid #5b86e5;
                border-radius: 0 12px 12px 0;
                line-height: 1.8;
            ">{escaped}</div>''')

        return ''.join(formatted)

    async def render_summary_card(self, platform_icon: str, title: str, owner: str,
                                   duration: str, views: str, likes: str,
                                   summary: str, subtitle_length: int,
                                   comments: str = "") -> Optional[str]:
        """渲染视频总结卡片为图片

        Args:
            platform_icon: 平台图标（📺 或 🎬）
            title: 视频标题
            owner: UP主/频道名称
            duration: 时长字符串
            views: 播放量字符串
            likes: 点赞数字符串
            summary: 总结内容
            subtitle_length: 字幕字数
            comments: 热门评论文本

        Returns:
            图片URL或路径，失败返回None
        """
        try:
            # 格式化总结内容为带样式的HTML
            summary_html = self._format_summary_html(summary)

            # 格式化评论为HTML
            comments_html = ""
            if comments:
                comments_html = self._format_comments_html(comments)

            data = {
                "platform_icon": platform_icon,
                "title": title,
                "owner": owner,
                "duration": duration,
                "views": views,
                "likes": likes,
                "summary_html": summary_html,
                "subtitle_length": subtitle_length,
                "summary_length": len(summary),
                "comments_html": comments_html
            }
            
            image_url = await self.html_render(VIDEO_SUMMARY_TEMPLATE, data)
            logger.info(f"成功渲染视频总结卡片")
            return image_url
        except Exception as e:
            logger.error(f"渲染视频总结卡片失败: {type(e).__name__}: {str(e)}")
            return None

    def extract_video_links_from_message(self, event: AstrMessageEvent) -> List[str]:
        """从消息链中提取所有可能的bilibili链接"""
        bilibili_links = []

        # 从消息链中提取链接
        for component in event.message_obj.message:
            if isinstance(component, Comp.Plain):
                text = component.text
                bilibili_extracted = self.extract_links_from_text(text)
                bilibili_links.extend(bilibili_extracted)

            elif isinstance(component, Comp.Reply):
                logger.info(f"检测到引用消息: {component}")
                b_links = self.extract_from_reply(event, component)
                bilibili_links.extend(b_links)

            elif isinstance(component, Comp.Forward):
                logger.info(f"检测到转发消息: {component}")
                b_links = self.extract_from_forward_message(component)
                bilibili_links.extend(b_links)

            elif hasattr(component, 'type') and component.type == 'Json':
                logger.info(f"检测到JSON消息组件: {component}")
                b_links = self.extract_from_json_component(component)
                bilibili_links.extend(b_links)

        return bilibili_links

    def extract_links_from_text(self, text: str) -> List[str]:
        """从文本中提取bilibili链接"""
        links = []
        url_patterns = [
            r'https?://(?:www\.)?bilibili\.com/video/[^\s\'"<>]+',
            r'https?://m\.bilibili\.com/video/[^\s\'"<>]+',
            r'https?://b23\.tv/[^\s\'"<>]+',
            r'BV[a-zA-Z0-9]{10}',
            r'av\d+',
        ]

        for pattern in url_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            links.extend(matches)

        return links

    def extract_from_json_component(self, json_component) -> List[str]:
        """从JSON消息组件中提取bilibili链接"""
        bilibili_links = []

        try:
            # 获取JSON数据
            json_data = None
            if hasattr(json_component, 'data'):
                if isinstance(json_component.data, str):
                    json_data = json.loads(json_component.data)
                else:
                    json_data = json_component.data

            if json_data:
                # 递归搜索JSON中的所有字符串值
                def search_json_for_links(obj):
                    found_links = []
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str):
                                b_links = self.extract_links_from_text(value)
                                found_links.extend(b_links)
                            elif isinstance(value, (dict, list)):
                                found_links.extend(search_json_for_links(value))
                    elif isinstance(obj, list):
                        for item in obj:
                            if isinstance(item, str):
                                b_links = self.extract_links_from_text(item)
                                found_links.extend(b_links)
                            elif isinstance(item, (dict, list)):
                                found_links.extend(search_json_for_links(item))
                    return found_links

                bilibili_links.extend(search_json_for_links(json_data))

                # 特别处理bilibili小程序卡片
                if isinstance(json_data, dict):
                    meta = json_data.get('meta', {})
                    if meta:
                        detail = meta.get('detail_1', {})
                        if detail:
                            title = detail.get('title', '')
                            if '哔哩哔哩' in title or 'bilibili' in title.lower():
                                qqdocurl = detail.get('qqdocurl', '')
                                if qqdocurl:
                                    bilibili_links.extend(self.extract_links_from_text(qqdocurl))
                                url = detail.get('url', '')
                                if url:
                                    bilibili_links.extend(self.extract_links_from_text(url))

                logger.info(f"从JSON组件中提取到Bilibili链接: {bilibili_links}")

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.warning(f"解析JSON消息组件失败: {type(e).__name__}: {str(e)}")
        except Exception as e:
            logger.error(f"解析JSON消息组件时发生未预期错误: {type(e).__name__}: {str(e)}")

        return bilibili_links

    def extract_from_reply(self, event: AstrMessageEvent, reply_component) -> List[str]:
        """从引用消息中提取bilibili链接"""
        bilibili_links = []

        try:
            logger.info(f"引用消息详情: {reply_component}")

            if hasattr(reply_component, 'text') and reply_component.text:
                text = reply_component.text
                bilibili_links.extend(self.extract_links_from_text(text))

            if hasattr(reply_component, 'chain') and reply_component.chain:
                for sub_component in reply_component.chain:
                    if isinstance(sub_component, Comp.Plain):
                        text = sub_component.text
                        bilibili_links.extend(self.extract_links_from_text(text))
                    elif hasattr(sub_component, 'type') and sub_component.type == 'Json':
                        b_links = self.extract_from_json_component(sub_component)
                        bilibili_links.extend(b_links)

            elif hasattr(reply_component, 'message') and reply_component.message:
                for sub_component in reply_component.message:
                    if isinstance(sub_component, Comp.Plain):
                        text = sub_component.text
                        bilibili_links.extend(self.extract_links_from_text(text))
                    elif hasattr(sub_component, 'type') and sub_component.type == 'Json':
                        b_links = self.extract_from_json_component(sub_component)
                        bilibili_links.extend(b_links)

        except (AttributeError, KeyError) as e:
            logger.warning(f"解析引用消息失败: {type(e).__name__}: {str(e)}")
        except Exception as e:
            logger.error(f"解析引用消息时发生未预期错误: {type(e).__name__}: {str(e)}")

        return bilibili_links

    def extract_from_forward_message(self, forward_component) -> List[str]:
        """从转发消息中提取bilibili链接"""
        bilibili_links = []

        try:
            # 转发消息可能包含多种格式的内容
            logger.info(f"转发消息结构: {forward_component}")
            logger.info(f"转发消息类型: {type(forward_component)}")
            logger.info(f"转发消息属性: {dir(forward_component)}")

            # 尝试从转发消息的各种属性中提取链接
            content_sources = []

            # 处理常见的属性
            if hasattr(forward_component, 'content'):
                content = forward_component.content
                if content:
                    if isinstance(content, str):
                        content_sources.append(content)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, str):
                                content_sources.append(item)
                            elif isinstance(item, Comp.Plain):
                                content_sources.append(item.text)
                            elif hasattr(item, 'text'):
                                content_sources.append(str(item.text))
                    else:
                        content_sources.append(str(content))
                        
            if hasattr(forward_component, 'text') and forward_component.text:
                content_sources.append(str(forward_component.text))
            if hasattr(forward_component, 'title') and forward_component.title:
                content_sources.append(str(forward_component.title))
            if hasattr(forward_component, 'summary') and forward_component.summary:
                content_sources.append(str(forward_component.summary))
            if hasattr(forward_component, 'desc') and forward_component.desc:
                content_sources.append(str(forward_component.desc))
            if hasattr(forward_component, 'description') and forward_component.description:
                content_sources.append(str(forward_component.description))

            # 如果转发消息包含节点列表
            if hasattr(forward_component, 'nodes') and forward_component.nodes:
                for node in forward_component.nodes:
                    try:
                        if hasattr(node, 'content') and node.content:
                            if isinstance(node.content, list):
                                for content_item in node.content:
                                    if isinstance(content_item, Comp.Plain):
                                        content_sources.append(content_item.text)
                                    elif hasattr(content_item, 'text'):
                                        content_sources.append(str(content_item.text))
                            elif isinstance(node.content, str):
                                content_sources.append(node.content)
                        if hasattr(node, 'message') and node.message:
                            if isinstance(node.message, list):
                                for msg_item in node.message:
                                    if isinstance(msg_item, Comp.Plain):
                                        content_sources.append(msg_item.text)
                                    elif hasattr(msg_item, 'text'):
                                        content_sources.append(str(msg_item.text))
                    except Exception as node_e:
                        logger.warning(f"解析转发节点失败: {type(node_e).__name__}: {str(node_e)}")
                        continue
            
            # 如果转发消息包含message列表
            if hasattr(forward_component, 'message') and forward_component.message:
                if isinstance(forward_component.message, list):
                    for msg_item in forward_component.message:
                        if isinstance(msg_item, Comp.Plain):
                            content_sources.append(msg_item.text)
                        elif hasattr(msg_item, 'text'):
                            content_sources.append(str(msg_item.text))

            # 尝试解析data属性（可能包含JSON数据）
            if hasattr(forward_component, 'data') and forward_component.data:
                try:
                    data = forward_component.data
                    if isinstance(data, str):
                        try:
                            json_data = json.loads(data)
                            if isinstance(json_data, dict):
                                def extract_strings(obj):
                                    strings = []
                                    if isinstance(obj, dict):
                                        for v in obj.values():
                                            strings.extend(extract_strings(v))
                                    elif isinstance(obj, list):
                                        for item in obj:
                                            strings.extend(extract_strings(item))
                                    elif isinstance(obj, str):
                                        strings.append(obj)
                                    return strings
                                content_sources.extend(extract_strings(json_data))
                        except json.JSONDecodeError:
                            content_sources.append(data)
                    elif isinstance(data, dict):
                        content_sources.append(str(data))
                except Exception as data_e:
                    logger.warning(f"解析转发消息data属性失败: {type(data_e).__name__}: {str(data_e)}")

            logger.info(f"从转发消息中提取到 {len(content_sources)} 个内容源")

            # 在所有内容中查找bilibili链接
            for content in content_sources:
                if content:
                    bilibili_links.extend(self.extract_links_from_text(content))

        except (AttributeError, KeyError) as e:
            logger.warning(f"解析转发消息失败: {type(e).__name__}: {str(e)}")
        except Exception as e:
            logger.error(f"解析转发消息时发生未预期错误: {type(e).__name__}: {str(e)}")

        # 去重
        bilibili_links = list(dict.fromkeys(bilibili_links))

        logger.info(f"转发消息提取结果 - Bilibili: {bilibili_links}")

        return bilibili_links

    def parse_bilibili_url(self, input_str: str) -> Optional[str]:
        """解析bilibili视频链接，提取BV号或AV号"""
        if not input_str or not input_str.strip():
            return None

        input_str = input_str.strip()

        # 如果是纯BV号或AV号
        if re.match(r'^BV[a-zA-Z0-9]{10}$', input_str):
            return input_str
        if re.match(r'^[a-zA-Z0-9]{10}$', input_str):
            return 'BV' + input_str
        if re.match(r'^av\d+$', input_str, re.IGNORECASE):
            return input_str.lower()
        if re.match(r'^\d+$', input_str):
            return 'av' + input_str

        # 如果是URL链接
        if 'bilibili.com' in input_str or 'b23.tv' in input_str:
            try:
                parsed = urlparse(input_str)

                # 处理b23.tv短链接 - 需要重定向获取真实链接
                if 'b23.tv' in parsed.netloc:
                    return input_str  # 返回原链接，后续处理重定向

                # 处理标准bilibili链接
                if 'bilibili.com' in parsed.netloc:
                    path = parsed.path

                    # 匹配 /video/BVxxxxx 或 /video/avxxxxx
                    video_match = re.search(r'/video/(BV[a-zA-Z0-9]{10}|av\d+)', path)
                    if video_match:
                        video_id = video_match.group(1)
                        if video_id.startswith('BV'):
                            return video_id
                        elif video_id.startswith('av'):
                            return video_id.lower()

                    # 处理查询参数中的bvid
                    query_params = parse_qs(parsed.query)
                    if 'bvid' in query_params:
                        bvid = query_params['bvid'][0]
                        if re.match(r'^BV[a-zA-Z0-9]{10}$', bvid):
                            return bvid

            except (ValueError, KeyError, IndexError) as e:
                logger.warning(f"解析URL失败: {type(e).__name__}: {str(e)}")
            except Exception as e:
                logger.error(f"解析URL时发生未预期错误: {type(e).__name__}: {str(e)}")

        return None

    async def resolve_short_url(self, short_url: str) -> Optional[str]:
        """解析b23.tv短链接"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(short_url, headers=headers, allow_redirects=False) as response:
                    if response.status in [301, 302, 303, 307, 308]:
                        location = response.headers.get('Location')
                        if location:
                            return self.parse_bilibili_url(location)

            return None
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"解析短链接时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    async def convert_av_to_bv(self, av_id: str) -> Optional[str]:
        """通过AV号获取BV号"""
        try:
            # 提取AV号中的数字
            av_num = re.search(r'av(\d+)', av_id, re.IGNORECASE)
            if not av_num:
                return None

            aid = av_num.group(1)
            url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            bvid = data.get('data', {}).get('bvid')
                            if bvid:
                                logger.info(f"成功转换AV号到BV号: {av_id} -> {bvid}")
                                return bvid

            await asyncio.sleep(self.request_interval)
            return None
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据解析失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"AV号转换时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def video_summary(self, event: AstrMessageEvent):
        """自动检测并总结Bilibili视频

        当检测到视频链接时，自动触发总结功能并阻止消息传递给AI聊天处理器
        """

        # 从当前消息中提取链接
        bilibili_links = self.extract_video_links_from_message(event)

        # 如果没有找到任何视频链接，直接返回，让消息继续传递给其他处理器
        if not bilibili_links:
            return

        # 检测到视频链接，阻止消息继续传递给AI聊天等其他处理器
        event.stop_event()

        # 检查配置
        if not self.openai_api_key:
            yield event.plain_result("❌ 未配置OpenAI API密钥，请联系管理员配置插件")
            return

        # 处理Bilibili视频
        video_input = bilibili_links[0]
        logger.info(f"自动检测到bilibili链接: {video_input}")
        async for result in self.process_bilibili_video(event, video_input):
            yield result
    
    async def process_bilibili_video(self, event: AstrMessageEvent, video_input: str):
        """处理Bilibili视频"""
        # 解析输入的视频标识
        video_id = self.parse_bilibili_url(video_input.strip())

        # 如果是短链接，需要先解析
        if video_input.strip().startswith('https://b23.tv/'):
            video_id = await self.resolve_short_url(video_input.strip())

        if not video_id:
            yield event.plain_result("❌ 无法识别的Bilibili视频链接或ID格式，请检查后重试")
            return

        try:
            # 获取视频基本信息
            video_info = await self.get_video_info(video_id)
            if not video_info:
                yield event.plain_result("❌ 获取视频信息失败，请检查BV号是否正确")
                return

            aid = video_info.get('aid')
            cid = video_info.get('cid')
            title = video_info.get('title', '未知标题')
            desc = video_info.get('desc', '')
            pic_url = video_info.get('pic', '')
            owner = video_info.get('owner', '未知UP主')
            view_count = video_info.get('view', 0)
            like_count = video_info.get('like', 0)
            duration = video_info.get('duration', 0)

            if not aid or not cid:
                yield event.plain_result("❌ 无法获取视频的aid或cid")
                return
            
            # 格式化时长
            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes:02d}:{seconds:02d}" if duration > 0 else "--:--"
            
            # 格式化播放量和点赞数
            def format_count(count):
                if count >= 100000000:  # 亿
                    return f"{count / 100000000:.1f}亿"
                elif count >= 10000:  # 万
                    return f"{count / 10000:.1f}万"
                else:
                    return str(count)
            
            view_str = format_count(view_count)
            like_str = format_count(like_count)
            
            # 静默模式：不发送中间状态消息
            logger.info(f"正在处理B站视频: {title}")

            # 获取字幕
            subtitle_text = await self.get_subtitle(aid, cid)
            subtitle_length = 0  # 记录字幕字数
            
            # 如果没有字幕且启用了音频转文字功能
            if not subtitle_text and self.enable_audio_transcription:
                logger.info("未找到字幕，尝试使用音频转文字功能")
                
                # 尝试最多2次获取和提取音频
                audio_path = None
                for attempt in range(2):
                    # 获取视频下载地址（每次都重新获取，因为URL可能过期）
                    video_url = await self.get_video_download_url(aid, cid)
                    if not video_url:
                        yield event.plain_result("❌ 无法获取视频下载地址")
                        return
                    
                    # 提取音频
                    audio_path = await self.audio_service.extract_audio_from_video(video_url, self.audio_extract_duration)
                    if audio_path:
                        break
                    
                    if attempt == 0:
                        logger.info(f"第{attempt + 1}次尝试失败，等待2秒后重试...")
                        await asyncio.sleep(2)
                
                if not audio_path:
                    yield event.plain_result("❌ 音频提取失败。可能原因：\n1. B站视频URL已过期\n2. 网络连接问题\n3. ffmpeg未正确安装\n\n建议：稍后重试或检查有无字幕的视频")
                    return
                
                # 转换为文字
                subtitle_text = await self.audio_service.transcribe_audio(audio_path, self.openai_api_key)
                if not subtitle_text:
                    yield event.plain_result("❌ 语音识别失败，请检查Whisper API配置")
                    return
                
                logger.info(f"音频转文字成功，文本长度: {len(subtitle_text)}字符")
            elif not subtitle_text:
                yield event.plain_result("❌ 未找到可用的字幕，且音频转文字功能未启用")
                return
            
            # 记录字幕字数
            subtitle_length = len(subtitle_text)

            # 获取热门评论
            comments_text = await self.get_comments(aid)
            if comments_text:
                logger.info("已获取热门评论，将纳入总结")

            # 生成总结
            summary = await self.generate_summary(title, desc, subtitle_text, comments=comments_text or "")
            if summary:
                logger.info(f"总结生成成功，长度: {len(summary)}字符")
                
                # 尝试渲染为图片
                image_url = await self.render_summary_card(
                    platform_icon="📺",
                    title=title,
                    owner=owner,
                    duration=duration_str,
                    views=view_str,
                    likes=like_str,
                    summary=summary,
                    subtitle_length=subtitle_length,
                    comments=comments_text or ""
                )
                
                if image_url:
                    # 成功渲染为图片
                    yield event.image_result(image_url)
                else:
                    # 渲染失败，回退到纯文本输出
                    logger.warning("图片渲染失败，使用纯文本输出")
                    output_parts = [
                        f"📺 【{title}】",
                        f"",
                        f"👤 UP主：{owner}",
                        f"⏱️ 时长：{duration_str}  |  👀 {view_str}  |  👍 {like_str}",
                        f"",
                        f"{'─' * 30}",
                        f"📋 内容总结",
                        f"{'─' * 30}",
                        f"",
                        summary,
                    ]
                    if comments_text:
                        output_parts.extend([
                            f"",
                            f"{'─' * 30}",
                            f"💬 热门评论",
                            f"{'─' * 30}",
                            f"",
                            comments_text,
                        ])
                    output_parts.extend([
                        f"",
                        f"{'─' * 30}",
                        f"📊 字幕：{subtitle_length} 字  |  总结：{len(summary)} 字"
                    ])
                    yield event.plain_result("\n".join(output_parts))
            else:
                yield event.plain_result("❌ 生成总结失败")

        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            yield event.plain_result("❌ 网络请求失败，请检查网络连接后重试")
        except (ValueError, KeyError) as e:
            logger.error(f"数据解析失败: {type(e).__name__}: {str(e)}")
            yield event.plain_result("❌ 数据解析失败，可能是视频信息格式异常")
        except OSError as e:
            logger.error(f"文件操作失败: {type(e).__name__}: {str(e)}")
            yield event.plain_result("❌ 文件操作失败，请检查系统权限和磁盘空间")
        except Exception as e:
            logger.error(f"处理请求时发生未预期错误: {type(e).__name__}: {str(e)}")
            yield event.plain_result(f"❌ 处理请求时发生错误，请联系管理员")

    async def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """获取视频基本信息"""
        # 根据视频ID类型构建URL
        if video_id.startswith('av'):
            # AV号
            av_match = re.search(r'av(\d+)', video_id, re.IGNORECASE)
            if not av_match:
                logger.error(f"无效的AV号格式: {video_id}")
                return None
            aid = av_match.group(1)
            url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
        else:
            # BV号
            url = f"https://api.bilibili.com/x/web-interface/view?bvid={video_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        code = data.get('code')
                        if code == 0:
                            video_data = data.get('data', {})
                            pages = video_data.get('pages', [])
                            if pages:
                                # 获取封面图URL
                                pic_url = video_data.get('pic', '')
                                # 获取UP主信息
                                owner = video_data.get('owner', {})
                                owner_name = owner.get('name', '未知UP主')
                                # 获取视频统计信息
                                stat = video_data.get('stat', {})
                                view_count = stat.get('view', 0)
                                like_count = stat.get('like', 0)
                                
                                result = {
                                    'aid': video_data.get('aid'),
                                    'cid': pages[0].get('cid'),  # 取第一个分P
                                    'title': video_data.get('title'),
                                    'desc': video_data.get('desc'),
                                    'pic': pic_url,
                                    'owner': owner_name,
                                    'view': view_count,
                                    'like': like_count,
                                    'duration': video_data.get('duration', 0)
                                }
                                logger.info(f"成功获取视频信息: {result['title']}")
                                return result
                        else:
                            message = data.get('message', '未知错误')
                            logger.warning(f"Bilibili API返回错误: code={code}, message={message}")
                    else:
                        logger.warning(f"HTTP请求失败: status={response.status}")

            await asyncio.sleep(self.request_interval)
            return None
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据解析失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取视频信息时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    async def get_subtitle(self, aid: int, cid: int) -> Optional[str]:
        """获取视频字幕（带wbi签名）"""
        # 构建请求参数并添加wbi签名
        params = {
            'aid': aid,
            'cid': cid
        }
        signed_params = await self._get_signed_params(params)
        
        # 构建带签名的URL
        base_url = "https://api.bilibili.com/x/player/wbi/v2"
        url = f"{base_url}?{urlencode(signed_params)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com'
        }

        # 如果有SESSDATA，添加到Cookie中
        if self.bilibili_cookie_str:
            headers['Cookie'] = self.bilibili_cookie_str

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    logger.info(f"字幕API响应状态: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        code = data.get('code')
                        if code == 0:
                            subtitle_data = data.get('data', {}).get('subtitle', {})
                            subtitles = subtitle_data.get('subtitles', [])

                            if not subtitles:
                                # 检查是否需要登录
                                need_login = data.get('data', {}).get('need_login_subtitle', False)
                                if need_login:
                                    logger.warning("获取字幕需要登录，请检查SESSDATA配置")
                                else:
                                    logger.warning("该视频没有可用的字幕")
                                return None

                            # 优先选择中文字幕
                            selected_subtitle = None
                            for subtitle in subtitles:
                                lan_doc = subtitle.get('lan_doc', '')
                                if '中文' in lan_doc:
                                    selected_subtitle = subtitle
                                    logger.info(f"选择中文字幕: {lan_doc}")
                                    break

                            # 如果没有中文字幕，选择第一个
                            if not selected_subtitle and subtitles:
                                selected_subtitle = subtitles[0]
                                lan_doc = selected_subtitle.get('lan_doc', '未知语言')
                                logger.info(f"未找到中文字幕，选择: {lan_doc}")

                            if selected_subtitle:
                                subtitle_url = selected_subtitle.get('subtitle_url')
                                if subtitle_url:
                                    # 确保URL是完整的
                                    if subtitle_url.startswith('//'):
                                        subtitle_url = 'https:' + subtitle_url
                                    elif not subtitle_url.startswith('http'):
                                        subtitle_url = 'https://' + subtitle_url

                                    return await self.download_subtitle(subtitle_url)
                        else:
                            message = data.get('message', '未知错误')
                            logger.warning(f"获取字幕API返回错误: code={code}, message={message}")
                    else:
                        logger.warning(f"获取字幕HTTP请求失败: status={response.status}")

            await asyncio.sleep(self.request_interval)
            return None
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据解析失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取字幕时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    async def download_subtitle(self, subtitle_url: str) -> Optional[str]:
        """下载字幕文件并提取文本"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(subtitle_url, headers=headers) as response:
                    if response.status == 200:
                        subtitle_data = await response.json()
                        body = subtitle_data.get('body', [])

                        if not body:
                            logger.warning("字幕文件为空")
                            return None

                        # 提取所有字幕文本
                        subtitle_texts = []
                        for item in body:
                            content = item.get('content', '').strip()
                            if content:
                                subtitle_texts.append(content)

                        if not subtitle_texts:
                            logger.warning("字幕内容为空")
                            return None

                        full_text = ' '.join(subtitle_texts)
                        original_length = len(full_text)

                        # 限制长度
                        if original_length > self.max_subtitle_length:
                            full_text = full_text[:self.max_subtitle_length] + "..."
                            logger.info(f"字幕文本过长({original_length}字符)，已截断到{self.max_subtitle_length}字符")
                        else:
                            logger.info(f"成功获取字幕文本({original_length}字符)")

                        return full_text
                    else:
                        logger.warning(f"下载字幕HTTP请求失败: status={response.status}")

            await asyncio.sleep(self.request_interval)
            return None
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据解析失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"下载字幕时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    async def get_video_download_url(self, aid: int, cid: int) -> Optional[str]:
        """获取视频下载地址（带wbi签名）"""
        # 构建请求参数并添加wbi签名
        params = {
            'avid': aid,
            'cid': cid,
            'qn': 16,
            'fnval': 16
        }
        signed_params = await self._get_signed_params(params)
        
        # 构建带签名的URL
        base_url = "https://api.bilibili.com/x/player/wbi/playurl"
        url = f"{base_url}?{urlencode(signed_params)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com'
        }
        
        if self.bilibili_cookie_str:
            headers['Cookie'] = self.bilibili_cookie_str
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            data_obj = data.get('data', {})
                            durl = data_obj.get('durl', [])
                            dash = data_obj.get('dash', {})
                            
                            video_url = None
                            if durl and len(durl) > 0:
                                video_url = durl[0].get('url')
                            elif dash:
                                # 如果是dash格式，获取音频流或视频流
                                audio = dash.get('audio', [])
                                video = dash.get('video', [])
                                if audio:
                                    video_url = audio[0].get('baseUrl')
                                elif video:
                                    video_url = video[0].get('baseUrl')
                            
                            if video_url:
                                logger.info(f"成功获取视频下载地址")
                                return video_url
                            else:
                                logger.warning("视频下载地址列表为空")
                        else:
                            logger.warning(f"获取视频地址失败: {data.get('message')}")
                    else:
                        logger.warning(f"HTTP请求失败: {response.status}")
            
            await asyncio.sleep(self.request_interval)
            return None
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据解析失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取视频下载地址时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None


    async def get_comments(self, aid: int) -> Optional[str]:
        """获取视频前20条热门评论"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }

        if self.bilibili_cookie_str:
            headers['Cookie'] = self.bilibili_cookie_str

        params = {
            'type': 1,
            'oid': aid,
            'sort': 2,
            'ps': 20,
            'pn': 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.bilibili.com/x/v2/reply',
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            replies = data.get('data', {}).get('replies', [])
                            if not replies:
                                logger.info("该视频没有评论")
                                return None

                            comments = []
                            for reply in replies[:20]:
                                message = reply.get('content', {}).get('message', '').strip()
                                if message:
                                    comments.append(message)

                            if comments:
                                comment_text = '\n'.join(comments)
                                logger.info(f"成功获取 {len(comments)} 条热门评论")
                                return comment_text
                        else:
                            logger.warning(f"获取评论API返回错误: {data.get('message')}")
                    else:
                        logger.warning(f"获取评论HTTP请求失败: {response.status}")

            await asyncio.sleep(self.request_interval)
            return None
        except aiohttp.ClientError as e:
            logger.error(f"获取评论网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取评论时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    async def generate_summary(self, title: str, desc: str, subtitle_text: str, comments: str = "") -> Optional[str]:
        """使用LLM生成视频总结"""
        # 构建提示词
        content = f"视频标题：{title}\n\n"
        if desc and desc.strip():
            content += f"视频简介：{desc}\n\n"
        content += f"视频字幕：\n{subtitle_text}"
        if comments:
            content += f"\n\n热门评论：\n{comments}"

        messages = [
            {"role": "system", "content": self.summary_prompt},
            {"role": "user", "content": content}
        ]

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.openai_api_key}'
        }

        payload = {
            "model": self.openai_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096  # 增加到4096，确保总结不被截断
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.openai_api_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        choices = data.get('choices', [])
                        if choices:
                            content = choices[0].get('message', {}).get('content', '').strip()
                            if content:
                                logger.info(f"成功生成总结({len(content)}字符)")
                                return content
                            else:
                                logger.warning("LLM返回空内容")
                                return None
                        else:
                            logger.warning("LLM响应中没有choices")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"LLM API请求失败: {response.status} - {error_text}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据解析失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"调用LLM API时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("Bilibili Summary插件: 已卸载")
