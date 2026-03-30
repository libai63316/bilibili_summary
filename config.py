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
    elif duration > 300:
        return "detailed"
    return "normal"


# 内容类型及其关键词和特定提示词
CONTENT_TYPES = {
    "tutorial": {
        "name": "教程类",
        "keywords": ["教程", "教学", "如何", "怎么", "指南", "入门", "学习", "讲解", "手把手", "干货", "技巧", "方法", "步骤", "操作"],
        "prompt_suffix": "\n\n【内容类型提示】这是一个教程类视频，请保留所有步骤、要点、操作细节，按教学逻辑组织总结，让读者能按总结复现内容。"
    },
    "news": {
        "name": "新闻类",
        "keywords": ["新闻", "报道", "最新", "突发", "消息", "官方", "发布", "通知", "声明", "事件"],
        "prompt_suffix": "\n\n【内容类型提示】这是一个新闻类视频，请客观报道事实，保留时间、地点、人物、事件等关键信息，按新闻结构组织总结。"
    },
    "vlog": {
        "name": "Vlog/生活",
        "keywords": ["vlog", "日常", "生活", "记录", "分享", "旅行", "出游", "体验", "打卡", "探店"],
        "prompt_suffix": "\n\n【内容类型提示】这是一个Vlog/生活记录类视频，请保留作者的体验感受、情感表达、有趣细节和场景描述。"
    },
    "tech": {
        "name": "科技类",
        "keywords": ["科技", "数码", "评测", "手机", "电脑", "AI", "人工智能", "软件", "硬件", "新品", "芯片", "显卡", "处理器"],
        "prompt_suffix": "\n\n【内容类型提示】这是一个科技类视频，请保留产品参数、功能特点、对比数据、优缺点分析等技术细节。"
    },
    "finance": {
        "name": "财经类",
        "keywords": ["财经", "经济", "投资", "股票", "理财", "金融", "市场", "分析", "基金", "交易"],
        "prompt_suffix": "\n\n【内容类型提示】这是一个财经类视频，请保留数据、趋势分析、投资建议等专业信息，注意区分事实和观点。"
    },
    "entertainment": {
        "name": "娱乐类",
        "keywords": ["搞笑", "娱乐", "综艺", "游戏", "电影", "动漫", "音乐", "吐槽", "段子", "梗"],
        "prompt_suffix": "\n\n【内容类型提示】这是一个娱乐类视频，请保留有趣的情节、梗点、笑点，让总结也能带来阅读乐趣。"
    },
    "knowledge": {
        "name": "知识科普",
        "keywords": ["科普", "知识", "历史", "科学", "原理", "揭秘", "解析", "冷知识", "涨知识"],
        "prompt_suffix": "\n\n【内容类型提示】这是一个知识科普类视频，请保留知识点、原理解释、科学依据，按知识结构组织总结。"
    }
}


def detect_content_type(title):
    """
    根据视频标题识别内容类型

    Args:
        title: 视频标题

    Returns:
        str: 内容类型键名，未识别返回 "general"
    """
    if not title:
        return "general"

    title_lower = title.lower()
    for type_name, type_info in CONTENT_TYPES.items():
        for keyword in type_info["keywords"]:
            if keyword in title_lower:
                return type_name

    return "general"


def get_content_type_prompt_suffix(content_type):
    """
    获取内容类型对应的提示词补充

    Args:
        content_type: 内容类型键名

    Returns:
        str: 提示词补充内容，未知类型返回空字符串
    """
    if content_type in CONTENT_TYPES:
        return CONTENT_TYPES[content_type]["prompt_suffix"]
    return ""


def get_content_type_name(content_type):
    """
    获取内容类型的中文名称

    Args:
        content_type: 内容类型键名

    Returns:
        str: 中文名称
    """
    if content_type in CONTENT_TYPES:
        return CONTENT_TYPES[content_type]["name"]
    return "通用"
