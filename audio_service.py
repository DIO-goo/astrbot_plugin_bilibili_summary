"""
音频处理服务模块
负责音频提取和语音识别功能
"""
import asyncio
import json
import os
import subprocess
import tempfile
import mimetypes
from typing import Optional
import aiohttp
from astrbot.api import logger


class AudioService:
    """音频处理服务类"""
    
    def __init__(self, whisper_api_key: str, whisper_api_url: str, 
                 whisper_model: str, audio_language: str):
        self.whisper_api_key = whisper_api_key
        self.whisper_api_url = whisper_api_url
        self.whisper_model = whisper_model
        self.audio_language = audio_language
    
    async def extract_audio_from_video(self, video_url: str, duration: int = 0) -> Optional[str]:
        """从视频URL提取音频 - 使用ffmpeg异步提取"""
        try:
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            audio_path = os.path.join(temp_dir, f"bilibili_audio_{os.getpid()}.mp3")
            
            logger.info("开始提取音频（使用ffmpeg异步处理）...")
            
            # 使用ffmpeg直接从URL提取音频，避免手动下载
            try:
                # 构建ffmpeg命令 - 添加更多参数以应对B站的防盗链
                cmd = [
                    'ffmpeg',
                    '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    '-referer', 'https://www.bilibili.com/',
                    '-reconnect', '1',  # 自动重连
                    '-reconnect_streamed', '1',  # 对流式连接重连
                    '-reconnect_delay_max', '5',  # 最大重连延迟5秒
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
                
                logger.info("执行ffmpeg命令（异步，带重连机制）")
                
                # 使用asyncio.create_subprocess_exec异步执行ffmpeg命令
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # 等待进程完成，设置超时
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=300  # 5分钟超时
                    )
                except asyncio.TimeoutError:
                    logger.error("ffmpeg执行超时（5分钟）")
                    process.kill()
                    await process.wait()
                    return None
                
                # 解码输出
                stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ''
                
                if process.returncode == 0 and os.path.exists(audio_path):
                    file_size = os.path.getsize(audio_path)
                    logger.info(f"音频提取成功: {audio_path}, 大小: {file_size / 1024 / 1024:.2f}MB")
                    return audio_path
                else:
                    # 检查是否是网络问题
                    if stderr_text and ('Stream ends prematurely' in stderr_text or 'Invalid data found' in stderr_text):
                        logger.error("视频URL可能已过期或存在防盗链限制")
                        logger.info("尝试重新获取视频URL...")
                        return None
                    else:
                        logger.error("ffmpeg提取音频失败")
                        logger.error(f"返回码: {process.returncode}")
                        if stderr_text:
                            stderr_lines = stderr_text.split('\n')
                            logger.error(f"错误信息: {' | '.join(stderr_lines[-5:])}")
                        return None
                        
            except FileNotFoundError:
                logger.error("未找到ffmpeg，请确保ffmpeg已安装并添加到系统PATH")
                return None
            except Exception as e:
                logger.error(f"ffmpeg执行时发生未预期错误: {type(e).__name__}: {str(e)}")
                return None
                
        except OSError as e:
            logger.error(f"文件系统操作失败: {type(e).__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"提取音频时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None

    async def transcribe_audio(self, audio_path: str, openai_api_key: str) -> Optional[str]:
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
            api_key = self.whisper_api_key if self.whisper_api_key else openai_api_key
            
            # 准备multipart/form-data请求
            async with aiohttp.ClientSession() as session:
                # 使用 with 语句确保文件正确关闭
                with open(audio_path, 'rb') as audio_file:
                    data = aiohttp.FormData()
                    
                    # 根据实际音频后缀推断文件名和MIME类型（兼容m4a/webm/mp3等）
                    filename = os.path.basename(audio_path) or 'audio.mp3'
                    guessed_mime, _ = mimetypes.guess_type(filename)
                    content_type = guessed_mime or 'application/octet-stream'
                    
                    # 添加文件字段 - 直接传递文件对象
                    data.add_field('file',
                                   audio_file,
                                   filename=filename,
                                   content_type=content_type)
                    
                    # 添加model字段 - 这是必需的
                    data.add_field('model', self.whisper_model)
                    
                    # 添加其他可选字段
                    if self.audio_language:
                        data.add_field('language', self.audio_language)
                    
                    # 设置返回格式
                    data.add_field('response_format', 'json')
                    
                    headers = {
                        'Authorization': f'Bearer {api_key}'
                    }
                    
                    request_url = self.whisper_api_url
                    
                    logger.info("发送语音识别请求")
                    logger.info(f"API地址: {request_url}")
                    logger.info(f"模型: {self.whisper_model}")
                    logger.info(f"文件大小: {file_size / 1024 / 1024:.2f}MB")
                    
                    try:
                        async with session.post(
                            request_url,
                            headers=headers,
                            data=data,
                            timeout=aiohttp.ClientTimeout(total=300)
                        ) as response:
                            response_text = await response.text()
                            
                            if response.status == 200:
                                # 尝试解析JSON响应
                                try:
                                    response_json = json.loads(response_text)
                                    text = ""
                                    
                                    # 标准OpenAI格式: {"text": "..."}
                                    if 'text' in response_json:
                                        text = response_json['text']
                                    # 某些变体格式
                                    elif 'data' in response_json and isinstance(response_json['data'], dict):
                                        text = response_json['data'].get('text', '')
                                    
                                    if text:
                                        logger.info(f"语音识别成功，文本长度: {len(text)}字符")
                                        return text
                                    else:
                                        # 如果JSON中没有text字段，可能返回了其他格式，尝试直接返回
                                        logger.warning(f"语音识别响应JSON中未找到text字段: {response_text[:100]}...")
                                        return str(response_json)
                                        
                                except json.JSONDecodeError:
                                    # 如果不是JSON，直接返回文本
                                    logger.info(f"语音识别成功（非JSON格式），文本长度: {len(response_text)}字符")
                                    return response_text
                            else:
                                # 记录详细错误信息
                                logger.error("语音识别API请求失败")
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
                        
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {type(e).__name__}: {str(e)}")
            return None
        except OSError as e:
            logger.error(f"文件操作失败: {type(e).__name__}: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"语音识别时发生未预期错误: {type(e).__name__}: {str(e)}")
            return None
        finally:
            # 清理临时音频文件
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.info("已清理临时音频文件")
                except OSError as e:
                    logger.warning(f"清理临时文件失败: {type(e).__name__}: {str(e)}")
                except Exception as e:
                    logger.error(f"清理临时文件时发生未预期错误: {type(e).__name__}: {str(e)}")