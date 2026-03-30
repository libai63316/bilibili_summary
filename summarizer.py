# -*- coding: utf-8 -*-
# @auth: ljz
# @date: 2026-03-29
# Claude总结模块 - 调用Claude Code CLI总结视频内容

import os
import subprocess
import config


def get_claude_env():
    """
    获取Claude Code运行所需的环境变量

    Returns:
        dict: 环境变量字典
    """
    env = os.environ.copy()

    # Windows上Claude Code需要git-bash
    if os.name == 'nt':
        # 尝试查找git-bash
        git_bash_paths = [
            r"E:\Installed Apps\Git\usr\bin\bash.exe",
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ]

        bash_path = None
        for path in git_bash_paths:
            if os.path.exists(path):
                bash_path = path
                break

        if bash_path:
            env['CLAUDE_CODE_GIT_BASH_PATH'] = bash_path

    return env


def summarize_with_claude(md_file_path, prompt=None):
    """
    使用Claude Code总结Markdown内容

    Args:
        md_file_path: Markdown文件路径
        prompt: 自定义提示词，默认使用内置提示词

    Returns:
        dict: {
            'success': bool,
            'summary': str or None,
            'summary_path': str or None,
            'message': str
        }
    """
    if not os.path.exists(md_file_path):
        return {
            'success': False,
            'summary': None,
            'summary_path': None,
            'message': f"文件不存在: {md_file_path}"
        }

    # 读取Markdown内容
    with open(md_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 如果没有提供prompt，使用默认提示词
    if prompt is None:
        prompt = """请总结以下视频字幕/转写内容。

请按以下格式输出总结：
1. 视频主题：简要说明视频的主要内容
2. 关键要点：列出3-5个视频的核心观点
3. 详细内容：如果视频有具体的步骤、列表或重要细节，请保留

视频内容如下：
"""

    print("[Claude总结] 正在调用Claude Code...")

    try:
        # 写入临时文件传递内容（避免命令行过长）
        import tempfile
        prompt_file = None
        try:
            # 创建包含完整prompt的临时文件
            full_prompt = f"{prompt}\n\n---\n\n{content}"
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', encoding='utf-8', delete=False) as f:
                f.write(full_prompt)
                prompt_file = f.name

            # 使用claude -p @file方式调用
            # @auth: ljz @date: 2026-03-30 抑制内部调试日志输出
            result = subprocess.run(
                ['claude', '-p', f'@{prompt_file}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,  # 丢弃内部调试日志
                timeout=600,
                env=get_claude_env()
            )
        finally:
            if prompt_file and os.path.exists(prompt_file):
                os.unlink(prompt_file)

        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
            raise Exception(f"Claude Code错误: {error_msg}")

        summary = result.stdout.decode('utf-8', errors='replace').strip()

        if not summary:
            raise Exception("Claude Code返回为空")

        # 保存总结结果
        summary_path = save_summary(summary, md_file_path)

        return {
            'success': True,
            'summary': summary,
            'summary_path': summary_path,
            'message': f"总结完成: {summary_path}"
        }

    except FileNotFoundError:
        return {
            'success': False,
            'summary': None,
            'summary_path': None,
            'message': "未找到Claude Code，请确保已安装并配置好PATH"
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'summary': None,
            'summary_path': None,
            'message': "Claude Code超时（超过10分钟）"
        }
    except Exception as e:
        return {
            'success': False,
            'summary': None,
            'summary_path': None,
            'message': f"总结异常: {str(e)}"
        }


def save_summary(summary, source_md_path):
    """
    保存总结结果到文件

    Args:
        summary: 总结内容
        source_md_path: 源Markdown文件路径

    Returns:
        str: 保存的文件路径
    """
    # 确保目录存在
    config.ensure_directories()

    # 从源文件名生成总结文件名
    source_filename = os.path.basename(source_md_path)
    name_parts = os.path.splitext(source_filename)
    summary_filename = f"{name_parts[0]}_summary.md"
    summary_path = os.path.join(config.SUMMARIES_DIR, summary_filename)

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 视频总结\n\n")
        f.write(f"源文件: {source_filename}\n\n")
        f.write("---\n\n")
        f.write(summary)

    print(f"[保存] 总结已保存至: {summary_path}")
    return summary_path


def interactive_summarize():
    """
    交互式总结 - 让用户输入要总结的文件路径
    """
    print("=" * 50)
    print("B站视频字幕/转写内容总结工具")
    print("=" * 50)
    print()

    md_path = input("请输入要总结的.md文件路径: ").strip().strip('"')

    if not os.path.exists(md_path):
        print(f"[错误] 文件不存在: {md_path}")
        return

    print()
    print("[Claude总结] 正在处理，请稍候...")
    print()

    result = summarize_with_claude(md_path)

    print()
    if result['success']:
        print("=" * 50)
        print("总结结果:")
        print("=" * 50)
        print(result['summary'])
        print()
        print(f"总结已保存至: {result['summary_path']}")
    else:
        print(f"[错误] {result['message']}")


if __name__ == "__main__":
    interactive_summarize()
