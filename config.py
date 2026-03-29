# -*- coding: utf-8 -*-
# @auth: ljz
# @date: 2026-03-29
# 配置文件

import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 输出目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
SUBTITLES_DIR = os.path.join(OUTPUT_DIR, "subtitles")
SUMMARIES_DIR = os.path.join(OUTPUT_DIR, "summaries")

# 音频文件临时目录
TEMP_AUDIO_DIR = os.path.join(PROJECT_ROOT, "temp_audio")

# 确保目录存在的函数
def ensure_directories():
    """确保所有必要目录存在，不存在则创建"""
    for directory in [OUTPUT_DIR, SUBTITLES_DIR, SUMMARIES_DIR, TEMP_AUDIO_DIR]:
        os.makedirs(directory, exist_ok=True)

# 初始化时确保目录存在
ensure_directories()

# Claude总结提示词模板
SUMMARY_PROMPTS = {
    "brief": """你是一个专业的视频内容总结助手。请简洁总结以下视频字幕内容。

要求：
- 提取最核心的1-3个要点
- 每点用简短的话概括
- 总字数控制在150字以内
- 不要遗漏视频的核心观点
- 请直接输出总结内容，不要提问，不要询问用户任何问题

视频字幕内容如下：
""",
    "normal": """你是一个专业的视频内容总结助手，同时也是一个有独立思考能力的评论者。请全面总结以下视频字幕/转写内容，并加入你自己的思考和见解。

请按以下结构输出总结：
1. 视频主题（1-2句话概括视频的主要内容）
2. 关键要点（列出3-5个核心观点，每个观点用1-2句话说明）
3. 重要细节（如果有具体的步骤、列表、数据、案例等，尽量保留）
4. 你的思考与见解（对这个内容的分析、评价或延伸思考）

要求：
- 总结要完整，不要遗漏重要信息，字数控制在500字以内
- 请直接输出总结内容，不要提问，不要询问用户任何问题
- 你的思考部分要真诚、有深度

视频字幕内容如下：
""",
    "detailed": """你是一个专业的视频内容总结助手，同时也是一个有独立思考能力的评论者。请尽可能完整、详细地总结视频字幕内容，并加入你自己的思考和见解。

重要原则：
1. 保留字幕中的所有信息，不要遗漏任何细节
2. 按照视频的原有逻辑结构进行总结
3. 重要的时间点、数据、案例、引用等都要保留
4. 如果视频有多个话题或章节，请按章节分别总结
5. UP主的观点、评论、情感态度等也要保留
6. 在总结的基础上，给出你对这个内容的分析、评价和见解

请按以下结构输出详细总结：
1. 视频主题与背景
2. 章节/话题划分（如有）
3. 各章节详细内容（逐段总结，保留所有要点）
4. 关键数据、案例、引用（原文保留）
5. UP主观点与态度
6. 视频总结与结论
7. 你的思考与见解（对这个视频内容的分析、评价、延伸思考）

要求：
- 字数无限制，尽可能完整详细
- 请直接输出总结内容，不要提问，不要询问用户任何问题
- 你的思考部分要真诚、有深度，不要泛泛而谈

视频字幕内容如下：
"""
}

# 默认总结程度：brief(简洁), normal(中等), detailed(详细)
DEFAULT_SUMMARY_LEVEL = "detailed"

# 默认转录模型: sensevoice, whisper, siliconflow
DEFAULT_TRANSCRIBE_MODEL = "sensevoice"

# 可用转录模型
AVAILABLE_TRANSCRIBE_MODELS = {
    "sensevoice": "SenseVoice (FunASR) - 中文识别效果好",
    "whisper": "Whisper (faster-whisper) - 英文支持好",
    "siliconflow": "SiliconFlow API - 云端转写，需API Key"
}


def auto_select_summary_level(duration):
    """
    根据视频时长智能选择总结力度

    Args:
        duration: 视频时长（秒）

    Returns:
        str: "brief", "normal", 或 "detailed"
    """
    if duration < 60:
        return "brief"
    elif duration > 600:
        return "detailed"
    return "normal"
