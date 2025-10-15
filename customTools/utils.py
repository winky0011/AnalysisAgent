from typing import Dict, List, Optional, Any, Annotated
from datetime import datetime

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
