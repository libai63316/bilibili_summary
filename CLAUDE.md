# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

B站视频字幕提取与LLM总结工具 - 从B站视频提取字幕或转写音频，然后使用Claude生成总结。

## 常用命令

### 运行
```bash
python main.py <B站视频URL>                    # 有字幕视频
python main.py --audio <音频下载链接>            # 无字幕视频（音频转写）
python main.py --summarize <md文件路径>         # 总结现有.md文件
python main.py --download <音频URL> [保存路径]  # 仅下载音频
python main.py --auto                          # 自动转写temp_audio中未处理的文件
python main.py --interactive                    # 交互模式
```

### 独立模块运行
```bash
python speech_to_text.py --download <音频URL>  # 下载音频
python speech_to_text.py --auto               # 扫描并自动转写未处理的文件
python speech_to_text.py <音频URL或本地文件>    # 转写音频
```

### 依赖安装
```bash
pip install -r requirements.txt
```

需要预先安装:
- `yt-dlp` - 视频/字幕下载
- `claude` CLI - Claude Code CLI工具（用于总结）

### 配置文件
在 `config.py` 中配置:
- `SILICONFLOW_API_KEY` - SiliconFlow API密钥（用于音频转写，非必须，有本地whisper备用）

## 代码架构

```
main.py              # 主入口，分发到4种模式
├── subtitle_extractor.py  # 使用yt-dlp提取B站字幕（支持ass/srt/vtt）
├── speech_to_text.py      # 音频转写：SiliconFlow API > 本地faster-whisper
└── summarizer.py          # 调用Claude Code CLI (claude -p) 生成总结
config.py            # 目录配置和API密钥
```

## 输出目录

- `temp_audio/` - 下载的临时音频文件（文件名与output/subtitles中的md文件一一对应）
- `temp_subs/` - yt-dlp临时字幕文件
- `output/subtitles/` - 提取/转写的字幕Markdown文件
- `output/summaries/` - Claude生成的总结文件

## 自动转写

`--auto` 命令会扫描 `temp_audio/` 目录：
- 音频文件（如 `audio_1234567890.mp3`）与 `output/subtitles/` 中的 `audio_1234567890.md` 一一对应
- 自动跳过已有md文件的音频
- 批量转写未处理的文件

## 核心流程

1. **字幕模式**: yt-dlp提取字幕 → 解析ass/srt/vtt → 保存md → Claude总结
2. **转写模式**: 下载音频 → SiliconFlow/Whisper转写 → 保存md → Claude总结
