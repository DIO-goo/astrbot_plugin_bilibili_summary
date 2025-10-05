# FFmpeg 安装详细教程

本教程提供 FFmpeg 在各个操作系统上的详细安装步骤，包含图文说明。

## 什么是 FFmpeg？

FFmpeg 是一个开源的音视频处理工具，本插件使用它来从 B站视频中提取音频。

---

## Windows 系统安装教程

### 方法一：使用 Chocolatey 包管理器（最简单，推荐）

#### 步骤 1：安装 Chocolatey

1. 以**管理员身份**运行 PowerShell
   - 按 `Win + X` 键
   - 选择"Windows PowerShell (管理员)"或"终端 (管理员)"

2. 复制并粘贴以下命令，按回车：
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
   ```

3. 等待安装完成（约 1-2 分钟）

#### 步骤 2：使用 Chocolatey 安装 FFmpeg

在同一个 PowerShell 窗口中执行：
```powershell
choco install ffmpeg -y
```

等待安装完成，Chocolatey 会自动配置环境变量。

#### 步骤 3：验证安装

关闭并重新打开一个新的命令提示符窗口，输入：
```cmd
ffmpeg -version
```

如果看到版本信息，说明安装成功！

---

### 方法二：手动下载安装（适合不想安装 Chocolatey 的用户）

#### 步骤 1：下载 FFmpeg

1. 访问 FFmpeg 官网：https://ffmpeg.org/download.html
2. 点击 Windows 图标下的 "Windows builds from gyan.dev"
3. 或直接访问：https://www.gyan.dev/ffmpeg/builds/
4. 下载 **ffmpeg-release-essentials.zip**（约 70MB）

#### 步骤 2：解压文件

1. 将下载的 zip 文件解压到一个固定位置
   - 推荐路径：`C:\ffmpeg`
   - 不要放在临时文件夹或桌面
2. 解压后的文件结构应该是：
   ```
   C:\ffmpeg\
   ├── bin\
   │   ├── ffmpeg.exe
   │   ├── ffplay.exe
   │   └── ffprobe.exe
   ├── doc\
   └── presets\
   ```

#### 步骤 3：添加到系统环境变量

**Windows 11 / Windows 10:**

1. 右键点击"此电脑"或"我的电脑"
2. 选择"属性"
3. 点击"高级系统设置"
4. 点击"环境变量"按钮
5. 在"系统变量"区域找到 `Path` 变量
6. 双击 `Path` 变量进行编辑
7. 点击"新建"
8. 输入：`C:\ffmpeg\bin`（根据你实际的解压路径）
9. 依次点击"确定"关闭所有窗口

**Windows 7:**

1. 右键点击"计算机"
2. 选择"属性"
3. 点击"高级系统设置"
4. 点击"环境变量"
5. 在"系统变量"中找到 `Path`
6. 点击"编辑"
7. 在变量值的**末尾**添加：`;C:\ffmpeg\bin`（注意前面的分号）
8. 点击"确定"

#### 步骤 4：验证安装

1. **重要**：关闭所有命令提示符窗口
2. 打开一个**新的**命令提示符窗口（Win + R，输入 cmd）
3. 输入命令：
   ```cmd
   ffmpeg -version
   ```
4. 如果显示版本信息，说明安装成功！

**常见问题：**
- 如果提示"不是内部或外部命令"，检查路径是否正确添加
- 确保重新打开了新的命令提示符窗口
- 检查 `C:\ffmpeg\bin` 目录下是否有 `ffmpeg.exe` 文件

---

## Linux 系统安装教程

### Ubuntu / Debian 系统

#### 步骤 1：更新软件包列表

打开终端，执行：
```bash
sudo apt-get update
```

#### 步骤 2：安装 FFmpeg

```bash
sudo apt-get install ffmpeg -y
```

#### 步骤 3：验证安装

```bash
ffmpeg -version
```

### CentOS / RHEL 系统

#### 步骤 1：启用 EPEL 仓库

```bash
sudo yum install epel-release -y
```

#### 步骤 2：安装 FFmpeg

```bash
sudo yum install ffmpeg ffmpeg-devel -y
```

#### 步骤 3：验证安装

```bash
ffmpeg -version
```

### Fedora 系统

```bash
sudo dnf install ffmpeg -y
```

### Arch Linux

```bash
sudo pacman -S ffmpeg
```

### 通用方法（从源码编译）

如果软件仓库中没有 FFmpeg，可以下载预编译的二进制文件：

```bash
# 下载最新的静态构建版本
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz

# 解压
tar xvf ffmpeg-release-amd64-static.tar.xz

# 移动到系统路径
sudo mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/
sudo mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/

# 添加执行权限
sudo chmod +x /usr/local/bin/ffmpeg
sudo chmod +x /usr/local/bin/ffprobe

# 验证
ffmpeg -version
```

---

## macOS 系统安装教程

### 方法一：使用 Homebrew（推荐）

#### 步骤 1：安装 Homebrew（如果还没有）

打开终端，执行：
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 步骤 2：使用 Homebrew 安装 FFmpeg

```bash
brew install ffmpeg
```

#### 步骤 3：验证安装

```bash
ffmpeg -version
```

### 方法二：使用 MacPorts

```bash
sudo port install ffmpeg
```

---

## 验证 FFmpeg 是否正常工作

安装完成后，在终端/命令提示符中运行以下命令来验证：

```bash
ffmpeg -version
```

**预期输出示例：**
```
ffmpeg version 6.0 Copyright (c) 2000-2023 the FFmpeg developers
built with gcc 12.2.0 (GCC)
configuration: ...
libavutil      58.  2.100 / 58.  2.100
libavcodec     60.  3.100 / 60.  3.100
...
```

如果看到类似的版本信息，说明 FFmpeg 已成功安装！

---

## 常见问题解答

### Q1: Windows 下提示"ffmpeg 不是内部或外部命令"

**解决方法：**
1. 确认 FFmpeg 已正确解压到 `C:\ffmpeg` 目录
2. 检查环境变量 Path 中是否包含 `C:\ffmpeg\bin`
3. **重新打开**命令提示符窗口（环境变量需要重启窗口才生效）
4. 如果还不行，重启电脑

### Q2: Linux 下提示"Permission denied"

**解决方法：**
```bash
# 添加执行权限
sudo chmod +x /usr/local/bin/ffmpeg
```

### Q3: macOS 提示"command not found"

**解决方法：**
1. 确认 Homebrew 安装成功：`brew --version`
2. 重新安装：`brew reinstall ffmpeg`
3. 检查 PATH：`echo $PATH` 应该包含 `/usr/local/bin` 或 `/opt/homebrew/bin`

### Q4: 我想卸载 FFmpeg

**Windows (Chocolatey):**
```powershell
choco uninstall ffmpeg
```

**Windows (手动安装):**
1. 删除 `C:\ffmpeg` 文件夹
2. 从环境变量 Path 中移除 `C:\ffmpeg\bin`

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get remove ffmpeg

# CentOS/RHEL
sudo yum remove ffmpeg
```

**macOS:**
```bash
brew uninstall ffmpeg
```

### Q5: 安装后插件还是提示"未找到 ffmpeg"

**检查清单：**
1. ✅ 在命令行中运行 `ffmpeg -version` 能显示版本信息
2. ✅ 重启了 AstrBot（重要！）
3. ✅ 检查 AstrBot 日志中的错误信息
4. ✅ 确认插件配置中启用了"音频转文字"功能

---

## 测试 FFmpeg 功能

安装完成后，可以用以下命令测试 FFmpeg 是否能正常提取音频：

```bash
# 下载一个测试视频
curl -o test.mp4 "https://www.example.com/test.mp4"

# 提取音频
ffmpeg -i test.mp4 -vn -acodec libmp3lame test.mp3

# 如果成功生成 test.mp3 文件，说明 FFmpeg 工作正常
```

---

## 获取帮助

如果按照以上步骤仍然无法安装，请：

1. 查看 [FFmpeg 官方文档](https://ffmpeg.org/documentation.html)
2. 访问 [FFmpeg 官方论坛](https://ffmpeg.org/contact.html)
3. 在本项目提交 [GitHub Issue](https://github.com/VincenttHo/astrbot_plugin_bilibili_summary/issues)
4. 加入 AstrBot QQ 群：975206796

---

## 视频教程推荐

如果您更喜欢看视频教程，可以在 B站搜索：
- "FFmpeg Windows 安装教程"
- "FFmpeg 环境变量配置"

相关教学视频可以帮助您更直观地了解安装过程。

---

**祝您安装顺利！🎉**