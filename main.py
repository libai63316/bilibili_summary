# -*- coding: utf-8 -*-
# @auth: ljz
# @date: 2026-03-29
# 主程序入口 - B站视频字幕提取与总结

import sys
import os
import glob
import subprocess
import time  # @auth: ljz @date: 2026-03-30 添加计时功能
import threading  # @auth: ljz @date: 2026-03-31 添加多线程支持

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import subtitle_extractor
import speech_to_text
import summarizer
import logger  # @auth: ljz @date: 2026-03-30 添加日志模块


def open_file(path):
    """
    用默认程序打开文件（完成后自动打开总结文件）

    Args:
        path: 文件路径
    """
    if not os.path.exists(path):
        print(f"[警告] 文件不存在: {path}")
        return

    try:
        # Windows: 使用默认程序打开文件
        if sys.platform == 'win32':
            os.startfile(path)
        # macOS: 使用 open 命令
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        # Linux: 使用 xdg-open
        else:
            subprocess.run(['xdg-open', path])
        print(f"[自动打开] 已打开: {path}")
    except Exception as e:
        print(f"[警告] 无法自动打开文件: {e}")


def print_banner():
    """打印横幅"""
    print("=" * 60)
    print("  B站视频字幕提取与LLM总结工具")
    print("  Bilibili Video Subtitle Extractor & Summarizer")
    print("=" * 60)
    print()


def print_usage():
    """打印使用说明"""
    print("使用方法:")
    print("  1. 处理视频: python main.py <视频URL>")
    print("     - B站视频: 自动检测字幕，无字幕则转写音频")
    print("     - 小红书视频: 自动下载音频转写")
    print("  2. 音频转写: python main.py --audio <音频下载链接> [--model <模型>]")
    print("  3. 仅总结现有.md: python main.py --summarize <md文件路径>")
    print("  4. 交互模式: python main.py --interactive")
    print("  5. 下载音频: python main.py --download <音频下载链接> [保存路径]")
    print("  6. 自动转写: python main.py --auto  (扫描temp_audio转写未处理的文件)")
    print("  7. 查看历史: python main.py --history [数量]  (查看最近处理记录)")
    print("  8. 清空历史: python main.py --clear-history")
    print()
    print("支持平台:")
    print("  - B站 (bilibili.com, b23.tv)")
    print("  - 小红书 (xiaohongshu.com, xhslink.com)")
    print()
    print("可选转录模型:")
    print("  sensevoice - SenseVoice (FunASR) 中文识别效果好（默认）")
    print("  whisper    - Whisper (faster-whisper) 英文支持好")
    print()
    print("配置:")
    print("  请在 config.py 中配置您的阿里云AccessKey")
    print()


# @auth: ljz @date: 2026-03-31 提取公共函数，减少重复代码
def _get_video_info_and_config(url, summary_level=None):
    """
    获取视频信息并确定处理配置（公共函数）

    Args:
        url: 视频URL
        summary_level: 用户指定的总结程度（可选）

    Returns:
        dict: {
            'video_title': str,
            'video_duration': int,
            'video_uploader': str,
            'content_type': str,
            'auto_summary_level': str or None,
            'summary_level': str,
            'prompt': str
        }
    """
    video_info = speech_to_text.get_bilibili_video_info(url)
    auto_summary_level = None
    content_type = "general"
    video_title = ""
    video_duration = 0
    video_uploader = ""

    if video_info:
        video_duration = video_info.get('duration', 0)
        video_title = video_info.get('title', '')
        video_uploader = video_info.get('uploader', '')
        logger.log_video_info(video_title, video_duration, video_uploader, url)

        if video_duration > 0:
            auto_summary_level = config.auto_select_summary_level(video_duration)
            minutes = video_duration // 60
            seconds = video_duration % 60
            print(f"[主流程] 视频时长: {minutes}分{seconds}秒")
            print(f"[主流程] 智能推荐总结程度: {auto_summary_level}")
            logger.log_info(f"智能推荐总结程度: {auto_summary_level}")

            # 如果用户未指定总结程度，使用智能推荐
            if summary_level is None:
                summary_level = auto_summary_level

        # 识别内容类型
        if video_title:
            content_type = config.detect_content_type(video_title)
            if content_type != "general":
                content_type_name = config.get_content_type_name(content_type)
                print(f"[主流程] 智能识别内容类型: {content_type_name}")
                logger.log_info(f"智能识别内容类型: {content_type_name}")

    # 获取总结提示词
    if summary_level is None:
        summary_level = config.DEFAULT_SUMMARY_LEVEL
    prompt = config.SUMMARY_PROMPTS.get(summary_level, config.SUMMARY_PROMPTS["normal"])

    # 根据内容类型追加特定提示
    prompt += config.get_content_type_prompt_suffix(content_type)

    return {
        'video_title': video_title,
        'video_duration': video_duration,
        'video_uploader': video_uploader,
        'content_type': content_type,
        'auto_summary_level': auto_summary_level,
        'summary_level': summary_level,
        'prompt': prompt
    }


def _finalize_processing(video_title, video_url, video_duration, video_uploader,
                         content_type, md_path, summary_result, start_time,
                         transcribe_mode=False):
    """
    统一完成处理流程（公共函数）

    Args:
        video_title: 视频标题
        video_url: 视频URL
        video_duration: 视频时长
        video_uploader: UP主
        content_type: 内容类型
        md_path: 字幕/转写文件路径
        summary_result: 总结结果字典
        start_time: 开始时间（用于计算耗时）
        transcribe_mode: 是否为转写模式

    Returns:
        bool: True
    """
    logger.log_info(f"处理完成: {video_title}")
    print("=" * 60)
    print("处理完成!")
    print("=" * 60)

    if transcribe_mode:
        print(f"转写文件: {md_path}")
    else:
        print(f"字幕文件: {md_path}")
    print(f"总结文件: {summary_result['summary_path']}")
    print()
    print("总结内容:")
    print("-" * 60)
    print(summary_result['summary'])

    # 添加历史记录
    config.add_history_record(
        title=video_title,
        url=video_url,
        duration=video_duration,
        uploader=video_uploader,
        content_type=content_type,
        subtitle_path=md_path,
        summary_path=summary_result['summary_path']
    )

    # 自动打开总结文件
    open_file(summary_result['summary_path'])

    # 显示总耗时
    elapsed = time.time() - start_time
    print(f"[完成] 总耗时: {int(elapsed // 60)}分{int(elapsed % 60)}秒")

    return True


def handle_video_with_subtitle(url, summary_level=None):
    """
    处理有字幕的视频（支持自动模式：无字幕时自动切换到音频转写）

    Args:
        url: B站视频URL
        summary_level: 总结程度 ("brief", "normal", "detailed")
    """
    # @auth: ljz @date: 2026-03-30 添加计时功能
    start_time = time.time()

    # @auth: ljz @date: 2026-03-30 添加日志记录
    logger.log_info(f"开始处理视频: {url}")

    # @auth: ljz @date: 2026-03-31 使用公共函数获取视频信息和配置
    info = _get_video_info_and_config(url, summary_level)
    video_title = info['video_title']
    video_duration = info['video_duration']
    video_uploader = info['video_uploader']
    content_type = info['content_type']
    summary_level = info['summary_level']
    prompt = info['prompt']

    print(f"[主流程] 模式: 有字幕视频")
    print(f"[主流程] 视频URL: {url}")
    print(f"[主流程] 总结程度: {summary_level}")
    logger.log_info(f"处理模式: 有字幕视频, 总结程度: {summary_level}")
    print()

    # Step 1: 提取字幕
    logger.log_step(1, "提取字幕")
    print("[Step 1/3] 提取字幕...")
    result = subtitle_extractor.extract_subtitles(url)

    if not result['success']:
        logger.log_error(f"字幕提取失败: {result['message']}")
        print(f"[错误] {result['message']}")
        return False

    # 自动模式：无字幕时自动切换到音频转写
    if not result['has_subtitle']:
        logger.log_info("视频无字幕，自动切换到音频转写模式")
        print("[自动模式] 该视频无字幕，将自动切换到音频转写模式...")
        print()

        # 下载音频
        print("[Step 1/3] 正在下载音频...")
        try:
            audio_path = speech_to_text.download_audio_from_bilibili(url, video_title)
            logger.log_info(f"音频下载完成: {audio_path}")

            # 继续使用音频转写流程
            return handle_video_without_subtitle_process(
                audio_path=audio_path,
                video_name=video_title,
                summary_level=summary_level,
                transcribe_model=config.DEFAULT_TRANSCRIBE_MODEL,
                video_url=url,
                video_duration=video_duration,
                video_uploader=video_uploader
            )
        except Exception as e:
            logger.log_error(f"自动模式切换失败: {e}")
            print(f"[错误] 自动模式切换失败: {e}")
            return False

    md_path = result['subtitle_path']
    logger.log_info(f"字幕提取完成: {md_path}")
    print(f"[Step 1/3] 完成: {md_path}")
    print()

    # Step 2: Claude总结
    logger.log_step(2, "Claude Code总结")
    print(f"[Step 2/3] 正在使用Claude Code总结 (程度: {summary_level})...")
    summary_result = summarizer.summarize_with_claude(md_path, prompt=prompt)

    if not summary_result['success']:
        logger.log_error(f"总结失败: {summary_result['message']}")
        print(f"[错误] {summary_result['message']}")
        return False

    logger.log_info(f"总结完成: {summary_result['summary_path']}")
    print(f"[Step 2/3] 完成: {summary_result['summary_path']}")
    print()

    # @auth: ljz @date: 2026-03-31 使用公共函数完成处理流程
    return _finalize_processing(
        video_title=video_title,
        video_url=url,
        video_duration=video_duration,
        video_uploader=video_uploader,
        content_type=content_type,
        md_path=md_path,
        summary_result=summary_result,
        start_time=start_time,
        transcribe_mode=False
    )


def handle_video_without_subtitle_process(audio_path, video_name=None, summary_level=None,
                                          transcribe_model=None, video_url=None, video_duration=None,
                                          video_uploader=None):
    """
    处理音频文件的通用函数（转写+总结）

    Args:
        audio_path: 音频文件路径
        video_name: 视频名称
        summary_level: 总结程度 ("brief", "normal", "detailed")
        transcribe_model: 转录模型
        video_url: 视频URL
        video_duration: 时长（秒）
        video_uploader: UP主

    Returns:
        bool: 处理是否成功
    """
    # @auth: ljz @date: 2026-03-30 添加计时功能
    start_time = time.time()

    # 获取总结提示词
    if summary_level is None:
        summary_level = config.DEFAULT_SUMMARY_LEVEL
    prompt = config.SUMMARY_PROMPTS.get(summary_level, config.SUMMARY_PROMPTS["normal"])

    # 识别内容类型
    content_type = "general"
    if video_name:
        content_type = config.detect_content_type(video_name)
        if content_type != "general":
            print(f"[主流程] 智能识别内容类型: {config.get_content_type_name(content_type)}")

    # 根据内容类型追加特定提示
    prompt += config.get_content_type_prompt_suffix(content_type)

    # 获取转录模型
    if transcribe_model is None:
        transcribe_model = config.DEFAULT_TRANSCRIBE_MODEL

    print(f"[主流程] 模式: 音频转写")
    if video_name:
        print(f"[主流程] 视频名称: {video_name}")
    print(f"[主流程] 总结程度: {summary_level}")
    print(f"[主流程] 转录模型: {transcribe_model}")
    print()

    # Step 1: 转写音频
    print("[Step 1/3] 正在转写音频...")
    result = speech_to_text.transcribe_audio(
        audio_path,
        video_name=video_name,
        model=transcribe_model,
        video_url=video_url,
        duration=video_duration,
        uploader=video_uploader,
        content_type=content_type
    )

    if not result['success']:
        print(f"[错误] {result['message']}")
        return False

    md_path = result['md_path']
    print(f"[Step 1/3] 完成: {md_path}")
    print()

    # Step 2: Claude总结
    print(f"[Step 2/3] 正在使用Claude Code总结 (程度: {summary_level})...")
    summary_result = summarizer.summarize_with_claude(md_path, prompt=prompt)

    if not summary_result['success']:
        print(f"[错误] {summary_result['message']}")
        return False

    print(f"[Step 2/3] 完成: {summary_result['summary_path']}")
    print()

    # @auth: ljz @date: 2026-03-31 使用公共函数完成处理流程
    return _finalize_processing(
        video_title=video_name or "",
        video_url=video_url,
        video_duration=video_duration or 0,
        video_uploader=video_uploader or "",
        content_type=content_type,
        md_path=md_path,
        summary_result=summary_result,
        start_time=start_time,
        transcribe_mode=True
    )


def handle_video_without_subtitle(audio_url, summary_level=None, transcribe_model=None):
    """
    处理无字幕视频（需要音频转写）

    Args:
        audio_url: 音频下载链接
        summary_level: 总结程度 ("brief", "normal", "detailed")
        transcribe_model: 转录模型 (None/sensevoice/whisper/siliconflow)
    """
    # @auth: ljz @date: 2026-03-30 添加计时功能
    start_time = time.time()

    # @auth: ljz @date: 2026-03-31 使用公共函数获取视频信息和配置（仅B站URL）
    video_title = ""
    video_duration = 0
    video_uploader = ""
    content_type = "general"

    # 判断是否是B站URL，获取视频信息
    if speech_to_text.is_bilibili_url(audio_url):
        info = _get_video_info_and_config(audio_url, summary_level)
        video_title = info['video_title']
        video_duration = info['video_duration']
        video_uploader = info['video_uploader']
        content_type = info['content_type']
        summary_level = info['summary_level']
        prompt = info['prompt']
    else:
        # 非B站URL，使用默认配置
        if summary_level is None:
            summary_level = config.DEFAULT_SUMMARY_LEVEL
        prompt = config.SUMMARY_PROMPTS.get(summary_level, config.SUMMARY_PROMPTS["normal"])

    # 获取转录模型
    if transcribe_model is None:
        transcribe_model = config.DEFAULT_TRANSCRIBE_MODEL

    print(f"[主流程] 模式: 无字幕视频（音频转写）")
    print(f"[主流程] 音频链接: {audio_url}")
    print(f"[主流程] 总结程度: {summary_level}")
    print(f"[主流程] 转录模型: {transcribe_model}")
    print()

    # Step 1: 下载音频并转写
    print("[Step 1/3] 下载音频并转写...")
    result = speech_to_text.transcribe_audio(
        audio_url,
        model=transcribe_model,
        video_url=audio_url if speech_to_text.is_bilibili_url(audio_url) else None,
        duration=video_duration,
        uploader=video_uploader,
        content_type=content_type
    )

    if not result['success']:
        print(f"[错误] {result['message']}")
        return False

    md_path = result['md_path']
    print(f"[Step 1/3] 完成: {md_path}")
    print()

    # Step 2: Claude总结
    print(f"[Step 2/3] 正在使用Claude Code总结 (程度: {summary_level})...")
    summary_result = summarizer.summarize_with_claude(md_path, prompt=prompt)

    if not summary_result['success']:
        print(f"[错误] {summary_result['message']}")
        return False

    print(f"[Step 2/3] 完成: {summary_result['summary_path']}")
    print()

    # @auth: ljz @date: 2026-03-31 使用公共函数完成处理流程
    return _finalize_processing(
        video_title=video_title,
        video_url=audio_url if speech_to_text.is_bilibili_url(audio_url) else None,
        video_duration=video_duration,
        video_uploader=video_uploader,
        content_type=content_type,
        md_path=md_path,
        summary_result=summary_result,
        start_time=start_time,
        transcribe_mode=True
    )


def find_unsummarized_files():
    """
    扫描字幕文件夹，找出未总结的文件

    Returns:
        list: 未总结的字幕文件路径列表
    """
    # 确保目录存在
    config.ensure_directories()

    # 获取所有字幕文件
    subtitle_files = glob.glob(os.path.join(config.SUBTITLES_DIR, "*.md"))

    # 获取已总结的文件基础名
    summary_files = glob.glob(os.path.join(config.SUMMARIES_DIR, "*_summary.md"))
    summarized_bases = set()
    for s in summary_files:
        # 从summary文件名提取对应的subtitle文件名
        basename = os.path.basename(s)
        # audio_xxx_summary.md -> audio_xxx
        if basename.endswith("_summary.md"):
            base = basename[:-len("_summary.md")]
            summarized_bases.add(base)

    # 找出未总结的文件
    unsummarized = []
    for sub_file in subtitle_files:
        basename = os.path.basename(sub_file)
        name_without_ext = os.path.splitext(basename)[0]
        if name_without_ext not in summarized_bases:
            unsummarized.append(sub_file)

    return unsummarized


def find_untranscribed_audio():
    """
    扫描temp_audio目录，找出未转写的音频文件

    Returns:
        list: 未转写的音频文件路径列表
    """
    # 确保目录存在
    config.ensure_directories()

    # 获取所有音频文件
    audio_extensions = ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.flac', '*.ogg']
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(glob.glob(os.path.join(config.TEMP_AUDIO_DIR, ext)))

    # 获取已转写的字幕文件基础名
    subtitle_files = glob.glob(os.path.join(config.SUBTITLES_DIR, "*.md"))
    transcribed_bases = set()
    for sub_file in subtitle_files:
        # 去掉扩展名得到基础名
        basename = os.path.splitext(os.path.basename(sub_file))[0]
        transcribed_bases.add(basename)

    # 找出未转写的音频（匹配字幕文件名）
    untranscribed = []
    for audio_path in audio_files:
        audio_basename = os.path.splitext(os.path.basename(audio_path))[0]
        if audio_basename not in transcribed_bases:
            untranscribed.append(audio_path)

    return untranscribed


def handle_transcribe_audio_files(transcribe_model=None):
    """
    处理temp_audio目录中未转写的音频文件

    Args:
        transcribe_model: 转录模型 (None/sensevoice/whisper/siliconflow)
    """
    # 获取转录模型
    if transcribe_model is None:
        transcribe_model = config.DEFAULT_TRANSCRIBE_MODEL

    print(f"[主流程] 模式: 转写temp_audio中的音频文件")
    print(f"[主流程] 转录模型: {transcribe_model}")
    print()

    untranscribed = find_untranscribed_audio()

    if not untranscribed:
        print("[提示] 所有音频文件都已转写，无需处理")
        return True

    print(f"[扫描] 发现 {len(untranscribed)} 个未转写的音频文件")
    print()

    # 询问视频名称（统一用于所有本次音频）
    video_name = input("请输入视频名称（用于命名，直接回车跳过）: ").strip()

    success_count = 0
    fail_count = 0

    for audio_path in untranscribed:
        print(f"[转写] {os.path.basename(audio_path)}")
        result = speech_to_text.transcribe_audio(audio_path, video_name=video_name if video_name else None, model=transcribe_model)

        if result['success']:
            print(f"[完成] -> {os.path.basename(result['md_path'])}")
            success_count += 1
        else:
            print(f"[失败] {result['message']}")
            fail_count += 1
        print()

    print("=" * 60)
    print(f"转写完成! 成功: {success_count}, 失败: {fail_count}")
    print("=" * 60)
    return fail_count == 0


def handle_summarize_only(md_path=None, summary_level=None):
    """
    仅总结现有的.md文件，或自动总结所有未总结的文件

    Args:
        md_path: Markdown文件路径，如果为None则自动扫描未总结的文件
        summary_level: 总结程度 ("brief", "normal", "detailed")
    """
    # @auth: ljz @date: 2026-03-30 添加计时功能
    start_time = time.time()

    # 获取提示词
    if summary_level is None:
        summary_level = config.DEFAULT_SUMMARY_LEVEL

    prompt = config.SUMMARY_PROMPTS.get(summary_level, config.SUMMARY_PROMPTS["normal"])

    if md_path is None:
        # 自动扫描未总结的文件
        print(f"[主流程] 模式: 自动总结未总结的字幕文件")
        print()

        unsummarized = find_unsummarized_files()

        if not unsummarized:
            print("[提示] 所有字幕文件都已总结，无需处理")
            return True

        print(f"[扫描] 发现 {len(unsummarized)} 个未总结的字幕文件")
        print()

        success_count = 0
        fail_count = 0

        for sub_file in unsummarized:
            print(f"[总结] {os.path.basename(sub_file)} (程度: {summary_level})")
            result = summarizer.summarize_with_claude(sub_file, prompt=prompt)

            if result['success']:
                print(f"[完成] -> {os.path.basename(result['summary_path'])}")
                success_count += 1
            else:
                print(f"[失败] {result['message']}")
                fail_count += 1
            print()

        print("=" * 60)
        print(f"总结完成! 成功: {success_count}, 失败: {fail_count}")
        # @auth: ljz @date: 2026-03-30 显示总耗时
        elapsed = time.time() - start_time
        print(f"[完成] 总耗时: {int(elapsed // 60)}分{int(elapsed % 60)}秒")
        print("=" * 60)
        return fail_count == 0

    # 总结指定的单个文件
    print(f"[主流程] 模式: 仅总结.md文件")
    print(f"[主流程] 文件路径: {md_path}")
    print()

    # 验证文件存在
    if not os.path.exists(md_path):
        # 尝试在项目目录中查找
        full_path = os.path.join(config.SUBTITLES_DIR, os.path.basename(md_path))
        if os.path.exists(full_path):
            md_path = full_path
        else:
            print(f"[错误] 文件不存在: {md_path}")
            return False

    # 总结
    print(f"[Step 1/2] 正在使用Claude Code总结 (程度: {summary_level})...")
    result = summarizer.summarize_with_claude(md_path, prompt=prompt)

    if not result['success']:
        print(f"[错误] {result['message']}")
        return False

    print(f"[Step 1/2] 完成: {result['summary_path']}")
    print()
    # 完成
    print("=" * 60)
    print("总结完成!")
    print("=" * 60)
    print(f"源文件: {md_path}")
    print(f"总结文件: {result['summary_path']}")
    print()
    print("总结内容:")
    print("-" * 60)
    print(result['summary'])

    # 自动打开总结文件
    open_file(result['summary_path'])

    # @auth: ljz @date: 2026-03-30 显示总耗时
    elapsed = time.time() - start_time
    print(f"[完成] 总耗时: {int(elapsed // 60)}分{int(elapsed % 60)}秒")

    return True


def show_history(limit=20):
    """
    显示历史记录

    Args:
        limit: 显示记录数量
    """
    history = config.get_recent_history(limit)

    if not history:
        print("[历史记录] 暂无记录")
        return

    print(f"[历史记录] 最近 {len(history)} 条记录:")
    print("=" * 70)
    for i, record in enumerate(history, 1):
        title = record.get('title', '未知标题')
        duration = record.get('duration', 0)
        mins = duration // 60
        secs = duration % 60
        uploader = record.get('uploader', '')
        content_type = record.get('content_type', '')
        process_time = record.get('process_time', '')
        summary_path = record.get('summary_path', '')

        print(f"{i}. {title}")
        if uploader:
            print(f"   UP主: {uploader}")
        if duration:
            print(f"   时长: {mins}分{secs}秒")
        if content_type and content_type != "general":
            type_name = config.get_content_type_name(content_type)
            print(f"   类型: {type_name}")
        print(f"   时间: {process_time}")
        if summary_path:
            print(f"   总结: {summary_path}")
        print()

    print("=" * 70)


# @auth: ljz @date: 2026-03-31 添加交互模式辅助函数
def _select_summary_level(default_level="detailed"):
    """
    交互式选择总结程度

    Args:
        default_level: 默认总结程度

    Returns:
        str: 选择的总结程度
    """
    print("请选择总结程度:")
    print("  1. 简洁 - 核心要点概述")
    print("  2. 中等 - 标准总结")
    print(f"  3. 详细 - 保留完整细节（默认）")
    print()

    try:
        choice = input("请输入选项 (1-3): ").strip()
    except EOFError:
        choice = ""

    if choice == '1':
        return "brief"
    elif choice == '2':
        return "normal"
    else:
        return default_level


def _select_transcribe_model():
    """
    交互式选择转录模型

    Returns:
        str or None: 选择的转录模型
    """
    print("请选择转录模型:")
    print("  1. SenseVoice（中文效果好，默认）")
    print("  2. Whisper（英文支持好）")
    print()

    try:
        choice = input("请输入选项 (1-2, 默认1): ").strip()
    except EOFError:
        choice = ""

    return "whisper" if choice == '2' else None


def interactive_mode():
    """
    交互模式
    @auth: ljz
    @date: 2026-03-30 支持直接粘贴链接
    @date: 2026-03-31 支持小红书链接，添加异常捕获
    """
    print("[交互模式] 欢迎使用视频字幕提取与总结工具")
    print("支持平台：B站、小红书")
    print()

    while True:
        try:
            print("请选择操作:")
            print("  1. 处理B站视频（自动检测是否有字幕）")
            print("  2. 处理小红书视频（音频转写）")
            print("  3. 处理其他音频文件（本地/URL，音频转写）")
            print("  4. 总结现有的视频字幕.md文件")
            print("  5. 转写temp_audio中的音频文件")
            print("  6. 查看历史记录")
            print("  0. 退出")
            print()

            choice = input("请输入选项 (0-6) 或直接粘贴视频链接: ").strip()

            # 检测是否是链接（支持粘贴带前缀的文本）
            # @auth: ljz @date: 2026-03-30
            url = speech_to_text.extract_url(choice)
            if url:
                # 直接处理链接
                print()
                print(f"[提示] 检测到链接，自动处理...")
                if speech_to_text.is_bilibili_url(url):
                    # @auth: ljz @date: 2026-03-31 直接下载音频转写，转写完再选总结力度
                    start_time = time.time()  # @auth: ljz @date: 2026-03-31 添加计时

                    # 获取视频信息
                    video_info = speech_to_text.get_bilibili_video_info(url)
                    video_title = video_info.get('title', '') if video_info else ''
                    video_duration = video_info.get('duration', 0) if video_info else 0
                    video_uploader = video_info.get('uploader', '') if video_info else ''

                    if video_info and video_duration > 0:
                        minutes = int(video_duration // 60)
                        seconds = int(video_duration % 60)
                        print(f"[信息] 视频时长: {minutes}分{seconds}秒")

                    # 下载音频
                    print("[处理中] 正在下载音频...")
                    try:
                        audio_path = speech_to_text.download_audio_from_bilibili(url, video_title)
                    except Exception as e:
                        print(f"[错误] 音频下载失败: {e}")
                        continue

                    # 转写
                    print("[处理中] 正在转写...")
                    transcribe_result = speech_to_text.transcribe_audio(
                        audio_path,
                        video_name=video_title,
                        model=config.DEFAULT_TRANSCRIBE_MODEL,
                        video_url=url,
                        duration=video_duration,
                        uploader=video_uploader
                    )

                    if not transcribe_result.get('success'):
                        print(f"[错误] {transcribe_result.get('message', '转写失败')}")
                        continue

                    md_path = transcribe_result['md_path']
                    print(f"[完成] 转写完成")

                    # 选择总结力度
                    auto_summary_level = config.auto_select_summary_level(video_duration) if video_duration > 0 else "detailed"
                    print()
                    print("请选择总结程度:")
                    print("  1. 简洁 - 核心要点概述")
                    print("  2. 中等 - 标准总结")
                    print(f"  3. 详细 - 保留完整细节（智能推荐: {auto_summary_level}）")
                    print()

                    try:
                        level_choice = input("请输入选项 (1-3): ").strip()
                    except EOFError:
                        level_choice = ""

                    if level_choice == '1':
                        summary_level = "brief"
                    elif level_choice == '2':
                        summary_level = "normal"
                    elif level_choice == '3':
                        summary_level = "detailed"
                    else:
                        summary_level = auto_summary_level

                    # 总结
                    content_type = config.detect_content_type(video_title) if video_title else 'general'
                    prompt = config.SUMMARY_PROMPTS.get(summary_level, config.SUMMARY_PROMPTS["normal"])
                    prompt += config.get_content_type_prompt_suffix(content_type)

                    print()
                    print(f"[总结] 正在使用Claude Code总结...")
                    summary_result = summarizer.summarize_with_claude(md_path, prompt=prompt)

                    if summary_result['success']:
                        print(f"[完成] 总结已保存")
                        print()
                        print("总结内容:")
                        print("-" * 60)
                        print(summary_result['summary'])
                        open_file(summary_result['summary_path'])

                        # 添加历史记录
                        config.add_history_record(
                            title=video_title,
                            url=url,
                            duration=video_duration,
                            uploader=video_uploader,
                            content_type=content_type,
                            subtitle_path=md_path,
                            summary_path=summary_result['summary_path']
                        )

                        # @auth: ljz @date: 2026-03-31 显示总耗时
                        elapsed = time.time() - start_time
                        print(f"[完成] 总耗时: {int(elapsed // 60)}分{int(elapsed % 60)}秒")
                    else:
                        print(f"[错误] {summary_result['message']}")
                elif speech_to_text.is_xiaohongshu_url(url):
                    # @auth: ljz @date: 2026-03-31 新增小红书支持
                    # 小红书链接：获取视频信息并进行音频转写
                    print("[信息] 检测到小红书链接，将进行音频转写...")
                    video_info = speech_to_text.get_xiaohongshu_video_info(url)
                    if video_info:
                        duration = video_info.get('duration', 0)
                        if duration > 0:
                            minutes = duration // 60
                            seconds = duration % 60
                            print(f"[信息] 视频时长: {minutes}分{seconds}秒")
                            print(f"[信息] 视频标题: {video_info.get('title', '')}")
                    print()
                    # 选择转录模型
                    print("请选择转录模型:")
                    print(f"  1. SenseVoice（中文效果好，默认）")
                    print("  2. Whisper（英文支持好）")
                    print()
                    try:
                        model_choice = input("请输入选项 (1-2, 默认1): ").strip()
                    except EOFError:
                        model_choice = ""
                    transcribe_model = None
                    if model_choice == '2':
                        transcribe_model = "whisper"

                    # 选择总结程度
                    print("请选择总结程度:")
                    print("  1. 简洁 - 核心要点概述")
                    print("  2. 中等 - 标准总结")
                    print("  3. 详细 - 保留完整细节（默认）")
                    print()
                    try:
                        level_choice = input("请输入选项 (1-3, 默认3，按Enter直接开始): ").strip()
                    except EOFError:
                        level_choice = ""
                    if level_choice == '1':
                        summary_level = "brief"
                    elif level_choice == '2':
                        summary_level = "normal"
                    else:
                        summary_level = "detailed"
                    print()
                    handle_video_without_subtitle(url, transcribe_model=transcribe_model, summary_level=summary_level)
                else:
                    # 其他音频链接：选择转录模型和总结程度
                    print("[信息] 非B站/小红书链接，将进行音频转写...")
                    print()
                    print("请选择转录模型:")
                    print(f"  1. SenseVoice（中文效果好，默认）")
                    print("  2. Whisper（英文支持好）")
                    print()
                    try:
                        model_choice = input("请输入选项 (1-2, 默认1): ").strip()
                    except EOFError:
                        model_choice = ""
                    transcribe_model = None
                    if model_choice == '2':
                        transcribe_model = "whisper"

                    # 选择总结程度
                    print("请选择总结程度:")
                    print("  1. 简洁 - 核心要点概述")
                    print("  2. 中等 - 标准总结")
                    print("  3. 详细 - 保留完整细节（默认）")
                    print()
                    try:
                        level_choice = input("请输入选项 (1-3, 默认3，按Enter直接开始): ").strip()
                    except EOFError:
                        level_choice = ""
                    if level_choice == '1':
                        summary_level = "brief"
                    elif level_choice == '2':
                        summary_level = "normal"
                    else:
                        summary_level = "detailed"
                    print()
                    handle_video_without_subtitle(url, transcribe_model=transcribe_model, summary_level=summary_level)
            elif choice == '1':
                url = input("请输入B站视频URL: ").strip()
                # 自动从文本中提取URL（支持粘贴包含无关前缀的文本）
                # @auth: ljz @date: 2026-03-30
                url = speech_to_text.extract_url(url)
                if url:
                    print()
                    # 先获取视频信息，显示智能推荐总结程度
                    video_info = speech_to_text.get_bilibili_video_info(url)
                    auto_summary_level = "detailed"
                    if video_info:
                        duration = video_info.get('duration', 0)
                        if duration > 0:
                            auto_summary_level = config.auto_select_summary_level(duration)
                            minutes = duration // 60
                            seconds = duration % 60
                            print(f"[信息] 视频时长: {minutes}分{seconds}秒")

                    # 选择总结程度（显示智能推荐）
                    print("请选择总结程度:")
                    print("  1. 简洁 - 核心要点概述")
                    print("  2. 中等 - 标准总结")
                    print(f"  3. 详细 - 保留完整细节（智能推荐: {auto_summary_level}）")
                    print()
                    try:
                        level_choice = input("请输入选项 (1-3, 默认使用智能推荐): ").strip()
                    except EOFError:
                        level_choice = ""
                    if level_choice == '1':
                        summary_level = "brief"
                    elif level_choice == '2':
                        summary_level = "normal"
                    elif level_choice == '3':
                        summary_level = "detailed"
                    else:
                        summary_level = auto_summary_level  # 使用智能推荐
                    print()
                    # 自动检测字幕并处理（无字幕时自动切换到音频转写）
                    handle_video_with_subtitle(url, summary_level=summary_level)
                else:
                    print("[提示] URL不能为空")
            elif choice == '2':
                # @auth: ljz @date: 2026-03-31 新增小红书选项
                url = input("请输入小红书视频URL: ").strip()
                url = speech_to_text.extract_url(url)
                if url:
                    print()
                    video_info = speech_to_text.get_xiaohongshu_video_info(url)
                    if video_info:
                        duration = video_info.get('duration', 0)
                        if duration > 0:
                            minutes = duration // 60
                            seconds = duration % 60
                            print(f"[信息] 视频时长: {minutes}分{seconds}秒")
                            print(f"[信息] 视频标题: {video_info.get('title', '')}")
                    print()
                    # 选择转录模型
                    print("请选择转录模型:")
                    print("  1. SenseVoice（中文效果好，默认）")
                    print("  2. Whisper（英文支持好）")
                    print()
                    try:
                        model_choice = input("请输入选项 (1-2, 默认1): ").strip()
                    except EOFError:
                        model_choice = ""
                    transcribe_model = None
                    if model_choice == '2':
                        transcribe_model = "whisper"

                    # 选择总结程度
                    print("请选择总结程度:")
                    print("  1. 简洁 - 核心要点概述")
                    print("  2. 中等 - 标准总结")
                    print("  3. 详细 - 保留完整细节（默认）")
                    print()
                    try:
                        level_choice = input("请输入选项 (1-3, 默认3，按Enter直接开始): ").strip()
                    except EOFError:
                        level_choice = ""
                    if level_choice == '1':
                        summary_level = "brief"
                    elif level_choice == '2':
                        summary_level = "normal"
                    else:
                        summary_level = "detailed"
                    print()
                    handle_video_without_subtitle(url, transcribe_model=transcribe_model, summary_level=summary_level)
                else:
                    print("[提示] URL不能为空")
            elif choice == '3':
                url = input("请输入音频下载链接或本地路径: ").strip()
                # 自动从文本中提取URL（支持粘贴包含无关前缀的文本）
                # @auth: ljz @date: 2026-03-30
                url = speech_to_text.extract_url(url)
                if url:
                    print()
                    # 选择转录模型
                    print("请选择转录模型:")
                    print("  1. SenseVoice - 中文识别效果好（默认）")
                    print("  2. Whisper - 英文支持好")
                    print()
                    try:
                        model_choice = input("请输入选项 (1-2, 默认1): ").strip()
                    except EOFError:
                        model_choice = "1"
                    if model_choice == '2':
                        transcribe_model = "whisper"
                    else:
                        transcribe_model = "sensevoice"

                    # 选择总结程度
                    print("请选择总结程度:")
                    print("  1. 简洁 - 核心要点概述")
                    print("  2. 中等 - 标准总结")
                    print("  3. 详细 - 保留完整细节（默认）")
                    print()
                    try:
                        level_choice = input("请输入选项 (1-3, 默认3): ").strip()
                    except EOFError:
                        level_choice = ""
                    if level_choice == '1':
                        summary_level = "brief"
                    elif level_choice == '2':
                        summary_level = "normal"
                    else:
                        summary_level = "detailed"
                    print()
                    handle_video_without_subtitle(url, summary_level=summary_level, transcribe_model=transcribe_model)
                else:
                    print("[提示] 链接不能为空")
            elif choice == '4':
                print("请选择总结程度:")
                print("  1. 简洁 - 核心要点概述")
                print("  2. 中等 - 标准总结")
                print("  3. 详细 - 保留完整细节（默认）")
                print()

                try:
                    level_choice = input("请输入选项 (1-3, 默认3): ").strip()
                except EOFError:
                    level_choice = "2"

                if level_choice == '1':
                    summary_level = "brief"
                elif level_choice == '3':
                    summary_level = "detailed"
                else:
                    summary_level = "detailed"

                print()
                handle_summarize_only(summary_level=summary_level)
            elif choice == '5':
                print()
                # 选择转录模型
                print("请选择转录模型:")
                print("  1. SenseVoice - 中文识别效果好（默认）")
                print("  2. Whisper - 英文支持好")
                print()
                try:
                    model_choice = input("请输入选项 (1-2, 默认1): ").strip()
                except EOFError:
                    model_choice = "1"
                if model_choice == '2':
                    transcribe_model = "whisper"
                else:
                    transcribe_model = "sensevoice"
                print()
                handle_transcribe_audio_files(transcribe_model=transcribe_model)
            elif choice == '6':
                # 查看历史记录
                show_history()
            elif choice == '0':
                # 退出程序
                print("[退出] 欢迎下次使用！")
                break
            else:
                print("[提示] 无效选项，请重新选择")

            print()
        except Exception as e:
            # @auth: ljz @date: 2026-03-31 添加异常捕获，防止闪退
            print(f"[错误] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            print()


def main():
    """主函数"""
    # @auth: ljz @date: 2026-03-31 确保目录存在（延迟初始化）
    config.ensure_directories()

    # @auth: ljz @date: 2026-03-31 清理旧日志文件（保留30天）
    logger.clean_old_logs(max_days=30)

    # @auth: ljz @date: 2026-03-31 清理临时音频文件（超过24小时的文件）
    cleaned = config.cleanup_temp_audio(max_age_hours=24, keep_latest=5)
    if cleaned > 0:
        print(f"[清理] 已清理 {cleaned} 个过期临时文件")

    print_banner()

    # 解析命令行参数
    if len(sys.argv) == 1:
        # 无参数，交互模式
        interactive_mode()
    elif len(sys.argv) == 2:
        # 一个参数，视为B站视频URL
        url = speech_to_text.extract_url(sys.argv[1])  # @auth: ljz @date: 2026-03-30 自动提取URL
        # @auth: ljz @date: 2026-03-31 添加None检查避免程序崩溃
        if url and url.startswith('http'):
            handle_video_with_subtitle(url)
        elif url:
            # 视为文件路径，进行总结
            handle_summarize_only(url)
        else:
            print("[错误] 无法识别输入，请提供有效的URL或文件路径")
            print_usage()
            sys.exit(1)
    elif len(sys.argv) >= 3 and sys.argv[1] == '--audio':
        # 音频转写模式
        audio_url = speech_to_text.extract_url(sys.argv[2])  # @auth: ljz @date: 2026-03-30 自动提取URL
        # @auth: ljz @date: 2026-03-31 添加None检查
        if not audio_url:
            print("[错误] 无法识别音频URL")
            print_usage()
            sys.exit(1)
        # 检查是否有--model参数
        transcribe_model = None
        if len(sys.argv) >= 5 and sys.argv[3] == '--model':
            transcribe_model = sys.argv[4]
        handle_video_without_subtitle(audio_url, transcribe_model=transcribe_model)
    elif sys.argv[1] == '--summarize':
        # 仅总结模式
        md_path = sys.argv[2]
        handle_summarize_only(md_path)
    elif sys.argv[1] == '--interactive':
        # 交互模式
        interactive_mode()
    elif sys.argv[1] == '--download':
        # 下载音频模式
        if len(sys.argv) >= 3:
            audio_url = speech_to_text.extract_url(sys.argv[2])  # @auth: ljz @date: 2026-03-30 自动提取URL
            # @auth: ljz @date: 2026-03-31 添加None检查
            if not audio_url:
                print("[错误] 无法识别音频URL")
                print_usage()
                sys.exit(1)
            output_path = sys.argv[3] if len(sys.argv) >= 4 else None
        else:
            print_usage()
            return
        print(f"[主流程] 模式: 下载音频")
        print(f"[主流程] 音频链接: {audio_url}")
        if output_path:
            print(f"[主流程] 保存路径: {output_path}")
        print()
        try:
            path = speech_to_text.download_audio(audio_url, output_path)
            print()
            print("=" * 60)
            print("下载完成!")
            print(f"保存路径: {path}")
        except Exception as e:
            print(f"[错误] {e}")
    elif sys.argv[1] == '--auto':
        # 自动转写temp_audio中未处理的文件
        speech_to_text.transcribe_untranscribed_in_temp()
    elif sys.argv[1] == '--history':
        # 查看历史记录
        limit = 20
        if len(sys.argv) >= 3 and sys.argv[2].isdigit():
            limit = int(sys.argv[2])
        show_history(limit)
    elif sys.argv[1] == '--clear-history':
        # 清空历史记录
        config.clear_history()
    elif sys.argv[1] == '--model':
        # 指定转录模型
        if len(sys.argv) >= 3:
            transcribe_model = sys.argv[2]
            print(f"[主流程] 转录模型: {transcribe_model}")
        else:
            print_usage()
    else:
        print_usage()


if __name__ == "__main__":
    main()
