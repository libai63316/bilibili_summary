# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this codebase.

## 项目概述

B站视频字幕提取与LLM总结工具 - 从B站视频提取字幕或转写音频，然后使用Claude Code CLI生成总结。

## 常用命令

### 运行
```bash
python main.py <B站视频URL>                    # 自动检测字幕，无字幕时自动转写音频
python main.py --audio <音频URL或B站URL>       # 强制使用音频转写模式
python main.py --audio <URL> --model whisper   # 指定Whisper模型转写
python main.py --summarize <md文件路径>        # 仅总结现有.md文件（不传路径则自动扫描未总结文件）
python main.py --download <音频URL> [保存路径] # 仅下载音频
python main.py --auto                          # 自动转写temp_audio中未处理的文件
python main.py --interactive                   # 交互模式
```

### 独立模块运行
```bash
python speech_to_text.py --download <音频URL>  # 下载音频
python speech_to_text.py --auto               # 扫描并自动转写未处理的文件
python speech_to_text.py <音频URL或本地文件>   # 转写音频
python subtitle_extractor.py                  # 测试字幕提取（交互输入URL）
python summarizer.py                          # 交互式总结
```

### 依赖安装
```bash
pip install -r requirements.txt
```

需要预先安装:
- `yt-dlp` - 视频/字幕下载（支持B站WBI签名）
- `claude` CLI - Claude Code CLI工具（用于总结）

ffmpeg无需单独安装，项目使用 `imageio-ffmpeg` 内置的二进制文件。

## 代码架构

```
main.py              # 主入口，命令行参数解析 + 交互模式
├── handle_video_with_subtitle()     # 有字幕视频处理（自动降级到音频转写）
├── handle_video_without_subtitle()  # 无字幕视频处理（音频转写）
├── handle_summarize_only()          # 仅总结（支持自动扫描未总结文件）
└── interactive_mode()               # 交互菜单

subtitle_extractor.py    # yt-dlp提取B站字幕 → 解析ass/srt/vtt → 保存md
speech_to_text.py        # 音频转写模块：
│   ├── transcribe_with_sensevoice()     # FunASR/SenseVoice（中文效果好）
│   ├── transcribe_with_whisper_local()  # faster-whisper（英文支持好）
│   └── transcribe_with_siliconflow()    # SiliconFlow API（云端）
└── download_audio_from_bilibili()       # yt-dlp下载B站音频

summarizer.py          # 调用 claude -p @file 生成总结
config.py              # 目录配置、总结提示词模板、默认设置
```

## 核心流程

1. **自动模式**: yt-dlp探测字幕 → 有字幕则提取 → 无字幕自动降级到音频转写 → Claude总结
2. **音频转写**: yt-dlp下载音频 → SenseVoice/Whisper转写 → 保存md → Claude总结
3. **仅总结**: 读取md → Claude生成总结 → 保存到summaries目录

## 智能总结力度

根据视频时长自动选择总结程度（config.py: `auto_select_summary_level()`）：
- `< 1分钟` → brief（150字以内，核心要点）
- `1-10分钟` → normal（500字以内，标准总结）
- `> 10分钟` → detailed（完整详细，无字数限制）

## 转录模型选择

| 模型 | 适用场景 | 说明 |
|------|----------|------|
| sensevoice | 中文为主 | FunASR/SenseVoiceSmall，默认选项 |
| whisper | 英文为主 | faster-whisper base模型 |
| siliconflow | 云端 | 需配置SILICONFLOW_API_KEY |

长音频（>5分钟）自动分段处理，避免GPU显存不足。

## 输出目录

- `temp_audio/` - 下载的临时音频文件
- `temp_subs/` - yt-dlp临时字幕文件（处理后清理）
- `output/subtitles/` - 提取/转写的字幕Markdown文件
- `output/summaries/` - Claude生成的总结文件（文件名: `原名_summary.md`）

## 配置文件 (config.py)

```python
DEFAULT_SUMMARY_LEVEL = "detailed"    # 默认总结程度
DEFAULT_TRANSCRIBE_MODEL = "sensevoice"  # 默认转录模型
SUMMARY_PROMPTS = {...}               # 三种总结提示词模板
```

如需使用SiliconFlow云端转写，需在config.py中添加 `SILICONFLOW_API_KEY`。

## 交互模式菜单

```
1. 处理B站视频（自动检测是否有字幕）
2. 处理音频文件（本地/URL，音频转写）
3. 总结现有的.md文件
4. 转写temp_audio中的音频文件
0. 退出
```
