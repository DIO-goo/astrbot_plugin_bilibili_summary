<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_bilibili_summary?name=astrbot_plugin_bilibili_summary&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

</div>

# Bilibili视频字幕总结插件

这是一个AstrBot插件，可以获取Bilibili视频的字幕并使用LLM生成内容总结。节省你的时间！

## 功能特性

- 🎬 支持多种Bilibili视频链接格式（BV号、AV号、完整链接、短链接）
- 🤖 使用LLM生成视频内容总结
- 🌏 优先选择中文字幕，支持多语言字幕
- 🎵 **智能音频转文字**：当视频没有字幕时，自动提取音频并使用Whisper API转换为文字
- ⚙️ 可配置的API参数和请求间隔
- 🛡️ 内置风控保护机制
- 💬 支持引用消息和转发消息解析
- 🔗 **自动检测触发**：智能识别消息中的bilibili链接和BV号，无需手动输入指令

## 安装方法

### 方法一：通过AstrBot界面的插件市场安装

1. 在AstrBot管理界面中，进入"插件市场"
2. 搜索 `astrbot_plugin_bilibili_summary`
3. 点击安装即可

### 方法二：手动安装

1. 克隆或下载插件代码到AstrBot的插件目录：
```bash
cd AstrBot/data/plugins
git clone https://github.com/VincenttHo/astrbot_plugin_bilibili_summary
```

2. 安装依赖：
```bash
cd astrbot_plugin_bilibili_summary
pip install -r requirements.txt
```

3. 重启AstrBot或在管理面板中重载插件

**📖 详细安装说明请查看 [安装指南 INSTALL.md](INSTALL.md)**

## 配置说明

在AstrBot管理面板中配置以下参数：

### 必需配置 <font color='red'>（重要）</font>
- **OpenAI API密钥**: 用于调用LLM生成总结的API密钥
- **OpenAI API地址**: 默认为OpenAI官方地址，可配置为其他兼容接口
- **使用的模型**: 默认为gpt-3.5-turbo
- **Bilibili SESSDATA**: 从浏览器Cookie中获取，用于访问需要登录的API

#### 如何获取Bilibili SESSDATA？

1. 打开浏览器，登录Bilibili
2. 按F12打开开发者工具
3. 切换到"Application"或"应用程序"标签
4. 在左侧找到"Cookies" -> "https://www.bilibili.com"
5. 找到名为"SESSDATA"的Cookie，复制其值
6. 将该值填入插件配置中

### 音频转文字配置
- **Whisper API密钥**: 用于语音转文字的API密钥（独立配置，如不填写则使用OpenAI API密钥）
- **启用音频转文字**: 当视频没有字幕时，自动提取音频并转换为文字（默认启用）
- **音频提取时长**: 最多提取多少秒的音频进行转写，避免处理过长视频（默认300秒，0表示不限制）
- **Whisper API地址**: 语音转文字API接口地址，兼容OpenAI Whisper格式
- **Whisper模型**: 使用的语音识别模型名称（默认whisper-1）
- **音频语言**: 音频的主要语言，用于提高识别准确率（zh=中文, en=英文）

### 可选配置
- **请求间隔**: 两次API请求之间的间隔时间，避免触发风控
- **最大字幕长度**: 提交给LLM的字幕最大字符数
- **总结提示词**: 用于指导LLM生成总结的提示词


## 使用方法

### 自动触发模式（推荐）

插件会自动检测消息中的bilibili视频链接和BV号，无需输入任何指令：

```
# 直接发送或转发包含bilibili链接的消息
https://www.bilibili.com/video/BV1jv7YzJED2

# 发送BV号
BV1jv7YzJED2

# 发送AV号
av123456

# 发送短链接
https://b23.tv/xxxxx

# 引用包含bilibili链接的消息

# 转发bilibili视频卡片
```

### 支持的链接格式

- **BV号**：BV1jv7YzJED2 或 1jv7YzJED2
- **AV号**：av123456 或 123456
- **完整链接**：https://www.bilibili.com/video/BV1jv7YzJED2
- **手机链接**：https://m.bilibili.com/video/BV1jv7YzJED2
- **短链接**：https://b23.tv/xxxxx
- **小程序卡片**：QQ等平台的bilibili分享卡片

## 注意事项

- 获取视频字幕信息需要登录状态，请确保配置了有效的SESSDATA
- 请求过于频繁可能触发Bilibili的风控机制，建议适当设置请求间隔
- **音频转文字功能需要安装ffmpeg**，请确保系统中已安装ffmpeg并添加到环境变量
- 音频转文字功能会消耗较多时间和API额度，建议设置合理的音频提取时长
- 对于没有字幕的视频，插件会自动尝试使用音频转文字功能
- 请遵守Bilibili的使用条款和相关法律法规

## 系统要求

### 基础功能（字幕总结）
- Python 3.8+
- aiohttp

### 音频转文字功能（可选）
- **ffmpeg**: 用于提取视频音频
  - Windows: 从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载并添加到PATH
  - Linux: `sudo apt-get install ffmpeg` 或 `sudo yum install ffmpeg`
  - macOS: `brew install ffmpeg`
  - **📖 详细的 FFmpeg 安装教程请查看 → [FFMPEG_INSTALL_GUIDE.md](FFMPEG_INSTALL_GUIDE.md)**
- **Whisper API**: 支持OpenAI Whisper API或兼容的语音识别接口


## 使用示例

![使用示例图](https://raw.githubusercontent.com/VincenttHo/astrbot_plugin_bilibili_summary/refs/heads/main/images/sample.jpg)

## 版本历史

- v1.0.0: 初始版本，支持多种格式搜索视频并进行总结
- v1.0.1: 新增引用消息和转发消息解析功能，支持智能提取bilibili链接
- v1.1.0: 新增音频转文字功能，支持无字幕视频的内容总结
- v1.2.0: 改为自动检测触发模式，无需手动输入指令，智能识别消息中的bilibili链接和BV号