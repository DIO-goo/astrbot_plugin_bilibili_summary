import asyncio
import re
import json
import os
import tempfile
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs
import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp


@register(
    "astrbot_plugin_bilibili_summary",
    "VincenttHo",
    "Bilibili视频字幕总结插件，自动检测消息中的B站视频链接并生成内容总结。支持无字幕视频的音频转文字功能",
    "1.2.0",
    "https://github.com/VincenttHo/astrbot_plugin_bilibili_summary"
)
class BilibiliSummaryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 配置参数
        self.openai_api_key = self.config.get("openai_api_key", "")
        self.openai_api_url = self.config.get("openai_api_url", "https://api.openai.com/v1/chat/completions")
        self.openai_model = self.config.get("openai_model", "gpt-3.5-turbo")
        self.bilibili_sessdata = self.config.get("bilibili_sessdata", "")
        self.request_interval = self.config.get("request_interval", 2.0)
        self.max_subtitle_length = self.config.get("max_subtitle_length", 8000)
        self.summary_prompt = self.config.get("summary_prompt",
            "请根据以下视频字幕和简介，生成一个简洁明了的视频内容总结。总结应该包含视频的主要内容、关键信息和要点。请用中文回答。")
        
        # 音频转文字配置
        self.enable_audio_transcription = self.config.get("enable_audio_transcription", True)
        self.audio_extract_duration = self.config.get("audio_extract_duration", 300)
        self.whisper_api_key = self.config.get("whisper_api_key", "")
        self.whisper_api_url = self.config.get("whisper_api_url", "https://api.openai.com/v1/audio/transcriptions")
        self.whisper_model = self.config.get("whisper_model", "whisper-1")
        self.audio_language = self.config.get("audio_language", "zh")
        
        # 验证配置
        if not self.openai_api_key:
            logger.warning("Bilibili Summary插件: 未配置OpenAI API密钥")
        if not self.bilibili_sessdata:
            logger.warning("Bilibili Summary插件: 未配置Bilibili SESSDATA，可能无法获取字幕")
            
        logger.info("Bilibili Summary插件: 初始化完成")

    def extract_bilibili_links_from_message(self, event: AstrMessageEvent) -> List[str]:
        """从消息链中提取所有可能的bilibili链接"""
        links = []

        # 从消息链中提取链接
        for component in event.message_obj.message:
            if isinstance(component, Comp.Plain):
                text = component.text
                # 查找文本中的bilibili链接
                extracted = self.extract_links_from_text(text)
                links.extend(extracted)

            elif isinstance(component, Comp.Reply):
                # 处理引用消息
                logger.info(f"检测到引用消息: {component}")
                reply_links = self.extract_bilibili_from_reply(event, component)
                links.extend(reply_links)

            elif isinstance(component, Comp.Forward):
                # 处理转发消息
                logger.info(f"检测到转发消息: {component}")
                forward_links = self.extract_bilibili_from_forward_message(component)
                links.extend(forward_links)

            elif hasattr(component, 'type') and component.type == 'Json':
                # 处理JSON消息组件（如QQ小程序卡片）
                logger.info(f"检测到JSON消息组件: {component}")
                json_links = self.extract_bilibili_from_json_component(component)
                links.extend(json_links)

        return links

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

    def extract_bilibili_from_json_component(self, json_component) -> List[str]:
        """从JSON消息组件中提取bilibili链接"""
        links = []

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
                                # 在字符串值中查找链接
                                found_links.extend(self.extract_links_from_text(value))
                            elif isinstance(value, (dict, list)):
                                found_links.extend(search_json_for_links(value))
                    elif isinstance(obj, list):
                        for item in obj:
                            if isinstance(item, str):
                                found_links.extend(self.extract_links_from_text(item))
                            elif isinstance(item, (dict, list)):
                                found_links.extend(search_json_for_links(item))
                    return found_links

                links.extend(search_json_for_links(json_data))

                # 特别处理bilibili小程序卡片
                if isinstance(json_data, dict):
                    # 检查是否是bilibili相关的小程序
                    meta = json_data.get('meta', {})
                    if meta:
                        detail = meta.get('detail_1', {})
                        if detail:
                            # 检查应用名称
                            title = detail.get('title', '')
                            if '哔哩哔哩' in title or 'bilibili' in title.lower():
                                # 提取qqdocurl字段中的链接
                                qqdocurl = detail.get('qqdocurl', '')
                                if qqdocurl:
                                    links.extend(self.extract_links_from_text(qqdocurl))

                                # 提取url字段中的链接
                                url = detail.get('url', '')
                                if url:
                                    links.extend(self.extract_links_from_text(url))

                logger.info(f"从JSON组件中提取到链接: {links}")

        except Exception as e:
            logger.warning(f"解析JSON消息组件失败: {str(e)}")

        return links

    def extract_bilibili_from_reply(self, event: AstrMessageEvent, reply_component) -> List[str]:
        """从引用消息中提取bilibili链接"""
        links = []

        try:
            # 引用消息的处理方式取决于平台
            # 对于QQ等平台，引用消息通常包含被引用消息的ID
            logger.info(f"引用消息详情: {reply_component}")

            # 尝试从引用消息的文本内容中提取链接
            if hasattr(reply_component, 'text') and reply_component.text:
                text = reply_component.text
                url_patterns = [
                    r'https?://(?:www\.)?bilibili\.com/video/[^\s]+',
                    r'https?://m\.bilibili\.com/video/[^\s]+',
                    r'https?://b23\.tv/[^\s]+',
                    r'BV[a-zA-Z0-9]{10}',
                    r'av\d+',
                ]

                for pattern in url_patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    links.extend(matches)

            # 如果引用消息本身包含消息链，递归解析
            if hasattr(reply_component, 'chain') and reply_component.chain:
                for sub_component in reply_component.chain:
                    if isinstance(sub_component, Comp.Plain):
                        text = sub_component.text
                        links.extend(self.extract_links_from_text(text))
                    elif hasattr(sub_component, 'type') and sub_component.type == 'Json':
                        # 处理引用消息中的JSON组件
                        json_links = self.extract_bilibili_from_json_component(sub_component)
                        links.extend(json_links)

            # 兼容旧的message属性
            elif hasattr(reply_component, 'message') and reply_component.message:
                for sub_component in reply_component.message:
                    if isinstance(sub_component, Comp.Plain):
                        text = sub_component.text
                        links.extend(self.extract_links_from_text(text))
                    elif hasattr(sub_component, 'type') and sub_component.type == 'Json':
                        json_links = self.extract_bilibili_from_json_component(sub_component)
                        links.extend(json_links)

        except Exception as e:
            logger.warning(f"解析引用消息失败: {str(e)}")

        return links

    def extract_bilibili_from_forward_message(self, forward_component) -> List[str]:
        """从转发消息中提取bilibili链接"""
        links = []

        try:
            # 转发消息可能包含多种格式的内容
            logger.info(f"转发消息结构: {forward_component}")

            # 尝试从转发消息的各种属性中提取链接
            content_sources = []

            if hasattr(forward_component, 'content'):
                content_sources.append(str(forward_component.content))
            if hasattr(forward_component, 'text'):
                content_sources.append(str(forward_component.text))
            if hasattr(forward_component, 'title'):
                content_sources.append(str(forward_component.title))
            if hasattr(forward_component, 'summary'):
                content_sources.append(str(forward_component.summary))

            # 如果转发消息包含节点列表
            if hasattr(forward_component, 'nodes'):
                for node in forward_component.nodes:
                    if hasattr(node, 'content'):
                        for content_item in node.content:
                            if isinstance(content_item, Comp.Plain):
                                content_sources.append(content_item.text)

            # 在所有内容中查找bilibili链接
            for content in content_sources:
                links.extend(self.extract_links_from_text(content))

            # 特殊处理：查找bilibili卡片消息的特征
            # bilibili分享卡片通常包含特定的文本模式
            for content in content_sources:
                # 查找类似 "哔哩哔哩" 或 bilibili 相关的关键词
                if any(keyword in content.lower() for keyword in ['bilibili', '哔哩哔哩', 'b站']):
                    # 在这种内容中更积极地查找BV号
                    additional_links = self.extract_links_from_text(content)
                    links.extend(additional_links)

        except Exception as e:
            logger.warning(f"解析转发消息失败: {str(e)}")

        return links

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

            except Exception as e:
                logger.warning(f"解析URL失败: {str(e)}")

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
        except Exception as e:
            logger.error(f"解析短链接失败: {str(e)}")
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
        except Exception as e:
            logger.error(f"AV号转换失败: {str(e)}")
            return None

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def bilibili_summary(self, event: AstrMessageEvent):
        """自动检测并总结bilibili视频"""
        
        # 从当前消息中提取链接
        extracted_links = self.extract_bilibili_links_from_message(event)
        
        # 如果没有找到bilibili链接，直接返回
        if not extracted_links:
            return
        
        # 使用第一个提取到的链接
        video_input = extracted_links[0]
        logger.info(f"自动检测到bilibili链接: {video_input}")

        # 解析输入的视频标识
        video_id = self.parse_bilibili_url(video_input.strip())

        # 如果是短链接，需要先解析
        if video_input.strip().startswith('https://b23.tv/'):
            video_id = await self.resolve_short_url(video_input.strip())

        if not video_id:
            yield event.plain_result("❌ 无法识别的视频链接或ID格式，请检查后重试")
            return

        # 直接使用video_id，get_video_info方法会处理AV号和BV号
            
        # 检查配置
        if not self.openai_api_key:
            yield event.plain_result("❌ 未配置OpenAI API密钥，请联系管理员配置插件")
            return
            
        yield event.plain_result(f"🔍 正在处理视频 {video_id}，请稍候...")

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
            
            # 构建视频信息卡片
            info_text = (
                f"╔══════════════════════╗\n"
                f"    📺  B站视频解析\n"
                f"╚══════════════════════╝\n\n"
                f"【标题】{title}\n\n"
                f"👤 UP主：{owner}\n"
                f"⏱️  时长：{duration_str}\n"
                f"👀 播放：{view_str}  |  👍 点赞：{like_str}\n"
            )
            
            # 如果有简介就显示
            if desc and desc.strip():
                # 限制简介长度
                short_desc = desc[:150] + "..." if len(desc) > 150 else desc
                info_text += f"\n📝 简介：\n{short_desc}\n"
            
            info_text += "\n" + "─" * 30
            
            # 构建消息链
            info_chain = [Comp.Plain(info_text)]
            
            # 如果有封面URL,添加封面图片
            if pic_url:
                info_chain.append(Comp.Image.fromURL(pic_url))
            
            yield event.chain_result(info_chain)
            
            # 发送处理提示
            yield event.plain_result("🔄 正在获取字幕并生成总结...")

            # 获取字幕
            subtitle_text = await self.get_subtitle(aid, cid)
            
            # 如果没有字幕且启用了音频转文字功能
            if not subtitle_text and self.enable_audio_transcription:
                logger.info("未找到字幕，尝试使用音频转文字功能")
                yield event.plain_result("📝 未找到字幕，正在提取视频音频并转换为文字，这可能需要较长时间...")
                
                # 获取视频下载地址
                video_url = await self.get_video_download_url(aid, cid)
                if not video_url:
                    yield event.plain_result("❌ 无法获取视频下载地址")
                    return
                
                # 提取音频
                audio_path = await self.extract_audio_from_video(video_url, self.audio_extract_duration)
                if not audio_path:
                    yield event.plain_result("❌ 音频提取失败，请检查是否安装了ffmpeg")
                    return
                
                # 转换为文字
                subtitle_text = await self.transcribe_audio(audio_path)
                if not subtitle_text:
                    yield event.plain_result("❌ 语音识别失败，请检查Whisper API配置")
                    return
                
                logger.info(f"音频转文字成功，文本长度: {len(subtitle_text)}字符")
            elif not subtitle_text:
                yield event.plain_result("❌ 未找到可用的字幕，且音频转文字功能未启用")
                return

            # 生成总结
            summary = await self.generate_summary(title, desc, subtitle_text)
            if summary:
                # 分段发送总结,避免单条消息过长被截断
                # 消息平台通常限制单条消息长度(如QQ约4000字符)
                header = f"📺 视频标题：{title}\n\n📋 内容总结：\n"
                
                # 计算每段的最大长度(预留标题等overhead)
                max_chunk_size = 1500  # 保守设置为1500字符一段
                
                # 如果总结较短,直接发送
                if len(summary) + len(header) <= 2000:
                    result_message = header + summary
                    yield event.plain_result(result_message)
                else:
                    # 分段发送
                    # 先发送标题
                    yield event.plain_result(header.rstrip())
                    
                    # 将总结按段落分割(尽量保持段落完整性)
                    paragraphs = summary.split('\n\n')
                    current_chunk = ""
                    part_num = 1
                    
                    for para in paragraphs:
                        # 如果当前段落加入后会超长,先发送当前chunk
                        if len(current_chunk) + len(para) + 2 > max_chunk_size and current_chunk:
                            yield event.plain_result(f"【{part_num}/{len(paragraphs)}】\n{current_chunk}")
                            current_chunk = para
                            part_num += 1
                        else:
                            if current_chunk:
                                current_chunk += "\n\n" + para
                            else:
                                current_chunk = para
                    
                    # 发送最后一段
                    if current_chunk:
                        # 如果只有一段,不显示分段标记
                        if part_num == 1:
                            yield event.plain_result(current_chunk)
                        else:
                            yield event.plain_result(f"【{part_num}】\n{current_chunk}")
            else:
                yield event.plain_result("❌ 生成总结失败")

        except Exception as e:
            logger.error(f"Bilibili Summary插件: 处理请求时发生错误: {str(e)}")
            yield event.plain_result(f"❌ 处理请求时发生错误: {str(e)}")

    async def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """获取视频基本信息"""
        # 根据视频ID类型构建URL
        if video_id.startswith('av'):
            # AV号
            aid = re.search(r'av(\d+)', video_id, re.IGNORECASE).group(1)
            url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
        else:
            # BV号
            url = f"https://api.bilibili.com/x/web-interface/view?bvid={video_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            return None

    async def get_subtitle(self, aid: int, cid: int) -> Optional[str]:
        """获取视频字幕"""
        url = f"https://api.bilibili.com/x/player/wbi/v2?aid={aid}&cid={cid}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }

        # 如果有SESSDATA，添加到Cookie中
        if self.bilibili_sessdata:
            headers['Cookie'] = f'SESSDATA={self.bilibili_sessdata}'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
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
        except Exception as e:
            logger.error(f"获取字幕失败: {str(e)}")
            return None

    async def download_subtitle(self, subtitle_url: str) -> Optional[str]:
        """下载字幕文件并提取文本"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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
        except Exception as e:
            logger.error(f"下载字幕失败: {str(e)}")
            return None

    async def get_video_download_url(self, aid: int, cid: int) -> Optional[str]:
        """获取视频下载地址"""
        url = f"https://api.bilibili.com/x/player/playurl?avid={aid}&cid={cid}&qn=16"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        
        if self.bilibili_sessdata:
            headers['Cookie'] = f'SESSDATA={self.bilibili_sessdata}'
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            durl = data.get('data', {}).get('durl', [])
                            if durl and len(durl) > 0:
                                video_url = durl[0].get('url')
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
        except Exception as e:
            logger.error(f"获取视频下载地址失败: {str(e)}")
            return None

    async def extract_audio_from_video(self, video_url: str, duration: int = 0) -> Optional[str]:
        """从视频URL提取音频 - 使用ffmpeg直接从URL提取"""
        try:
            import subprocess
            
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            audio_path = os.path.join(temp_dir, f"bilibili_audio_{os.getpid()}.mp3")
            
            logger.info("开始提取音频（使用ffmpeg直接处理）...")
            
            # 使用ffmpeg直接从URL提取音频，避免手动下载
            try:
                # 构建ffmpeg命令
                cmd = [
                    'ffmpeg',
                    '-headers', f'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\nReferer: https://www.bilibili.com/',
                    '-i', video_url,
                    '-vn',  # 不处理视频
                    '-acodec', 'libmp3lame',  # 使用mp3编码
                    '-ar', '16000',  # 采样率16kHz（降低文件大小）
                    '-ac', '1',  # 单声道
                    '-b:a', '64k',  # 码率64kbps
                ]
                
                # 如果设置了时长限制
                if duration > 0:
                    cmd.extend(['-t', str(duration)])
                
                cmd.extend(['-y', audio_path])  # 覆盖已存在的文件
                
                logger.info(f"执行命令: ffmpeg -i [URL] -vn -acodec libmp3lame -ar 16000 -ac 1 -b:a 64k{' -t ' + str(duration) if duration > 0 else ''} {audio_path}")
                
                # 执行ffmpeg命令
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=300,  # 5分钟超时
                    encoding='utf-8',
                    errors='ignore'
                )
                
                if result.returncode == 0 and os.path.exists(audio_path):
                    file_size = os.path.getsize(audio_path)
                    logger.info(f"音频提取成功: {audio_path}, 大小: {file_size / 1024 / 1024:.2f}MB")
                    return audio_path
                else:
                    logger.error(f"ffmpeg提取音频失败")
                    logger.error(f"返回码: {result.returncode}")
                    if result.stderr:
                        stderr_lines = result.stderr.split('\n')
                        # 只记录最后几行错误信息
                        logger.error(f"错误信息: {' | '.join(stderr_lines[-5:])}")
                    return None
                    
            except FileNotFoundError:
                logger.error("未找到ffmpeg，请确保ffmpeg已安装并添加到系统PATH")
                return None
            except subprocess.TimeoutExpired:
                logger.error("ffmpeg执行超时（5分钟）")
                return None
            except Exception as e:
                logger.error(f"ffmpeg执行失败: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"提取音频失败: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return None

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """使用Whisper API将音频转换为文字"""
        try:
            if not os.path.exists(audio_path):
                logger.error(f"音频文件不存在: {audio_path}")
                return None
            
            # 检查文件大小（Whisper API限制25MB）
            file_size = os.path.getsize(audio_path)
            if file_size > 25 * 1024 * 1024:
                logger.warning(f"音频文件过大({file_size / 1024 / 1024:.2f}MB)，尝试压缩...")
                # 这里可以添加音频压缩逻辑
            
            logger.info("开始语音识别...")
            
            # 使用独立的 Whisper API Key，如果未设置则回退到 OpenAI API Key
            api_key = self.whisper_api_key if self.whisper_api_key else self.openai_api_key
            
            # 检测是否使用硅基流动API（通过URL判断）
            is_siliconflow = 'siliconflow.cn' in self.whisper_api_url.lower()
            
            # 准备multipart/form-data请求
            async with aiohttp.ClientSession() as session:
                # 使用 with 语句确保文件正确关闭
                with open(audio_path, 'rb') as audio_file:
                    data = aiohttp.FormData()
                    
                    # 添加文件字段 - 直接传递文件对象
                    data.add_field('file',
                                   audio_file,
                                   filename='audio.mp3',
                                   content_type='audio/mpeg')
                    
                    # 添加model字段 - 这是必需的
                    data.add_field('model', self.whisper_model)
                    
                    # 添加其他可选字段
                    if self.audio_language and not is_siliconflow:
                        # 硅基流动可能不支持language参数
                        data.add_field('language', self.audio_language)
                    
                    # 设置返回格式
                    if not is_siliconflow:
                        data.add_field('response_format', 'text')
                    
                    headers = {
                        'Authorization': f'Bearer {api_key}'
                    }
                    
                    # 构建请求URL（硅基流动可能需要model作为URL参数）
                    request_url = self.whisper_api_url
                    if is_siliconflow and '?' not in request_url:
                        request_url = f"{request_url}?model={self.whisper_model}"
                    
                    logger.info(f"发送语音识别请求")
                    logger.info(f"API地址: {request_url}")
                    logger.info(f"模型: {self.whisper_model}")
                    logger.info(f"文件大小: {file_size / 1024 / 1024:.2f}MB")
                    logger.info(f"是否硅基流动: {is_siliconflow}")
                    
                    try:
                        async with session.post(
                            request_url,
                            headers=headers,
                            data=data,
                            timeout=aiohttp.ClientTimeout(total=300)
                        ) as response:
                            response_text = await response.text()
                            
                            if response.status == 200:
                                # 尝试解析JSON响应（硅基流动可能返回JSON）
                                try:
                                    response_json = json.loads(response_text)
                                    # 硅基流动可能返回 {"text": "..."}
                                    if 'text' in response_json:
                                        text = response_json['text']
                                        logger.info(f"语音识别成功（JSON格式），文本长度: {len(text)}字符")
                                        return text
                                    elif 'data' in response_json and isinstance(response_json['data'], dict):
                                        text = response_json['data'].get('text', '')
                                        if text:
                                            logger.info(f"语音识别成功（data.text格式），文本长度: {len(text)}字符")
                                            return text
                                except json.JSONDecodeError:
                                    # 如果不是JSON，直接返回文本
                                    pass
                                
                                # 直接返回文本（OpenAI格式）
                                logger.info(f"语音识别成功（纯文本格式），文本长度: {len(response_text)}字符")
                                return response_text
                            else:
                                # 记录详细错误信息
                                logger.error(f"语音识别API请求失败")
                                logger.error(f"状态码: {response.status}")
                                logger.error(f"响应内容: {response_text}")
                                
                                # 尝试解析JSON错误信息
                                try:
                                    error_json = json.loads(response_text)
                                    logger.error(f"错误详情: {json.dumps(error_json, ensure_ascii=False)}")
                                except:
                                    pass
                                
                                return None
                    except asyncio.TimeoutError:
                        logger.error("语音识别请求超时")
                        return None
                    except Exception as e:
                        logger.error(f"发送请求时出错: {str(e)}")
                        return None
                        
        except Exception as e:
            logger.error(f"语音识别失败: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return None
        finally:
            # 清理临时音频文件
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.info("已清理临时音频文件")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")

    async def generate_summary(self, title: str, desc: str, subtitle_text: str) -> Optional[str]:
        """使用LLM生成视频总结"""
        # 构建提示词
        content = f"视频标题：{title}\n\n"
        if desc and desc.strip():
            content += f"视频简介：{desc}\n\n"
        content += f"视频字幕：\n{subtitle_text}"

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
            "max_tokens": 1000
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
        except Exception as e:
            logger.error(f"调用LLM API失败: {str(e)}")
            return None

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("Bilibili Summary插件: 已卸载")
