from typing import Optional
from datetime import datetime
import os
import time
from pathlib import Path

# ------------------------------
# 解析时间字符串为datetime对象
# ------------------------------
def parse_datetime(time_str: str) -> Optional[datetime]:
    """解析时间字符串为datetime对象，支持多种常见格式"""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%H:%M:%S",
        "%H:%M"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return None


# ------------------------------
# 本地CSV存储配置（可根据需求修改）
# ------------------------------
# 固定存储目录（建议用绝对路径）
LOCAL_CSV_DIR = Path("./cache/local_csv_cache")
# 确保目录存在，不存在则创建
LOCAL_CSV_DIR.mkdir(exist_ok=True, parents=True)

def generate_csv_filename(table_name: str) -> str:
    """生成时间命名的CSV文件名，格式：表名_YYYYMMDDHHMMSS.csv"""
    timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
    return f"{table_name}_{timestamp}.csv"

def get_absolute_csv_path(filename: str) -> str:
    """获取CSV文件的绝对路径"""
    return str(LOCAL_CSV_DIR / filename)