# -*- coding: utf-8 -*-
# @auth: ljz
# @date: 2026-03-29
# 字幕提取模块 - 使用yt-dlp提取B站视频字幕并转换为Markdown

import os
import re
import glob
import subprocess
import config


def extract_subtitles(bilibili_url):
    """
    从B站视频URL提取字幕

    Args:
        bilibili_url: B站视频URL

    Returns:
        dict: {
            'success': bool,
            'subtitle_path': str or None,  # .md文件路径
            'message': str,
            'has_subtitle': bool
        }
    """
    print(f"[字幕提取] 正在分析视频: {bilibili_url}")

    # 创建临时目录用于存放字幕
    temp_dir = os.path.join(config.PROJECT_ROOT, "temp_subs")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # 使用yt-dlp提取字幕
        # --write-subs: 写入字幕
        # --write-auto-subs: 写入自动生成的字幕
        # --sub-lang zh-Hans,zh-Hant,en: 指定字幕语言
        # -o: 输出模板
        # @auth: ljz @date: 2026-03-30 使用cookies绕过WBI验证
        cookies_file = config.COOKIES_FILE
        cmd = [
            "yt-dlp",
            "--write-subs",
            "--write-auto-subs",
            "--sub-lang", "zh-Hans,zh-Hant,en",
            "--skip-download",
            "--cookies", cookies_file,
            "-o", os.path.join(temp_dir, "%(id)s.%(ext)s"),
            bilibili_url
        ]

        print(f"[字幕提取] 执行命令: {' '.join(cmd)}")
        # @auth: ljz @date: 2026-03-30 添加timeout避免无限等待
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)

        if result.returncode != 0:
            print(f"[字幕提取] yt-dlp错误: {result.stderr}")
            return {
                'success': False,
                'subtitle_path': None,
                'message': f"字幕提取失败: {result.stderr}",
                'has_subtitle': False
            }

        # 查找生成的字幕文件
        subtitle_files = []
        for ext in ['ass', 'srt', 'vtt']:
            pattern = os.path.join(temp_dir, f"*.{ext}")
            subtitle_files.extend([f for f in glob.glob(pattern) if 'auto' in f or True])

        if not subtitle_files:
            # 尝试不筛选auto
            for ext in ['ass', 'srt', 'vtt']:
                pattern = os.path.join(temp_dir, f"*.{ext}")
                subtitle_files.extend(glob.glob(pattern))

        print(f"[字幕提取] 找到字幕文件: {subtitle_files}")

        if not subtitle_files:
            return {
                'success': True,
                'subtitle_path': None,
                'message': "未找到字幕文件",
                'has_subtitle': False
            }

        # 转换字幕为Markdown
        md_path = convert_subtitles_to_md(subtitle_files[0])

        return {
            'success': True,
            'subtitle_path': md_path,
            'message': f"字幕提取成功: {md_path}",
            'has_subtitle': True
        }

    except FileNotFoundError:
        return {
            'success': False,
            'subtitle_path': None,
            'message': "未找到yt-dlp，请先安装: pip install yt-dlp",
            'has_subtitle': False
        }
    except Exception as e:
        return {
            'success': False,
            'subtitle_path': None,
            'message': f"字幕提取异常: {str(e)}",
            'has_subtitle': False
        }


def convert_subtitles_to_md(subtitle_file):
    """
    将字幕文件(ass/srt/vtt)转换为Markdown格式

    Args:
        subtitle_file: 字幕文件路径

    Returns:
        str: 转换后的.md文件路径
    """
    filename = os.path.basename(subtitle_file)
    video_id = filename.split('.')[0]
    md_filename = f"{video_id}.md"
    md_path = os.path.join(config.SUBTITLES_DIR, md_filename)

    print(f"[字幕转换] 正在转换 {subtitle_file} -> {md_path}")

    with open(subtitle_file, 'r', encoding='utf-8') as f:
        content = f.read()

    md_lines = []
    ext = os.path.splitext(subtitle_file)[1].lower()

    if ext == '.ass' or ext == '.ssa':
        md_lines = parse_ass(content)
    elif ext == '.srt':
        md_lines = parse_srt(content)
    elif ext == '.vtt':
        md_lines = parse_vtt(content)
    else:
        md_lines = [content]

    # 写入Markdown文件
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# 视频字幕\n\n")
        f.write(f"视频ID: {video_id}\n\n")
        f.write("---\n\n")
        f.write('\n'.join(md_lines))

    print(f"[字幕转换] 完成，共 {len(md_lines)} 行")

    # 清理临时字幕文件
    try:
        os.remove(subtitle_file)
    except:
        pass

    return md_path


def parse_ass(content):
    """解析ASS/SSA格式字幕"""
    lines = []
    in_events = False
    format_fields = []

    for line in content.split('\n'):
        line = line.strip()

        if line.startswith('[Events]'):
            in_events = True
            continue

        if in_events and line.startswith('Format:'):
            # 解析Format行
            format_fields = [f.strip().lower() for f in line.split(':', 1)[1].split(',')]
            continue

        if in_events and line.startswith('Dialogue:'):
            # 解析Dialogue行
            parts = line.split(':', 1)
            if len(parts) > 1:
                dialogue_content = parts[1]
                # 按逗号分割，但文本字段可能包含逗号
                fields = []
                current = ''
                comma_count = 0
                for char in dialogue_content:
                    if char == ',' and comma_count < 9:
                        fields.append(current.strip())
                        current = ''
                        comma_count += 1
                    else:
                        current += char
                fields.append(current.strip())

                if len(fields) >= 10:
                    # Text字段是最后一个
                    text = fields[9]
                    # 清理ASS样式标签
                    text = clean_ass_tags(text)
                    if text.strip():
                        lines.append(text)

    return lines


def clean_ass_tags(text):
    """清理ASS样式标签"""
    # 移除 {\pos(...)} 等位置标签
    text = re.sub(r'\{[^}]*\}', '', text)
    # 移除 \N 和 \n 换行符
    text = text.replace('\\N', '\n').replace('\\n', '\n')
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_srt(content):
    """解析SRT格式字幕"""
    lines = []
    # SRT格式: 序号\n时间码\n文本\n\n
    blocks = content.strip().split('\n\n')

    for block in blocks:
        parts = block.split('\n')
        if len(parts) >= 3:
            # 取文本部分（去掉时间码）
            text_lines = parts[2:]
            text = ' '.join(text_lines)
            if text.strip():
                lines.append(text.strip())

    return lines


def parse_vtt(content):
    """解析WebVTT格式字幕"""
    lines = []
    # 跳过头部
    lines_raw = content.split('\n')
    skip_next = False

    for i, line in enumerate(lines_raw):
        if line.strip().startswith('NOTE') or line.strip().startswith('STYLE'):
            continue
        if '-->' in line:
            skip_next = True
            continue
        if skip_next:
            skip_next = False
            continue
        if line.strip() and not line.strip().startswith('WEBVTT'):
            lines.append(line.strip())

    return lines


if __name__ == "__main__":
    # 测试
    test_url = input("请输入B站视频URL: ").strip()
    if test_url:
        result = extract_subtitles(test_url)
        print(result)
