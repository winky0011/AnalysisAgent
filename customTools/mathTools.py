from typing import Dict, List, Optional, Any, Annotated
from datetime import datetime

from langchain_core.tools import tool, BaseTool, InjectedToolCallId

from langchain_core.tools import tool, InjectedToolCallId, BaseTool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

import csv
from typing import Dict, Any, Annotated, List

from customState import CustomState
from utils import *

# ------------------------------
# 批量计算两个时间的对应差值
# ------------------------------
@tool
def calculate_single_time_difference(time1: str, time2: str) -> Dict[str, Any]:
    """
    计算两个时间点之间的差值（time1 - time2）
    
    参数:
        time1: 第一个时间字符串（如"2024-01-01 10:00"）
        time2: 第二个时间字符串（如"2024-01-01 09:30"）
    
    返回:
        包含时间差信息的字典，包括状态、差值（秒、分钟、小时、天）
    """
    t1 = parse_datetime(time1)
    t2 = parse_datetime(time2)
    
    if not t1 or not t2:
        return {
            "status": "error",
            "message": f"无法解析时间格式：time1='{time1}', time2='{time2}'",
            "difference": None
        }
    
    diff = t1 - t2
    diff_sec = diff.total_seconds()
    
    return {
        "status": "success",
        "message": "时间差计算完成",
        "difference": {
            "seconds": round(diff_sec, 2),
            "minutes": round(diff_sec / 60, 2),
            "hours": round(diff_sec / 3600, 2),
            "days": round(diff_sec / 86400, 2),
            "time1": time1,
            "time2": time2,
            "interpretation": "time1 晚于 time2" if diff_sec > 0 else 
                                "time1 早于 time2" if diff_sec < 0 else 
                                "两个时间相同"
        }
    }


# ------------------------------
# 批量计算两个时间列表的对应差值
# ------------------------------
@tool
def batch_calculate_time_differences(list1: List[str], list2: List[str]) -> Dict[str, Any]:
    """
    批量计算两个时间列表的对应差值（list1 - list2），并进行统计分析
    
    参数:
        list1: 时间字符串列表（如["2024-01-01 10:00", "2024-01-02 14:00"]）
        list2: 时间字符串列表（需与list1长度一致，如["2024-01-01 09:30", "2024-01-02 15:00"]）
    
    返回:
        包含差值统计（正值/负值/零值数量）和超时最多的前五个样本的字典
    """
    if len(list1) != len(list2):
        return {
            "status": "error",
            "message": f"列表长度不匹配：list1({len(list1)}条) vs list2({len(list2)}条)",
            "statistics": None,
            "top_overtime_samples": None
        }

    total = len(list1)
    positive = 0  # list1 > list2（差值为正）
    negative = 0  # list1 < list2（差值为负）
    zero = 0
    invalid = 0
    differences = []  # 存储差值信息的列表
    overtime_samples = []  # 存储超时样本（用于后续取前5）

    for idx, (t1_str, t2_str) in enumerate(zip(list1, list2)):
        t1 = parse_datetime(t1_str)
        t2 = parse_datetime(t2_str)
        
        if not t1 or not t2:
            invalid += 1
            differences.append({
                "index": idx,
                "time1": t1_str,
                "time2": t2_str,
                "difference_seconds": None,
                "status": "invalid"
            })
            continue

        diff_sec = (t1 - t2).total_seconds()
        diff_info = {
            "index": idx,
            "time1": t1_str,
            "time2": t2_str,
            "difference_seconds": round(diff_sec, 2),
            "difference_minutes": round(diff_sec / 60, 2),
            "status": "valid"
        }
        differences.append(diff_info)
        
        # 记录超时样本（diff_sec > 0）
        if diff_sec > 0:
            positive += 1
            overtime_samples.append({
                "index": idx,
                "time1": t1_str,
                "time2": t2_str,
                "difference_seconds": round(diff_sec, 2),
                "difference_minutes": round(diff_sec / 60, 2)
            })
        elif diff_sec < 0:
            negative += 1
        else:
            zero += 1

    # 按超时时间排序，取前5个
    top_overtime = sorted(
        overtime_samples, 
        key=lambda x: x["difference_seconds"], 
        reverse=True
    )[:5]

    return {
        "status": "success",
        "message": f"完成{total}对时间差计算",
        "statistics": {
            "total_pairs": total,
            "positive_count": positive,  # 计划超时（如实际结束>计划结束）
            "negative_count": negative,  # 提前完成（如实际结束<计划结束）
            "zero_count": zero,
            "invalid_count": invalid,
            "positive_ratio": round(positive / total * 100, 2) if total > 0 else 0,
            "negative_ratio": round(negative / total * 100, 2) if total > 0 else 0
        },
        # "differences": differences,  # 所有差值详细信息
        "top_overtime_samples": top_overtime  # 超时最多的前5个样本
    }


# ------------------------------
# 基础数学运算
# ------------------------------
@tool
def calculate_math(operation: str, a: float, b: float) -> Dict[str, Any]:
    """
    基础数学运算（用于数据分析中的数值计算，如平均值、总和等衍生计算）
    参数:
        operation: 运算类型（支持"add"/"subtract"/"multiply"/"divide"）
        a: 第一个数值
        b: 第二个数值
    返回:
        包含运算结果的字典
    """
    try:
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return {"status": "error", "message": "除数不能为0", "result": None}
            result = a / b
        else:
            return {"status": "error", "message": f"不支持的运算：{operation}", "result": None}
        return {"status": "success", "message": f"{a} {operation} {b} = {result}", "result": round(result, 2)}
    except Exception as e:
        return {"status": "error", "message": f"运算错误: {str(e)}", "result": None}


def get_math_tools() -> List[BaseTool]:
    return [
        calculate_single_time_difference,
        batch_calculate_time_differences,
        calculate_math
    ]