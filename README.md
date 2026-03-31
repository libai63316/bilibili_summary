# B站/小红书视频字幕提取与LLM总结工具

从B站视频提取字幕或转写音频，从小红书下载视频并转写音频，然后使用Claude生成智能总结。

## 功能特点

- **B站有字幕视频**：直接提取B站视频内置字幕（支持ass/srt/vtt格式）
- **B站无字幕视频**：自动下载音频并使用AI模型转写
- **小红书视频**：下载视频音频并转写（小红书无字幕功能）
- **智能总结**：三种总结程度可选（简洁/中等/详细）
- **多模型支持**：SenseVoice、Whisper多种转录模型可选
- **长音频处理**：自动分段转写，避免显存不足

## 支持的平台

| 平台 | 字幕提取 | 音频转写 | 链接格式 |
|------|----------|----------|----------|
| B站 | ✓ (有字幕时) | ✓ (无字幕时) | `bilibili.com/video/`, `b23.tv/` |
| 小红书 | ✗ | ✓ | `xiaohongshu.com/discovery/item/`, `xhslink.com/` |

## 安装依赖

```bash
pip install -r requirements.txt
```

### 主要依赖

| 依赖 | 说明 |
|------|------|
| yt-dlp | B站视频/音频下载，支持WBI签名 |
| funasr | FunASR/SenseVoice中文语音识别 |
| faster-whisper | Whisper转写（英文支持好） |
| claude | Claude Code CLI（用于总结） |

### ffmpeg

本项目使用 `imageio-ffmpeg` 提供的ffmpeg二进制文件，无需单独安装。

## 快速开始

### 交互模式

```bash
python main.py
```

### 有字幕视频

```bash
python main.py <B站视频URL>
```

### 无字幕视频（音频转写）

```bash
# 使用SenseVoice转写（默认，中文效果好）
python main.py --audio <音频下载链接>

# 使用Whisper转写（英文支持好）
python main.py --audio <音频下载链接> --model whisper
```

### 小红书视频

```bash
python main.py <小红书视频URL>
# 支持短链接：http://xhslink.com/o/xxx
```

### 仅总结现有字幕

```bash
python main.py --summarize <md文件路径>
```

### 下载音频

```bash
python main.py --download <音频URL> [保存路径]
```

### 自动转写

扫描 `temp_audio/` 目录，自动转写未处理的文件：

```bash
python main.py --auto
```

## 交互模式选项说明

```
1. 处理B站视频（自动检测是否有字幕）
2. 处理小红书视频（音频转写）
3. 处理其他音频文件（本地/URL，音频转写）
4. 总结现有的.md文件
5. 转写temp_audio中的音频文件
6. 查看历史记录
0. 退出
```

**快捷输入**：直接粘贴视频链接（B站或小红书），自动识别平台并处理。

选择选项时会提示选择：
- **总结程度**：简洁 / 中等 / 详细
- **转录模型**：SenseVoice（默认） / Whisper

## 配置

在 `config.py` 中配置：

```python
# 默认转录模型: sensevoice, whisper, siliconflow
DEFAULT_TRANSCRIBE_MODEL = "sensevoice"

# 默认总结程度: brief, normal, detailed
DEFAULT_SUMMARY_LEVEL = "detailed"
```

## 输出目录

```
bilibili-subtitle/
├── temp_audio/           # 下载的临时音频文件
├── output/
│   ├── subtitles/        # 提取/转写的字幕Markdown文件
│   └── summaries/        # Claude生成的总结文件
└── temp_subs/           # yt-dlp临时字幕文件
```

## 转录模型对比

| 模型 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| SenseVoice | 中文为主 | 中文识别效果好，速度快 | 英文识别一般 |
| Whisper | 英文为主 | 英文支持好，泛化能力强 | 中文识别不如SenseVoice |
| SiliconFlow | 云端转写 | 无需本地GPU | 需要API Key |

## 技术栈

- **转写模型**：FunASR (iic/SenseVoiceSmall)
- **音频下载**：yt-dlp
- **音频格式**：M4A（直接支持，无需转换）
- **GPU 加速**：支持 NVIDIA GPU
- **长音频处理**：自动分段（5分钟/段）

## 文件说明

```
bilibili-subtitle/
├── main.py              # 主入口程序
├── config.py            # 配置文件
├── subtitle_extractor.py # B站字幕提取（yt-dlp）
├── speech_to_text.py    # 音频转写模块
├── summarizer.py        # Claude总结模块
└── requirements.txt     # 依赖列表
```
