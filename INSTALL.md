# 安装指南

本文档提供详细的安装步骤，帮助您正确配置插件的所有依赖。

## 1. Python 依赖安装

### 自动安装（推荐）

当您在 AstrBot 中安装或重载本插件时，AstrBot 会自动读取 `requirements.txt` 文件并安装所需的 Python 依赖包。

### 手动安装

如果需要手动安装 Python 依赖，请在插件目录下执行：

```bash
# 进入插件目录
cd AstrBot/data/plugins/astrbot_plugin_bilibili_summary

# 安装依赖
pip install -r requirements.txt
```

或者使用国内镜像源加速：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 依赖包说明

- **aiohttp**: 异步HTTP客户端，用于网络请求
- **pydub**: 音频处理库（v1.1.0新增）

## 2. 系统依赖安装（音频转文字功能必需）

### FFmpeg 安装

音频转文字功能需要 FFmpeg 来提取视频中的音频。

**📖 详细的 FFmpeg 安装教程请查看 → [FFMPEG_INSTALL_GUIDE.md](FFMPEG_INSTALL_GUIDE.md)**

以下是快速安装方法：

#### Windows 系统

**方法一：使用包管理器（推荐）**

1. 安装 [Chocolatey](https://chocolatey.org/install)
2. 以管理员身份运行 PowerShell：
   ```powershell
   choco install ffmpeg
   ```

**方法二：手动安装**

1. 访问 [FFmpeg 官网](https://ffmpeg.org/download.html)
2. 下载 Windows 版本（推荐下载 full 版本）
3. 解压到合适的位置（如 `C:\ffmpeg`）
4. 添加到系统环境变量：
   - 右键"此电脑" → "属性" → "高级系统设置" → "环境变量"
   - 在"系统变量"中找到 `Path`，点击"编辑"
   - 添加 FFmpeg 的 bin 目录路径（如 `C:\ffmpeg\bin`）
   - 点击"确定"保存

5. 验证安装：打开新的命令提示符窗口，输入：
   ```cmd
   ffmpeg -version
   ```

#### Linux 系统

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**CentOS/RHEL:**
```bash
# 启用 EPEL 仓库
sudo yum install epel-release
# 安装 FFmpeg
sudo yum install ffmpeg
```

**Fedora:**
```bash
sudo dnf install ffmpeg
```

验证安装：
```bash
ffmpeg -version
```

#### macOS 系统

使用 Homebrew 安装：

```bash
# 如果没有安装 Homebrew，先安装：
# /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 FFmpeg
brew install ffmpeg
```

验证安装：
```bash
ffmpeg -version
```

## 3. 配置插件

在 AstrBot 管理面板中配置插件：

### 必需配置

1. **OpenAI API密钥**: 用于调用 LLM 和 Whisper API
   - 从 [OpenAI Platform](https://platform.openai.com/api-keys) 获取
   - 或使用兼容 OpenAI 格式的其他服务提供商

2. **Bilibili SESSDATA**: 用于访问 B站 API
   - 登录 [bilibili.com](https://www.bilibili.com)
   - 按 F12 打开开发者工具
   - 转到"应用程序/Application" → "Cookies" → "https://www.bilibili.com"
   - 找到 `SESSDATA` 并复制其值

### 音频转文字配置（可选）

- **启用音频转文字**: 默认启用，可以关闭以仅使用字幕
- **音频提取时长**: 建议设置为 300 秒（5分钟），避免处理过长视频
- **Whisper API地址**: 默认使用 OpenAI 官方地址
- **Whisper模型**: 默认 whisper-1
- **音频语言**: 默认 zh（中文）

## 4. 验证安装

### 测试基础功能（字幕总结）

在 AstrBot 中发送：
```
/bs BV1jv7YzJED2
```

如果成功返回视频总结，说明基础功能正常。

### 测试音频转文字功能

找一个没有字幕的 B站视频，发送：
```
/bs [无字幕视频的BV号]
```

如果插件提示"正在提取视频音频并转换为文字"，说明音频转文字功能已启用。

## 5. 常见问题

### Q: 提示"未找到 ffmpeg"
**A**: 请确保已正确安装 FFmpeg 并添加到系统 PATH 环境变量中。安装后需要重启终端或命令提示符。

### Q: 音频转文字很慢
**A**: 这是正常现象。音频转文字需要：
1. 下载视频（取决于网络速度）
2. 提取音频（取决于视频长度）
3. 调用 Whisper API（取决于音频长度和 API 响应速度）

建议设置合理的 `audio_extract_duration` 参数。

### Q: Whisper API 调用失败
**A**: 可能的原因：
- API 密钥不正确或已过期
- API 配额不足
- 网络连接问题
- 音频文件过大（超过 25MB）

### Q: 提示"音频提取失败"
**A**: 可能的原因：
- FFmpeg 未正确安装
- 视频下载失败（网络问题或需要登录权限）
- 磁盘空间不足

### Q: Python 依赖安装失败
**A**: 尝试：
```bash
# 升级 pip
pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 6. 获取帮助

如果遇到问题：

1. 查看 AstrBot 日志：在管理面板的"日志"选项卡中查看详细错误信息
2. 查看 [项目 README](README.md)
3. 提交 [GitHub Issue](https://github.com/VincenttHo/astrbot_plugin_bilibili_summary/issues)
4. 加入 AstrBot QQ群：975206796

## 7. 升级插件

如果从旧版本升级：

```bash
cd AstrBot/data/plugins/astrbot_plugin_bilibili_summary
git pull
pip install -r requirements.txt
```

然后在 AstrBot 管理面板中重载插件。