# -*- coding: utf-8 -*-
# @auth: ljz
# @date: 2026-03-29
# 主程序入口 - B站视频字幕提取与总结

import sys
import os
import glob

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import subtitle_extractor
import speech_to_text
import summarizer


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
    print("  1. 有字幕视频: python main.py <B站视频URL>")
    print("  2. 无字幕视频: python main.py --audio <音频下载链接> [--model <模型>]")
    print("  3. 仅总结现有.md: python main.py --summarize <md文件路径>")
    print("  4. 交互模式: python main.py --interactive")
    print("  5. 下载音频: python main.py --download <音频下载链接> [保存路径]")
    print("  6. 自动转写: python main.py --auto  (扫描temp_audio转写未处理的文件)")
    print()
    print("可选转录模型:")
    print("  sensevoice - SenseVoice (FunASR) 中文识别效果好（默认）")
    print("  whisper    - Whisper (faster-whisper) 英文支持好")
    print()
    print("配置:")
    print("  请在 config.py 中配置您的阿里云AccessKey")
    print()


def handle_video_with_subtitle(url, summary_level=None):
    """
    处理有字幕的视频

    Args:
        url: B站视频URL
        summary_level: 总结程度 ("brief", "normal", "detailed")
    """
    # 获取总结提示词
    if summary_level is None:
        summary_level = config.DEFAULT_SUMMARY_LEVEL
    prompt = config.SUMMARY_PROMPTS.get(summary_level, config.SUMMARY_PROMPTS["normal"])

    print(f"[主流程] 模式: 有字幕视频")
    print(f"[主流程] 视频URL: {url}")
    print(f"[主流程] 总结程度: {summary_level}")
    print()

    # Step 1: 提取字幕
    print("[Step 1/3] 提取字幕...")
    result = subtitle_extractor.extract_subtitles(url)

    if not result['success']:
        print(f"[错误] {result['message']}")
        return False

    if not result['has_subtitle']:
        print("[提示] 未找到字幕，切换到无字幕模式...")
        print("[提示] 请使用 --audio 参数并提供音频下载链接")
        return False

    md_path = result['subtitle_path']
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

    # 完成
    print("=" * 60)
    print("处理完成!")
    print("=" * 60)
    print(f"字幕文件: {md_path}")
    print(f"总结文件: {summary_result['summary_path']}")
    print()
    print("总结内容:")
    print("-" * 60)
    print(summary_result['summary'])

    return True


def handle_video_without_subtitle(audio_url, summary_level=None, transcribe_model=None):
    """
    处理无字幕视频（需要音频转写）

    Args:
        audio_url: 音频下载链接
        summary_level: 总结程度 ("brief", "normal", "detailed")
        transcribe_model: 转录模型 (None/sensevoice/whisper/siliconflow)
    """
    # 获取总结提示词
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
    result = speech_to_text.transcribe_audio(audio_url, model=transcribe_model)

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

    # 完成
    print("=" * 60)
    print("处理完成!")
    print("=" * 60)
    print(f"转写文件: {md_path}")
    print(f"总结文件: {summary_result['summary_path']}")
    print()
    print("总结内容:")
    print("-" * 60)
    print(summary_result['summary'])

    return True


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

    return True


def interactive_mode():
    """
    交互模式
    """
    print("[交互模式] 欢迎使用B站视频字幕提取与总结工具")
    print()

    while True:
        print("请选择操作:")
        print("  1. 处理有字幕的B站视频")
        print("  2. 处理无字幕的B站视频（需要音频转写）")
        print("  3. 总结现有的.md文件")
        print("  4. 转写temp_audio中的音频文件")
        print("  0. 退出")
        print()

        choice = input("请输入选项 (0-4): ").strip()

        if choice == '0':
            print("再见!")
            break
        elif choice == '1':
            url = input("请输入B站视频URL: ").strip()
            if url:
                print()
                # 选择总结程度
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
                handle_video_with_subtitle(url, summary_level=summary_level)
            else:
                print("[提示] URL不能为空")
        elif choice == '2':
            url = input("请输入音频下载链接: ").strip()
            if url:
                print()
                # 选择总结程度
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
                # 选择转录模型
                print()
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
                handle_video_without_subtitle(url, summary_level=summary_level, transcribe_model=transcribe_model)
            else:
                print("[提示] 链接不能为空")
        elif choice == '3':
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
        elif choice == '4':
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
        else:
            print("[提示] 无效选项，请重新选择")

        print()


def main():
    """主函数"""
    print_banner()

    # 解析命令行参数
    if len(sys.argv) == 1:
        # 无参数，交互模式
        interactive_mode()
    elif len(sys.argv) == 2:
        # 一个参数，视为B站视频URL
        url = sys.argv[1]
        if url.startswith('http'):
            handle_video_with_subtitle(url)
        else:
            # 视为文件路径，进行总结
            handle_summarize_only(url)
    elif len(sys.argv) >= 3 and sys.argv[1] == '--audio':
        # 音频转写模式
        audio_url = sys.argv[2]
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
            audio_url = sys.argv[2]
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
