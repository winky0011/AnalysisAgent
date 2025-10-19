from langchain_core.tools import tool, InjectedToolCallId, BaseTool
from langgraph.prebuilt import InjectedState
from langchain_core.messages import ToolMessage

import csv
import os
from typing import Dict, Any, Annotated, List
from io import StringIO
from pathlib import Path

from memory_state import CustomState  # 需确保含 csv_local_path: str、csv_meta: dict（元数据）
from .tool_utils import parse_datetime


# ------------------------------
# 通用工具：从本地CSV文件读取数据（内部复用）
# ------------------------------
def _read_local_csv(csv_path: str) -> tuple[list[dict], list[str]]:
    """
    内部工具函数：从本地CSV文件读取所有行和列名
    返回：(所有行数据列表, 列名列表)
    """
    if not csv_path or not os.path.exists(csv_path):
        raise FileNotFoundError(f"本地CSV文件不存在：{csv_path}")
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)
    return rows, columns


# ------------------------------
# 获取记忆里的CSV结果（返回文件路径和元数据，不返回完整内容）
# ------------------------------
@tool
def get_csv_results(
    state: Annotated[CustomState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, str]:
    """读取记忆中的CSV文件路径和元数据，非必要不读取完整内容（避免超上下文）"""
    csv_path = state.get("csv_local_path")
    csv_meta = state.get("csv_meta", {})  # 元数据：总行数、列名等
    if csv_path and os.path.exists(csv_path):
        # 仅返回路径、元数据，不返回完整CSV内容（关键优化）
        return {
            "tool_call_id": tool_call_id,
            "status": "success",
            "message": f"获取CSV文件成功，路径：{csv_path}",
            "csv_local_path": csv_path,  # 返回文件路径
            "csv_meta": csv_meta,        # 返回元数据（如总行数、列名）
            "csv_version": csv_meta.get("version", 0)  # 从元数据取版本号
        }
    else:
        return {
            "tool_call_id": tool_call_id,
            "status": "error", 
            "message": "无历史CSV文件", 
            "csv_local_path": "",
            "csv_meta": {},
            "csv_version": 0
        }


# ------------------------------
# 获取CSV中的某一行（按行号，从0开始）
# ------------------------------
@tool
def get_csv_row_by_index(
    state: Annotated[CustomState, InjectedState], 
    row_index: int,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, Any]:
    """获取本地CSV中的某一行数据（行号从0开始）"""
    csv_path = state.get("csv_local_path")
    if not csv_path or not os.path.exists(csv_path):
        return {
            "tool_call_id": tool_call_id,
            "status": "error", 
            "message": "本地CSV文件不存在", 
            "row": None
        }
    
    try:
        # 从本地文件读取数据（不加载完整文件，优化内存）
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames
            # 逐行遍历，找到目标行（避免加载全部数据）
            for idx, row in enumerate(reader):
                if idx == row_index:
                    return {
                        "tool_call_id": tool_call_id,
                        "status": "success",
                        "message": f"成功获取本地CSV第{row_index}行",
                        "row": row,
                        "columns": columns
                    }
            # 行索引超出范围
            total_rows = idx + 1 if 'idx' in locals() else 0
            return {
                "tool_call_id": tool_call_id,
                "status": "error", 
                "message": f"行索引 {row_index} 超出范围（本地CSV共{total_rows}行）", 
                "row": None
            }
    except Exception as e:
        return {
            "tool_call_id": tool_call_id,
            "status": "error", 
            "message": f"读取行失败: {str(e)}", 
            "row": None
        }


# ------------------------------
# 获取CSV中的某一列（按列名）
# ------------------------------
@tool
def get_csv_column_by_name(
    state: Annotated[CustomState, InjectedState], 
    column_name: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, Any]:
    """获取本地CSV中某一列的所有值（按列名）"""
    csv_path = state.get("csv_local_path")
    if not csv_path or not os.path.exists(csv_path):
        return {
            "tool_call_id": tool_call_id,
            "status": "error", 
            "message": "本地CSV文件不存在", 
            "column_values": []
        }
    
    try:
        # 先读取列名，校验列是否存在
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            if column_name not in columns:
                return {
                    "tool_call_id": tool_call_id,
                    "status": "error", 
                    "message": f"列名 '{column_name}' 不存在。可用列: {columns}", 
                    "column_values": []
                }
        
        # 再读取目标列（逐行读取，不加载全部数据）
        column_values = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                column_values.append(row[column_name])
        
        return {
            "tool_call_id": tool_call_id,
            "status": "success",
            "message": f"成功获取本地CSV列 '{column_name}' 的 {len(column_values)} 个值",
            "column_values": column_values,
            "columns": columns
        }
    except Exception as e:
        return {
            "tool_call_id": tool_call_id,
            "status": "error", 
            "message": f"读取列失败: {str(e)}", 
            "column_values": []
        }


# ------------------------------
# 向CSV插入一行数据（追加到末尾）
# ------------------------------
@tool
def insert_csv_row(
    state: Annotated[CustomState, InjectedState], 
    new_row: Dict[str, str],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, Any]:
    """向本地CSV文件末尾插入一行新数据（必须与表结构兼容）"""
    csv_path = state.get("csv_local_path")
    csv_meta = state.get("csv_meta", {})
    current_version = csv_meta.get("version", 0)
    
    if not csv_path or not os.path.exists(csv_path):
        return {
            "tool_call_id": tool_call_id,
            "status": "error", 
            "message": "本地CSV文件不存在", 
            "row_count": 0,
            "csv_updated": False,
            "new_csv_version": current_version
        }
    
    try:
        # 读取本地文件现有数据
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)
            fieldnames = reader.fieldnames or []
        
        if not fieldnames:
            return {
                "tool_call_id": tool_call_id,
                "status": "error", 
                "message": "CSV无字段头，无法插入", 
                "row_count": 0,
                "csv_updated": False,
                "new_csv_version": current_version
            }
        
        # 补全缺失字段
        missing_fields = set(fieldnames) - set(new_row.keys())
        message_extra = f"（警告：缺失字段 {list(missing_fields)}，已自动填充为空字符串）" if missing_fields else ""
        complete_row = {field: new_row.get(field, "") for field in fieldnames}
        
        # 追加新行到本地文件（追加模式，避免覆盖）
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(complete_row)
        
        # 更新元数据（总行数+1、版本号+1）
        new_version = current_version + 1
        new_row_count = len(existing_rows) + 1
        new_csv_meta = {
            **csv_meta,
            "row_count": new_row_count,
            "version": new_version,
            "last_updated": os.path.getmtime(csv_path)  # 最后修改时间
        }
        # 同步更新state中的元数据
        state["csv_meta"] = new_csv_meta

        return {
            "tool_call_id": tool_call_id,
            "status": "success",
            "message": f"成功向本地CSV插入1行数据{message_extra}。当前总行数: {new_row_count}，版本号: {new_version}",
            "row_count": new_row_count,
            "csv_updated": True,
            "new_csv_version": new_version,
            "csv_meta": new_csv_meta
        }
    except Exception as e:
        return {
            "tool_call_id": tool_call_id,
            "status": "error", 
            "message": f"插入行失败: {str(e)}", 
            "row_count": len(existing_rows) if 'existing_rows' in locals() else 0,
            "csv_updated": False,
            "new_csv_version": current_version
        }


# ------------------------------
# 基于CSV中两列时间字段计算差值并统计（列名指定）
# ------------------------------
@tool
def calculate_time_diff_from_csv_columns(
    state: Annotated[CustomState, InjectedState],
    column1: str,
    column2: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, Any]:
    """从本地CSV中提取两列时间数据，计算 column1 - column2 的差值，并返回统计分析"""
    csv_path = state.get("csv_local_path")
    if not csv_path or not os.path.exists(csv_path):
        return {
            "tool_call_id": tool_call_id,
            "status": "error",
            "message": "本地CSV文件不存在",
            "statistics": None,
            "top_overtime_samples": None
        }

    try:
        # 从本地文件读取数据
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []

        if not fieldnames:
            return {
                "tool_call_id": tool_call_id,
                "status": "error", 
                "message": "CSV无字段头", 
                "statistics": None, 
                "top_overtime_samples": None
            }

        # 校验列存在性
        if column1 not in fieldnames:
            return {
                "tool_call_id": tool_call_id,
                "status": "error", 
                "message": f"列 '{column1}' 不存在。可用列: {fieldnames}", 
                "statistics": None, 
                "top_overtime_samples": None
            }
        if column2 not in fieldnames:
            return {
                "tool_call_id": tool_call_id,
                "status": "error", 
                "message": f"列 '{column2}' 不存在。可用列: {fieldnames}", 
                "statistics": None, 
                "top_overtime_samples": None
            }

        # 提取时间列数据并计算差值
        total = len(rows)
        if total == 0:
            return {
                "tool_call_id": tool_call_id,
                "status": "success", 
                "message": "本地CSV无数据行", 
                "statistics": {"total_pairs": 0}, 
                "top_overtime_samples": []
            }

        positive = 0
        negative = 0
        zero = 0
        invalid = 0
        overtime_samples = []

        for idx, row in enumerate(rows):
            t1_str = row[column1]
            t2_str = row[column2]
            t1 = parse_datetime(t1_str)
            t2 = parse_datetime(t2_str)

            if not t1 or not t2:
                invalid += 1
                continue

            diff_sec = (t1 - t2).total_seconds()
            if diff_sec > 0:
                positive += 1
                overtime_samples.append({
                    "index": idx,
                    "time1": t1_str,
                    "time2": t2_str,
                    "difference_seconds": round(diff_sec, 2),
                    "difference_minutes": round(diff_sec / 60, 2),
                    "full_row": row
                })
            elif diff_sec < 0:
                negative += 1
            else:
                zero += 1

        # 处理统计结果
        top_overtime = sorted(overtime_samples, key=lambda x: x["difference_seconds"], reverse=True)[:5]
        stats = {
            "total_pairs": total,
            "positive_count": positive,   # column1 > column2（如实际晚于计划）
            "negative_count": negative,   # column1 < column2（提前）
            "zero_count": zero,
            "invalid_count": invalid,
            "positive_ratio": round(positive / total * 100, 2) if total > 0 else 0,
            "negative_ratio": round(negative / total * 100, 2) if total > 0 else 0
        }

        return {
            "tool_call_id": tool_call_id,
            "status": "success",
            "message": f"成功对本地CSV列 '{column1}' 与 '{column2}' 进行时间差分析（共{total}行）",
            "statistics": stats,
            "top_overtime_samples": top_overtime
        }

    except Exception as e:
        return {
            "tool_call_id": tool_call_id,
            "status": "error",
            "message": f"处理CSV列时间差时出错: {str(e)}",
            "statistics": None,
            "top_overtime_samples": None
        }


# ------------------------------
# 获取当前内存CSV的列名（字段头）
# ------------------------------
@tool
def get_csv_columns(
    state: Annotated[CustomState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, Any]:
    """获取本地CSV的列名，无需加载完整数据"""
    csv_path = state.get("csv_local_path")
    if not csv_path or not os.path.exists(csv_path):
        return {
            "tool_call_id": tool_call_id,
            "status": "error",
            "message": "本地CSV文件不存在，请先执行 query_data",
            "columns": []
        }

    try:
        # 仅读取列名，不读取数据行（高效）
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

        return {
            "tool_call_id": tool_call_id,
            "status": "success",
            "message": f"成功获取本地CSV的 {len(fieldnames)} 个列名",
            "columns": fieldnames
        }
    except Exception as e:
        return {
            "tool_call_id": tool_call_id,
            "status": "error",
            "message": f"读取CSV列名失败: {str(e)}",
            "columns": []
        }


# ------------------------------
# 统计CSV中指定列的空值情况(column_name指定)
# ------------------------------
@tool
def count_missing_values_in_column(
    state: Annotated[CustomState, InjectedState], 
    column_name: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Dict[str, Any]:
    """统计本地CSV中指定列的空值（缺失值）数量和比例"""
    csv_path = state.get("csv_local_path")
    if not csv_path or not os.path.exists(csv_path):
        return {
            "tool_call_id": tool_call_id,
            "status": "error",
            "message": "本地CSV文件不存在",
            "column": column_name,
            "total_rows": 0,
            "missing_count": 0,
            "missing_ratio_percent": 0.0,
            "non_missing_count": 0,
            "sample_missing_row_indices": []
        }

    try:
        # 先校验列存在性
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            if column_name not in fieldnames:
                return {
                    "tool_call_id": tool_call_id,
                    "status": "error",
                    "message": f"列 '{column_name}' 不存在。可用列: {fieldnames}",
                    "column": column_name,
                    "total_rows": 0,
                    "missing_count": 0,
                    "missing_ratio_percent": 0.0,
                    "non_missing_count": 0,
                    "sample_missing_row_indices": []
                }
        
        # 逐行统计空值（不加载全部数据）
        total_rows = 0
        missing_count = 0
        missing_indices = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                total_rows += 1
                value = row.get(column_name, "")
                if value is None or str(value).strip() == "":
                    missing_count += 1
                    missing_indices.append(idx)
        
        # 计算结果
        non_missing_count = total_rows - missing_count
        missing_ratio = round(missing_count / total_rows * 100, 2) if total_rows > 0 else 0.0
        sample_missing = missing_indices[:5]  # 取前5个空值行索引

        return {
            "tool_call_id": tool_call_id,
            "status": "success",
            "message": f"本地CSV列 '{column_name}' 空值分析完成",
            "column": column_name,
            "total_rows": total_rows,
            "missing_count": missing_count,
            "missing_ratio_percent": missing_ratio,
            "non_missing_count": non_missing_count,
            "sample_missing_row_indices": sample_missing
        }

    except Exception as e:
        return {
            "tool_call_id": tool_call_id,
            "status": "error",
            "message": f"统计空值时出错: {str(e)}",
            "column": column_name,
            "total_rows": 0,
            "missing_count": 0,
            "missing_ratio_percent": 0.0,
            "non_missing_count": 0,
            "sample_missing_row_indices": []
        }


def get_csv_tools() -> List[BaseTool]:
    return [
        get_csv_results,
        get_csv_row_by_index,
        get_csv_column_by_name,
        insert_csv_row,
        calculate_time_diff_from_csv_columns,
        get_csv_columns,
        count_missing_values_in_column
    ]