# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this codebase.

## 项目概述

B站视频字幕提取与LLM总结工具 - 从B站视频提取字幕或转写音频，然后使用Claude Code CLI生成总结。

## 常用命令

```bash
python main.py <B站视频URL>                    # 自动模式：检测字幕，无字幕自动转写
python main.py --audio <音频URL> --model whisper   # 指定Whisper模型转写
python main.py --summarize <md文件路径>        # 仅总结（不传路径则自动扫描未总结文件）
python main.py --history [数量]                # 查看历史记录
python main.py --clear-history                 # 清空历史
python main.py --interactive                   # 交互模式
```

## 依赖安装

```bash
pip install -r requirements.txt
```

需要预先安装：
- `yt-dlp` - 视频/字幕下载（支持B站WBI签名）
- `claude` CLI - Claude Code CLI工具（用于总结）

ffmpeg无需单独安装，项目使用 `imageio-ffmpeg` 内置的二进制文件。

## 代码架构

```
main.py              # 主入口，命令行参数解析 + 交互模式
├── handle_video_with_subtitle()     # 有字幕视频处理（自动降级到音频转写）
├── handle_video_without_subtitle()  # 无字幕视频处理（音频转写）
├── handle_video_without_subtitle_process()  # 音频处理通用函数
├── handle_summarize_only()          # 仅总结
├── show_history()                   # 显示历史记录
└── open_file()                      # 自动打开总结文件

subtitle_extractor.py    # yt-dlp提取B站字幕 → 解析ass/srt/vtt → 保存md
speech_to_text.py        # 音频转写模块：
│   ├── get_bilibili_video_info()    # 获取视频元信息（标题、时长、UP主等）
│   ├── transcribe_with_sensevoice() # FunASR/SenseVoice（中文效果好）
│   ├── transcribe_with_whisper_local()  # faster-whisper（英文支持好）
│   └── download_audio_from_bilibili()   # yt-dlp下载B站音频

summarizer.py          # 调用 claude -p @file 生成总结
config.py              # 目录配置、总结提示词、内容类型识别、历史记录管理
```

## 核心流程

1. **自动模式**: yt-dlp探测字幕 → 有字幕则提取 → 无字幕自动降级到音频转写 → Claude总结
2. **音频转写**: yt-dlp下载音频 → SenseVoice/Whisper转写 → 保存md（含元信息）→ Claude总结
3. **仅总结**: 读取md → Claude生成总结 → 保存到summaries目录

## 智能化功能

### 智能总结力度
根据视频时长自动选择（`config.py: auto_select_summary_level()`）：
- `< 1分钟` → brief
- `1-5分钟` → normal
- `> 5分钟` → detailed

### 内容类型识别
根据标题关键词识别类型并调整总结风格（`config.py: CONTENT_TYPES`）：
- 教程类、新闻类、Vlog、科技类、财经类、娱乐类、知识科普

### 自动模式（无感切换）
`handle_video_with_subtitle()` 自动检测字幕，无字幕时自动切换到音频转写。

### 长音频分段
音频超过10分钟自动分段处理（`speech_to_text.py`），每段10分钟。

## 输出目录

- `temp_audio/` - 下载的临时音频文件
- `output/subtitles/` - 字幕/转写Markdown文件（含视频元信息）
- `output/summaries/` - Claude生成的总结文件
- `history.json` - 历史记录

## 视频元信息保存格式

字幕/转写文件包含完整元信息：
```markdown
# 视频标题

## 视频信息
- **来源**: https://www.bilibili.com/video/xxx
- **时长**: 15分30秒
- **UP主**: xxx
- **内容类型**: 教程类
- **处理时间**: 2026-03-30 12:00:00

---

## 转写文本
...
```

## 交互模式菜单

```
1. 处理B站视频（自动检测是否有字幕）
2. 处理音频文件（本地/URL，音频转写）
3. 总结现有的.md文件
4. 转写temp_audio中的音频文件
5. 查看历史记录
0. 退出
```

## 配置文件 (config.py)

```python
DEFAULT_SUMMARY_LEVEL = "detailed"       # 默认总结程度
DEFAULT_TRANSCRIBE_MODEL = "sensevoice"  # 默认转录模型
SUMMARY_PROMPTS = {...}                  # 三种总结提示词模板
CONTENT_TYPES = {...}                    # 内容类型关键词和提示词
```

历史记录管理函数：
- `add_history_record()` - 添加记录
- `get_recent_history()` - 获取最近记录
- `clear_history()` - 清空历史