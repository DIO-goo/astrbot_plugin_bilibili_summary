# 安装指南

本文档提供详细的安装步骤，帮助您正确配置插件的所有依赖。

## 1. Python 依赖安装

### 自动安装（推荐）

在 AstrBot 中安装或重载本插件时，AstrBot 会自动读取 `requirements.txt` 并安装依赖。

### 手动安装

```bash
cd AstrBot/data/plugins/astrbot_plugin_bilibili_summary
pip install -r requirements.txt
```

国内镜像加速：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 依赖包说明

- **aiohttp**: 异步 HTTP 客户端，用于调用 B站 API 和下载资源

## 2. FFmpeg 安装（音频转文字功能需要）

如果不需要音频转文字功能，可以跳过此步骤。

### Windows

**方法一：包管理器（推荐）**

```powershell
# 安装 Chocolatey 后，以管理员身份运行：
choco install ffmpeg
```

**方法二：手动安装**

1. 从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载 Windows 版本
2. 解压到合适位置（如 `C:\ffmpeg`）
3. 将 `C:\ffmpeg\bin` 添加到系统 PATH 环境变量
4. 打开新的命令提示符，验证：`ffmpeg -version`

### Linux

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install ffmpeg

# CentOS/RHEL
sudo yum install epel-release && sudo yum install ffmpeg

# Fedora
sudo dnf install ffmpeg
```

### macOS

```bash
brew install ffmpeg
```

## 3. 配置插件

在 AstrBot 管理面板中配置：

### 必需配置

1. **OpenAI API 密钥**: 用于调用 LLM 生成总结
   - 从 [OpenAI Platform](https://platform.openai.com/api-keys) 获取
   - 或使用兼容 OpenAI 格式的其他服务

2. **Bilibili Cookie（Netscape 格式）**: 用于访问 B站 API
   - 安装浏览器扩展 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - 登录 [bilibili.com](https://www.bilibili.com)
   - 点击扩展图标，导出当前站点 Cookie
   - 将全部文本粘贴到插件配置中

### 音频转文字配置（可选）

- **启用音频转文字**: 默认开启
- **音频提取时长**: 建议 300 秒，避免处理过长视频
- **Whisper API 地址**: 默认 OpenAI 官方地址
- **Whisper 模型**: 默认 whisper-1
- **音频语言**: 默认 zh（中文）

## 4. 验证安装

在聊天中发送一个 B站视频链接，例如：

```
https://www.bilibili.com/video/BV1jv7YzJED2
```

如果成功返回视频总结卡片，说明安装正常。

要测试音频转文字功能，可以发送一个没有字幕的视频链接，插件会自动提取音频并转写。

## 5. 常见问题

### Q: 提示"获取字幕需要登录"
**A**: 请确保在插件配置中正确填写了 Netscape 格式的 Bilibili Cookie。Cookie 有有效期，过期后需要重新导出。

### Q: 提示"未找到 ffmpeg"
**A**: 请安装 FFmpeg 并添加到系统 PATH。安装后需要重启终端。

### Q: 音频转文字很慢
**A**: 这是正常现象，需要下载视频、提取音频、调用 Whisper API。建议设置合理的 `音频提取时长`。

### Q: Whisper API 调用失败
**A**: 可能原因：API 密钥不正确/过期、配额不足、网络问题、音频文件超过 25MB。

### Q: Python 依赖安装失败
**A**:
```bash
pip install --upgrade pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 6. 获取帮助

1. 查看 AstrBot 管理面板的"日志"选项卡
2. 提交 [GitHub Issue](https://github.com/VincenttHo/astrbot_plugin_bilibili_summary/issues)

## 7. 升级插件

```bash
cd AstrBot/data/plugins/astrbot_plugin_bilibili_summary
git pull
pip install -r requirements.txt
```

然后在 AstrBot 管理面板中重载插件。
