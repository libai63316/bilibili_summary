# -*- coding: utf-8 -*-
# @auth: ljz
# @date: 2026-03-30
# 日志模块

import os
import logging
from datetime import datetime

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径（按日期）
def get_log_file():
    """获取当天的日志文件路径"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"bilibili_subtitle_{date_str}.log")

# 配置日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 创建日志记录器
logger = logging.getLogger("bilibili_subtitle")
logger.setLevel(logging.DEBUG)

# 文件处理器（记录所有日志）
file_handler = logging.FileHandler(get_log_file(), encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# 控制台处理器（只显示INFO及以上级别）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# 添加处理器
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def log_info(message):
    """记录INFO级别日志"""
    logger.info(message)


def log_warning(message):
    """记录WARNING级别日志"""
    logger.warning(message)


def log_error(message):
    """记录ERROR级别日志"""
    logger.error(message)


def log_debug(message):
    """记录DEBUG级别日志（仅写入文件）"""
    logger.debug(message)


def log_step(step_num, step_name, status="开始"):
    """记录步骤日志"""
    logger.info(f"[Step {step_num}] {status}: {step_name}")


def log_video_info(title, duration, uploader, url):
    """记录视频信息"""
    logger.info(f"视频标题: {title}")
    logger.info(f"视频时长: {duration}秒")
    logger.info(f"UP主: {uploader}")
    logger.debug(f"视频URL: {url}")