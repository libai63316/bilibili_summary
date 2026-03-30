# -*- coding: utf-8 -*-
# @auth: ljz
# @date: 2026-03-29
# SenseVoice转写模块 - 使用FunASR/SenseVoice进行音频转写

import os
import time
import shutil
import requests
import config
import glob
import site

# 设置ffmpeg路径，让FunASR能找到
import site
_site_packages = [p for p in site.getsitepackages() if 'site-packages' in p][0]
_ffmpeg_path = os.path.join(_site_packages, "imageio_ffmpeg", "binaries")
if os.path.exists(_ffmpeg_path) and _ffmpeg_path not in os.environ.get('PATH', ''):
    os.environ['PATH'] = _ffmpeg_path + os.pathsep + os.environ.get('PATH', '')


def download_audio(audio_url, video_name=None):
    """
    下载音频文件

    Args:
        audio_url: 音频下载链接
        video_name: 视频名称（可选），用于生成文件名

    Returns:
        str: 下载后的文件路径
    """
    # 确保目录存在
    config.ensure_directories()

    timestamp = time.strftime('%Y%m%d_%H%M')

    if video_name:
        # 清理视频名称中的非法字符
        safe_name = "".join(c for c in video_name if c.isalnum() or c in (' ', '-', '_', '。', '，')).strip()
        safe_name = safe_name.replace(' ', '_')
        filename = f"{safe_name}_{timestamp}.mp3"
    else:
        filename = f"audio_{timestamp}.mp3"

    output_path = os.path.join(config.TEMP_AUDIO_DIR, filename)

    print(f"[音频下载] 正在下载: {audio_url}")
    print(f"[音频下载] 保存至: {output_path}")

    try:
        response = requests.get(audio_url, stream=True, timeout=300)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r[音频下载] 进度: {percent:.1f}%", end='', flush=True)

        print()  # 换行
        print(f"[音频下载] 完成: {output_path}")
        return output_path

    except requests.exceptions.RequestException as e:
        raise Exception(f"音频下载失败: {str(e)}")


# 模型缓存，避免每次转写都重新加载
_sensevoice_model = None
_sensevoice_model_device = None


def transcribe_with_sensevoice(audio_path):
    """
    使用FunASR/SenseVoice进行本地音频转写

    Args:
        audio_path: 音频文件路径

    Returns:
        dict: {
            'success': bool,
            'text': str or None,
            'segments': list or None,
            'message': str
        }
    """
    global _sensevoice_model, _sensevoice_model_device

    try:
        from funasr import AutoModel
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"

        # 使用缓存的模型，避免每次重新加载
        if _sensevoice_model is None or _sensevoice_model_device != device:
            print("[转写] 正在加载SenseVoice模型...")
            _sensevoice_model = AutoModel(
                model="iic/SenseVoiceSmall",
                trust_remote_code=True,
                device=device,
                disable_update=True,
            )
            _sensevoice_model_device = device
            print(f"[转写] 模型已加载，设备: {device}")
        else:
            print(f"[转写] 使用缓存模型，设备: {device}")

        model = _sensevoice_model
        print(f"[转写] 正在转写音频: {audio_path}")

        # 检查音频时长，过长的音频在GPU上会显存不足
        # 如果超过5分钟，用ffmpeg分段处理
        import subprocess
        try:
            ffmpeg_path = os.path.join(
                [p for p in site.getsitepackages() if 'site-packages' in p][0],
                'imageio_ffmpeg', 'binaries', 'ffmpeg.exe'
            )
            probe_result = subprocess.run(
                [ffmpeg_path, '-i', audio_path],
                capture_output=True, text=True, encoding='utf-8', errors='replace'
            )
            import re
            duration_match = re.search(r'Duration: (\d+):(\d+):(\d+)', probe_result.stderr)
            if duration_match:
                hours, mins, secs = int(duration_match.group(1)), int(duration_match.group(2)), int(duration_match.group(3))
                duration_sec = hours * 3600 + mins * 60 + secs
                print(f"[转写] 音频时长: {duration_sec}秒")

                if duration_sec > 480:
                    # 音频超过5分钟，分段处理
                    print(f"[转写] 音频较长，将分段处理...")
                    # 分段为8分钟一段
                    segment_duration = 480
                    segments_dir = os.path.join(config.TEMP_AUDIO_DIR, f"segments_{int(time.time())}")
                    os.makedirs(segments_dir, exist_ok=True)

                    # 计算总段数
                    total_segments = (duration_sec + segment_duration - 1) // segment_duration
                    print(f"[转写] 音频较长，将分段处理，共 {total_segments} 段")

                    all_texts = []
                    for i in range(0, duration_sec, segment_duration):
                        start = i
                        end = min(i + segment_duration, duration_sec)
                        segment_path = os.path.join(segments_dir, f"segment_{i}_{end}.m4a")
                        current_segment = i // segment_duration + 1

                        # 显示进度
                        minutes_start = start // 60
                        seconds_start = start % 60
                        minutes_end = end // 60
                        seconds_end = end % 60
                        print(f"[转写] 第 {current_segment}/{total_segments} 段 ({minutes_start}分{seconds_start}秒 - {minutes_end}分{seconds_end}秒)...")

                        # 切割音频段
                        print(f"[转写]   切割音频...")
                        subprocess.run([
                            ffmpeg_path, '-y', '-i', audio_path,
                            '-ss', str(start), '-to', str(end),
                            '-ar', '16000', '-ac', '1',
                            segment_path
                        ], capture_output=True, errors='replace')

                        # 转写该段
                        print(f"[转写]   转写中...")
                        result = model.generate(
                            input=segment_path,
                            use_itn=True,
                            batch_size_s=60,
                        )

                        if result and len(result) > 0:
                            res = result[0]
                            text = res.get('text', '') if isinstance(res, dict) else str(res)
                            all_texts.append(text)
                            print(f"[转写]   第 {current_segment}/{total_segments} 段完成")

                    # 清理分段文件
                    import shutil
                    shutil.rmtree(segments_dir, ignore_errors=True)

                    print(f"[转写] 分段转写完成，共处理 {total_segments} 段")

                    return {
                        'success': True,
                        'text': ' '.join(all_texts),
                        'segments': None,
                        'message': "转写成功"
                    }
        except Exception as e:
            print(f"[转写] 时长检测失败: {e}")

        # 非分段模式：直接转写
        print("[转写] 正在转写，请稍候...")

        # 执行转写，use_itn=True 使用ITN（逆文本正则化）获得可读文本
        result = model.generate(
            input=audio_path,
            use_itn=True,
            batch_size_s=60,
        )

        if not result or len(result) == 0:
            return {
                'success': False,
                'text': None,
                'segments': None,
                'message': "转写结果为空"
            }

        # 解析结果
        res = result[0]
        # 兼容不同的返回格式
        if isinstance(res, dict):
            text = res.get('text', '')
        elif isinstance(res, str):
            text = res
        else:
            text = str(res) if res else ''

        # 提取时间戳信息（如果有）
        segment_list = []
        if 'timestamp' in res:
            for ts in res['timestamp']:
                # timestamp可能是list [start, end, text] 或 dict {'start': ..., 'end': ..., 'text': ...}
                if isinstance(ts, dict):
                    start = ts.get('start', 0) / 1000
                    end = ts.get('end', 0) / 1000
                    segment_text = ts.get('text', '')
                elif isinstance(ts, (list, tuple)) and len(ts) >= 3:
                    start = float(ts[0]) / 1000
                    end = float(ts[1]) / 1000
                    segment_text = str(ts[2])
                else:
                    continue
                segment_list.append({
                    'start': start,
                    'end': end,
                    'text': segment_text
                })

        return {
            'success': True,
            'text': text,
            'segments': segment_list if segment_list else None,
            'message': "转写成功"
        }

    except ImportError:
        return {
            'success': False,
            'text': None,
            'segments': None,
            'message': "请先安装FunASR: pip install funasr"
        }
    except Exception as e:
        return {
            'success': False,
            'text': None,
            'segments': None,
            'message': f"转写失败: {str(e)}"
        }


def transcribe_with_whisper_local(audio_path, model_size="base", language="zh"):
    """
    使用faster-whisper进行本地音频转写（备用方案）

    Args:
        audio_path: 音频文件路径
        model_size: 模型大小 (tiny, base, small, medium, large)
        language: 语言代码 (zh, en, ja, ko等)

    Returns:
        dict: {
            'success': bool,
            'text': str or None,
            'segments': list or None,
            'message': str
        }
    """
    print(f"[转写] 正在加载Whisper模型: {model_size}...")

    try:
        from faster_whisper import WhisperModel

        compute_type = "float16"

        try:
            model = WhisperModel(model_size, device="cuda", compute_type=compute_type)
            print("[转写] 使用GPU加速")
        except Exception:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            print("[转写] 使用CPU计算")

        print(f"[转写] 正在转写音频: {audio_path}")

        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        full_text = []
        segment_list = []

        print(f"[转写] 检测到语言: {info.language}, 时长: {info.duration:.2f}秒")
        print("[转写] 正在处理音频...")

        for segment in segments:
            text = segment.text.strip()
            start_time = segment.start
            end_time = segment.end

            full_text.append(text)
            segment_list.append({
                'start': start_time,
                'end': end_time,
                'text': text
            })

            elapsed = end_time
            print(f"\r[转写] 已处理: {elapsed:.1f}秒 / {info.duration:.1f}秒", end='', flush=True)

        print()

        combined_text = " ".join(full_text)

        return {
            'success': True,
            'text': combined_text,
            'segments': segment_list,
            'language': info.language,
            'duration': info.duration,
            'message': "转写成功"
        }

    except ImportError:
        return {
            'success': False,
            'text': None,
            'segments': None,
            'message': "请先安装faster-whisper: pip install faster-whisper"
        }
    except Exception as e:
        return {
            'success': False,
            'text': None,
            'segments': None,
            'message': f"转写失败: {str(e)}"
        }


def transcribe_with_siliconflow(audio_path, language="zh"):
    """
    使用SiliconFlow Whisper API进行音频转写（云端方案）

    Args:
        audio_path: 音频文件路径
        language: 语言代码

    Returns:
        dict: {
            'success': bool,
            'text': str or None,
            'segments': list or None,
            'message': str
        }
    """
    api_key = config.SILICONFLOW_API_KEY

    if not api_key or api_key == "your_api_key":
        return {
            'success': False,
            'text': None,
            'segments': None,
            'message': "请在config.py中配置您的SiliconFlow API Key"
        }

    print(f"[转写] 正在上传音频到SiliconFlow...")

    url = "https://api.siliconflow.cn/v1/audio/transcriptions"

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    try:
        with open(audio_path, 'rb') as f:
            files = {
                'file': (os.path.basename(audio_path), f, 'audio/mpeg'),
                'model': (None, 'speech-paraformer-large-v2'),
                'language': (None, language),
                'need_timestamp': (None, 'true'),
            }

            response = requests.post(url, files=files, headers=headers, timeout=300)

        if response.status_code == 200:
            result = response.json()
            text = result.get('text', '')
            return {
                'success': True,
                'text': text,
                'segments': result.get('words', []),
                'message': "转写成功"
            }
        else:
            return {
                'success': False,
                'text': None,
                'segments': None,
                'message': f"转写失败: {response.status_code} - {response.text}"
            }

    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'text': None,
            'segments': None,
            'message': f"转写失败: {str(e)}"
        }


def save_transcription_as_md(text, segments=None, audio_path=None, video_name=None, transcribe_tool=None):
    """
    将转写文本保存为Markdown文件

    Args:
        text: 转写文本
        segments: 分段信息
        audio_path: 音频文件路径
        video_name: 视频名称
        transcribe_tool: 转写工具名称 (SenseVoice / Whisper)

    Returns:
        str: 保存的.md文件路径
    """
    # 确保目录存在
    config.ensure_directories()

    timestamp = time.strftime('%Y%m%d_%H%M')

    # 确定文件名
    if video_name:
        # 清理视频名称中的非法字符
        safe_name = "".join(c for c in video_name if c.isalnum() or c in (' ', '-', '_', '。', '，')).strip()
        safe_name = safe_name.replace(' ', '_')
        filename = f"{safe_name}_{timestamp}.md"
    elif audio_path:
        # 从音频文件名获取名称
        audio_basename = os.path.basename(audio_path)
        audio_name = os.path.splitext(audio_basename)[0]
        # 清理名称中的非法字符
        safe_name = "".join(c for c in audio_name if c.isalnum() or c in (' ', '-', '_', '。', '，')).strip()
        safe_name = safe_name.replace(' ', '_')
        filename = f"{safe_name}.md"
    else:
        filename = f"transcript_{timestamp}.md"

    md_path = os.path.join(config.SUBTITLES_DIR, filename)

    # 确定标题
    if not video_name and audio_path:
        video_name = os.path.splitext(os.path.basename(audio_path))[0]

    with open(md_path, 'w', encoding='utf-8') as f:
        title = video_name if video_name else "音频转写"
        f.write(f"# {title}\n\n")
        f.write(f"转写时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if transcribe_tool:
            f.write(f"转写工具: {transcribe_tool}\n\n")
        if video_name:
            f.write(f"视频名称: {video_name}\n\n")
        if audio_path:
            f.write(f"音频文件: {audio_path}\n\n")
        f.write("---\n\n")
        f.write("## 转写文本\n\n")
        f.write(text)

    print(f"[保存] 转写文本已保存至: {md_path}")
    return md_path


def extract_url(text):
    """
    从文本中提取URL，从第一个'http'开始

    Args:
        text: 可能包含URL的文本

    Returns:
        str: 提取出的URL，如果没有找到返回None
    """
    if not text:
        return None

    text = text.strip()

    # 如果直接是http开头，直接返回
    if text.startswith('http'):
        return text

    # 查找第一个http出现的位置
    http_pos = text.find('http')
    if http_pos != -1:
        # 从http位置开始截取
        url = text[http_pos:].strip()
        # URL通常到空格、换行或某些分隔符结束
        # 简单处理：取到第一个空格为止
        parts = url.split()
        if parts:
            return parts[0]

    return None


def is_bilibili_url(url):
    """
    检查URL是否是B站视频链接

    Args:
        url: URL字符串

    Returns:
        bool: 是否是B站视频链接
    """
    if not url:
        return False
    return 'bilibili.com' in url and ('/video/' in url or '/bangumi/' in url)


def get_bilibili_video_info(bilibili_url):
    """
    获取B站视频信息（时长、标题、是否有字幕等）

    Args:
        bilibili_url: B站视频URL

    Returns:
        dict: {
            'title': str,  # 视频标题
            'duration': int,  # 时长（秒）
            'has_subtitle': bool  # 是否有字幕
        } 或 None
    """
    import subprocess
    import json

    cmd = ["yt-dlp", "--dump-json", "--no-download", bilibili_url]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode == 0:
            info = json.loads(result.stdout)
            return {
                'title': info.get('title', ''),
                'duration': info.get('duration', 0),
                'has_subtitle': bool(info.get('subtitles') or info.get('automatic_captions'))
            }
    except Exception as e:
        print(f"[警告] 获取视频信息失败: {e}")

    return None


def download_audio_from_bilibili(bilibili_url, video_name=None):
    """
    使用yt-dlp从B站视频下载音频

    Args:
        bilibili_url: B站视频URL
        video_name: 视频名称（可选）

    Returns:
        str: 下载后的音频文件路径
    """
    import subprocess
    import json

    config.ensure_directories()
    timestamp = time.strftime('%Y%m%d_%H%M')

    # 获取视频信息
    print(f"[B站下载] 正在分析视频: {bilibili_url}")

    # 先获取视频标题
    probe_cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        bilibili_url
    ]

    try:
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if probe_result.returncode == 0:
            info = json.loads(probe_result.stdout)
            title = info.get('title', '') or video_name or ''
            # 清理标题中的非法字符
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '。', '，')).strip()
            safe_title = safe_title.replace(' ', '_')
            if safe_title:
                video_name = safe_title
    except Exception as e:
        print(f"[B站下载] 获取视频标题失败: {e}")

    if video_name:
        filename = f"{video_name}_{timestamp}.m4a"
    else:
        filename = f"audio_{timestamp}.m4a"

    output_path = os.path.join(config.TEMP_AUDIO_DIR, filename)

    print(f"[B站下载] 正在下载音频: {bilibili_url}")
    print(f"[B站下载] 保存至: {output_path}")

    # 使用yt-dlp下载音频（选择最佳音频格式，哔哩哔哩通常是m4a）
    # 显示下载进度
    cmd = [
        "yt-dlp",
        "-f", "bestaudio/best",
        "--progress",
        "--newline",
        "-o", output_path,
        bilibili_url
    ]

    # 实时显示下载进度
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace')
    for line in process.stdout:
        line = line.strip()
        if line:
            # 显示yt-dlp的进度输出
            print(f"[B站下载] {line}")

    process.wait()

    if process.returncode != 0:
        raise Exception(f"yt-dlp下载失败")

    print(f"[B站下载] 完成: {output_path}")
    return output_path


def transcribe_audio(audio_url_or_path, video_name=None, model=None):
    """
    转写音频文件的主函数

    Args:
        audio_url_or_path: 音频URL或本地文件路径
        video_name: 视频名称（可选），用于生成文件名
        model: 转录模型 (None/sensevoice/whisper/siliconflow)

    Returns:
        dict: {
            'success': bool,
            'text': str or None,
            'md_path': str or None,
            'message': str
        }
    """
    # 判断是B站视频URL还是普通音频URL/本地文件
    if os.path.exists(audio_url_or_path):
        # 本地文件直接使用
        audio_path = audio_url_or_path
    elif is_bilibili_url(audio_url_or_path):
        # B站视频URL，使用yt-dlp下载音频
        try:
            audio_path = download_audio_from_bilibili(audio_url_or_path, video_name)
        except Exception as e:
            return {
                'success': False,
                'text': None,
                'md_path': None,
                'message': f"B站音频下载失败: {str(e)}"
            }
    else:
        # 提取URL（处理"主链接：https://..."这种情况）
        audio_url = extract_url(audio_url_or_path)
        if not audio_url:
            return {
                'success': False,
                'text': None,
                'md_path': None,
                'message': f"无效的音频链接: {audio_url_or_path}"
            }

        # 下载音频
        try:
            audio_path = download_audio(audio_url, video_name)
        except Exception as e:
            return {
                'success': False,
                'text': None,
                'md_path': None,
                'message': f"下载音频失败: {str(e)}"
            }

    if not os.path.exists(audio_path):
        return {
            'success': False,
            'text': None,
            'md_path': None,
            'message': f"音频文件不存在: {audio_path}"
        }

    # 选择转写模型
    if model is None:
        model = config.DEFAULT_TRANSCRIBE_MODEL

    # 根据模型选择转写方法
    if model == "whisper":
        print("[转写] 使用模型: Whisper (faster-whisper)")
        result = transcribe_with_whisper_local(audio_path)
        used_tool = "Whisper"
    elif model == "siliconflow":
        print("[转写] 使用模型: SiliconFlow API")
        result = transcribe_with_siliconflow(audio_path)
        used_tool = "SiliconFlow"
    else:  # 默认 sensevoice
        print("[转写] 使用模型: SenseVoice (FunASR)")
        result = transcribe_with_sensevoice(audio_path)
        used_tool = "SenseVoice"

    if not result['success']:
        return {
            'success': False,
            'text': None,
            'md_path': None,
            'message': f"转写失败: {result['message']}"
        }

    # 保存为Markdown
    md_path = save_transcription_as_md(
        result['text'],
        result.get('segments'),
        audio_path,
        video_name,
        transcribe_tool=used_tool
    )

    return {
        'success': True,
        'text': result['text'],
        'md_path': md_path,
        'message': f"转写成功: {md_path}"
    }


def transcribe_untranscribed_in_temp():
    """
    扫描temp_audio目录，找出未转写的音频文件并自动转写

    Returns:
        dict: {
            'success': bool,
            'transcribed_count': int,  # 转写成功的数量
            'skipped_count': int,       # 跳过的数量（已有md）
            'failed_count': int,        # 失败的数量
            'results': list            # 每项结果
        }
    """
    print("[自动转写] 扫描 temp_audio 目录...")

    # 确保目录存在
    config.ensure_directories()

    # 获取所有音频文件
    audio_files = []
    for ext in ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.flac', '*.ogg']:
        audio_files.extend(glob.glob(os.path.join(config.TEMP_AUDIO_DIR, ext)))

    if not audio_files:
        print("[自动转写] 未找到音频文件")
        return {
            'success': True,
            'transcribed_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'results': []
        }

    print(f"[自动转写] 找到 {len(audio_files)} 个音频文件")

    # 获取已转写的md文件列表（不带扩展名，用于匹配）
    md_pattern = os.path.join(config.SUBTITLES_DIR, "*.md")
    transcribed_bases = set()
    for md_file in glob.glob(md_pattern):
        # 去掉.md扩展名，得到基础名
        base = os.path.splitext(os.path.basename(md_file))[0]
        transcribed_bases.add(base)

    transcribed_count = 0
    skipped_count = 0
    failed_count = 0
    results = []

    for audio_path in audio_files:
        audio_basename = os.path.splitext(os.path.basename(audio_path))[0]
        md_basename = audio_basename

        # 检查是否已有对应的md文件
        if md_basename in transcribed_bases:
            print(f"[跳过] {os.path.basename(audio_path)} 已转写")
            skipped_count += 1
            continue

        # 执行转写
        print(f"[转写] 开始转写: {os.path.basename(audio_path)}")
        try:
            result = transcribe_audio(audio_path)

            if result['success']:
                transcribed_count += 1
                results.append({
                    'audio': audio_path,
                    'md_path': result['md_path'],
                    'status': 'success'
                })
                print(f"[完成] {os.path.basename(audio_path)} -> {os.path.basename(result['md_path'])}")
            else:
                failed_count += 1
                results.append({
                    'audio': audio_path,
                    'error': result['message'],
                    'status': 'failed'
                })
                print(f"[失败] {os.path.basename(audio_path)}: {result['message']}")
        except Exception as e:
            failed_count += 1
            results.append({
                'audio': audio_path,
                'error': str(e),
                'status': 'failed'
            })
            print(f"[异常] {os.path.basename(audio_path)}: {e}")

    print()
    print(f"[自动转写] 完成: 成功 {transcribed_count}, 跳过 {skipped_count}, 失败 {failed_count}")

    return {
        'success': failed_count == 0,
        'transcribed_count': transcribed_count,
        'skipped_count': skipped_count,
        'failed_count': failed_count,
        'results': results
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "--download":
        # 纯下载模式
        if len(sys.argv) >= 3:
            audio_url = sys.argv[2]
            video_name = sys.argv[3] if len(sys.argv) >= 4 else None
        else:
            audio_url = input("请输入音频下载链接: ").strip()
            video_name = None

        if not audio_url:
            print("[错误] 链接不能为空")
            sys.exit(1)

        # 提取URL
        audio_url = extract_url(audio_url)
        if not audio_url:
            print("[错误] 无效的链接")
            sys.exit(1)

        try:
            path = download_audio(audio_url, video_name)
            print(f"[完成] 音频已保存至: {path}")
        except Exception as e:
            print(f"[错误] {e}")
            sys.exit(1)
    elif len(sys.argv) >= 2 and sys.argv[1] == "--auto":
        # 自动转写temp_audio中未处理的文件
        transcribe_untranscribed_in_temp()
    elif len(sys.argv) >= 2:
        # 转写模式（保留原有逻辑）
        audio_url_or_path = sys.argv[1]
        result = transcribe_audio(audio_url_or_path)
        print(result)
    else:
        print("用法:")
        print("  下载音频: python speech_to_text.py --download <音频URL> [保存路径]")
        print("  自动转写: python speech_to_text.py --auto  (扫描并转写未处理的文件)")
        print("  转写音频: python speech_to_text.py <音频URL或本地文件路径>")
