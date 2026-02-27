<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_bilibili_summary?name=astrbot_plugin_bilibili_summary&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

</div>

# Bilibili 视频总结插件

AstrBot 插件，自动检测消息中的 B站视频链接，获取字幕和热门评论并使用 LLM 生成内容总结。

## 功能特性

- **自动触发** — 智能识别消息中的 Bilibili 链接，无需手动输入指令
- **字幕获取** — 优先选择中文字幕，支持多语言
- **音频转文字** — 无字幕时自动提取音频，通过 Whisper API 转写
- **热门评论** — 抓取热评辅助生成更全面的总结
- **卡片渲染** — 总结结果以精美卡片图片形式发送
- **多格式支持** — BV号、AV号、完整链接、短链接、小程序卡片、引用/转发消息

## 安装

### 方法一：插件市场（推荐）

1. 进入 AstrBot 管理界面 → "插件市场"
2. 搜索 `astrbot_plugin_bilibili_summary`
3. 点击安装

### 方法二：手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/VincenttHo/astrbot_plugin_bilibili_summary
cd astrbot_plugin_bilibili_summary
pip install -r requirements.txt
```

重启 AstrBot 或在管理面板中重载插件。

> 详细安装说明请查看 [INSTALL.md](INSTALL.md)

## 配置说明

在 AstrBot 管理面板中配置以下参数：

### 必需配置

| 配置项 | 说明 |
|--------|------|
| **OpenAI API 密钥** | 用于调用 LLM 生成总结 |
| **OpenAI API 地址** | 默认 OpenAI 官方地址，可换为兼容接口 |
| **使用的模型** | 默认 gpt-3.5-turbo |
| **Bilibili Cookie** | Netscape 格式，用于访问需要登录的 API |

### 如何获取 Bilibili Cookie？

1. 安装浏览器扩展 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. 登录 [bilibili.com](https://www.bilibili.com)
3. 点击扩展图标，导出当前站点的 Cookie（Netscape 格式）
4. 将导出的全部文本粘贴到插件配置的 **Bilibili Cookie** 字段中

> 导出的文本包含 `#HttpOnly_` 开头的行是正常的，插件会自动解析。

### 音频转文字配置（可选）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 启用音频转文字 | 开启 | 无字幕时自动提取音频转写 |
| 音频提取时长 | 300秒 | 最多提取的音频时长，0 = 不限制 |
| Whisper API 密钥 | 空 | 不填则复用 OpenAI API 密钥 |
| Whisper API 地址 | OpenAI 官方 | 兼容 OpenAI Whisper 格式的接口 |
| Whisper 模型 | whisper-1 | 语音识别模型名称 |
| 音频语言 | zh | zh=中文, en=英文 |

### 其他配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 请求间隔 | 2.0秒 | API 请求间隔，避免触发风控 |
| 最大字幕长度 | 8000 | 提交给 LLM 的字幕最大字符数 |
| 总结提示词 | 内置 | 可自定义 LLM 生成总结的提示词 |

## 使用方法

插件会自动检测消息中的视频链接，无需输入任何指令：

```
# 直接发送链接或BV号
https://www.bilibili.com/video/BV1jv7YzJED2
BV1jv7YzJED2
av123456
https://b23.tv/xxxxx

# 也支持引用/转发包含视频链接的消息、小程序卡片
```

### 支持的链接格式

- **BV号** — `BV1jv7YzJED2` 或 `1jv7YzJED2`
- **AV号** — `av123456` 或 `123456`
- **完整链接** — `https://www.bilibili.com/video/BV1jv7YzJED2`
- **手机链接** — `https://m.bilibili.com/video/BV1jv7YzJED2`
- **短链接** — `https://b23.tv/xxxxx`
- **小程序卡片** — QQ 等平台的 bilibili 分享卡片

## 系统要求

- Python 3.8+
- aiohttp
- **ffmpeg**（音频转文字功能需要）
  - Windows: `choco install ffmpeg` 或从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载
  - Linux: `sudo apt-get install ffmpeg`
  - macOS: `brew install ffmpeg`

## 使用示例

![使用示例图](https://raw.githubusercontent.com/VincenttHo/astrbot_plugin_bilibili_summary/refs/heads/main/images/sample.jpg)

## 注意事项

- 获取视频字幕需要有效的 Cookie，请确保配置了 Netscape 格式的 Bilibili Cookie
- 请求过于频繁可能触发 B站风控，建议保持默认请求间隔
- 音频转文字会消耗较多时间和 API 额度，建议设置合理的提取时长
- 请遵守 Bilibili 使用条款和相关法律法规

## 版本历史

- v1.4.0: 移除 YouTube 支持，改用 Netscape 格式 Cookie 配置，新增热门评论抓取和卡片渲染
- v1.3.4: 修复 YouTube 无字幕时音频下载失败问题
- v1.3.3: 新增 Cookie 文本配置，适配云部署场景
- v1.3.2: 新增 yt-dlp Cookie 配置
- v1.3.1: 修复 YouTube 链接解析触发逻辑
- v1.3.0: 新增 YouTube 视频支持
- v1.2.0: 改为自动检测触发模式
- v1.1.0: 新增音频转文字功能
- v1.0.1: 新增引用消息和转发消息解析
- v1.0.0: 初始版本
