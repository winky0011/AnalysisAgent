from langchain_core.tools import tool, InjectedToolCallId, BaseTool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

import csv
from typing import Dict, Any, Annotated, List
from io import StringIO

from customState import CustomState
from utils import *

# ------------------------------
# 获取记忆里的CSV结果
# ------------------------------
@tool
def get_csv_results(state: Annotated[CustomState, InjectedState]) -> Dict[str, str]:
    """
    读取记忆中的 CSV 内容，非必要不使用，可能超出上下文范围
    返回:
        包含CSV数据和状态的字典
    """
    csv_buffer = state.get("csv_buffer")
    if csv_buffer:
        csv_buffer.seek(0)
        return {
            "status": "success",
            "message": "获取上一次查询的CSV成功",
            "csv_data": csv_buffer.getvalue()
        }
    else:
        return {"status": "error", "message": "无历史CSV结果，请先执行query_data_test", "csv_data": ""}
    

# ------------------------------
# 获取CSV中的某一行（按行号，从0开始）
# ------------------------------
@tool
def get_csv_row_by_index(state: Annotated[CustomState, InjectedState], row_index: int) -> Dict[str, Any]:
    """
    获取当前内存CSV中的某一行数据（行号从0开始）
    参数:
        row_index: 行索引（整数，如0表示第一行）
    返回:
        包含该行数据的字典（字段名作为key）
    """
    csv_buffer = state.get("csv_buffer")  # 获取短期记忆中的csv文件

    if csv_buffer is None:
        return {"status": "error", "message": "无CSV数据，请先执行`query_data_test`或`filter_data_by_date_range`", "row": None}
    
    try:
        csv_buffer.seek(0)
        reader = csv.DictReader(csv_buffer)
        rows = list(reader)
        
        if row_index < 0 or row_index >= len(rows):
            return {"status": "error", "message": f"行索引 {row_index} 超出范围（共{len(rows)}行）", "row": None}
        
        return {
            "status": "success",
            "message": f"成功获取第{row_index}行",
            "row": rows[row_index]
        }
    except Exception as e:
        return {"status": "error", "message": f"读取行失败: {str(e)}", "row": None}


# ------------------------------
# 获取CSV中的某一列（按列名）
# ------------------------------
@tool
def get_csv_column_by_name(state: Annotated[CustomState, InjectedState], column_name: str) -> Dict[str, Any]:
    """
    获取当前内存CSV中某一列的所有值（按列名）
    参数:
        column_name: 列名（如"project_id"）
    返回:
        包含该列所有值的列表
    """
    csv_buffer = state.get("csv_buffer")  # 获取短期记忆中的csv文件
    if csv_buffer is None:
        return {"status": "error", "message": "无CSV数据，请先执行`query_data_test`或`filter_data_by_date_range`", "column_values": []}
    
    try:
        csv_buffer.seek(0)
        reader = csv.DictReader(csv_buffer)
        headers = reader.fieldnames
        
        if not headers or column_name not in headers:
            return {"status": "error", "message": f"列名 '{column_name}' 不存在。可用列: {list(headers) if headers else []}", "column_values": []}
        
        column_values = [row[column_name] for row in reader]
        
        return {
            "status": "success",
            "message": f"成功获取列 '{column_name}' 的 {len(column_values)} 个值",
            "column_values": column_values
        }
    except Exception as e:
        return {"status": "error", "message": f"读取列失败: {str(e)}", "column_values": []}


# ------------------------------
# 向CSV插入一行数据（追加到末尾）
# ------------------------------
@tool
def insert_csv_row(state: Annotated[CustomState, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId],new_row: Dict[str, str]) -> Dict[str, Any]:
    """
    向当前内存CSV末尾插入一行新数据（必须包含所有字段，或至少与表结构兼容）
    参数:
        new_row: 字典，键为列名，值为字符串（如{"id": "101", "name": "test"})
    返回:
        操作结果状态
    """
    csv_buffer = state.get("csv_buffer")  # 获取短期记忆中的csv文件
    if csv_buffer is None:
        return {"status": "error", "message": "无CSV数据，请先执行`query_data_test`或`filter_data_by_date_range`", "row_count": 0}
    
    try:
        # 读取现有数据
        csv_buffer.seek(0)
        reader = csv.DictReader(csv_buffer)
        existing_rows = list(reader)
        fieldnames = reader.fieldnames
        
        if not fieldnames:
            return {"status": "error", "message": "CSV无字段头，无法插入", "row_count": 0}
        
        # 验证 new_row 是否包含必要字段（宽松处理：允许缺失字段，但会警告）
        missing_fields = set(fieldnames) - set(new_row.keys())
        extra_fields = set(new_row.keys()) - set(fieldnames)
        if extra_fields:
            # 可选：严格模式可报错，这里仅警告
            pass  # 或记录日志
        
        # 补全缺失字段为空字符串
        complete_row = {field: new_row.get(field, "") for field in fieldnames}
        
        # 添加新行
        existing_rows.append(complete_row)
        
        # 重新写入 csv_buffer
        csv_buffer = StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
        csv_buffer.seek(0)

        return Command(update={
            'csv_buffer': csv_buffer,
            'messages': [
                ToolMessage(
                    content=f"成功插入1行数据。当前总行数: {len(existing_rows)}",  # 必须：消息内容通过 content 传入
                    status="success",  # 额外元数据：工具调用状态
                    row_count=len(existing_rows),  # 额外元数据：自定义统计字段
                    tool_call_id=tool_call_id
                )
            ]
        })
    except Exception as e:
        return {"status": "error", "message": f"插入行失败: {str(e)}", "row_count": 0}


# ------------------------------
# 基于CSV中两列时间字段计算差值并统计（列名指定）
# ------------------------------
@tool
def calculate_time_diff_from_csv_columns(
    state: Annotated[CustomState, InjectedState],
    column1: str,
    column2: str
) -> Dict[str, Any]:
    """
    从当前内存CSV中提取两列时间数据，计算 column1 - column2 的差值，并返回统计分析。
    
    参数:
        column1: 第一列时间字段名（如 "actual_end"）
        column2: 第二列时间字段名（如 "plan_end"）
    
    返回:
        包含差值统计（正值/负值/零值数量）和超时最多的前五个样本的字典
    """
    csv_buffer = state.get("csv_buffer")  # 获取短期记忆中的csv文件
    if csv_buffer is None:
        return {
            "status": "error",
            "message": "无CSV数据，请先执行 query_data_test 或 filter_data_by_date_range",
            "statistics": None,
            "top_overtime_samples": None
        }

    try:
        csv_buffer.seek(0)
        reader = csv.DictReader(csv_buffer)
        rows = list(reader)
        fieldnames = reader.fieldnames

        if not fieldnames:
            return {"status": "error", "message": "CSV无字段头", "statistics": None, "top_overtime_samples": None}

        # 校验列是否存在
        if column1 not in fieldnames:
            return {"status": "error", "message": f"列 '{column1}' 不存在。可用列: {list(fieldnames)}", "statistics": None, "top_overtime_samples": None}
        if column2 not in fieldnames:
            return {"status": "error", "message": f"列 '{column2}' 不存在。可用列: {list(fieldnames)}", "statistics": None, "top_overtime_samples": None}

        # 提取两列数据
        list1 = [row[column1] for row in rows]
        list2 = [row[column2] for row in rows]

        # 复用已有的批量计算逻辑（但不暴露给用户）
        total = len(list1)
        if total == 0:
            return {"status": "success", "message": "CSV无数据行", "statistics": {"total_pairs": 0}, "top_overtime_samples": []}

        positive = 0
        negative = 0
        zero = 0
        invalid = 0
        differences = []
        overtime_samples = []

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

            if diff_sec > 0:
                positive += 1
                overtime_samples.append({
                    "index": idx,
                    "time1": t1_str,
                    "time2": t2_str,
                    "difference_seconds": round(diff_sec, 2),
                    "difference_minutes": round(diff_sec / 60, 2),
                    "full_row": rows[idx]  # ✅ 保存整行原始数据
                })
            elif diff_sec < 0:
                negative += 1
            else:
                zero += 1

        # 取超时最多的前5个
        top_overtime = sorted(
            overtime_samples,
            key=lambda x: x["difference_seconds"],
            reverse=True
        )[:5]

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
            "status": "success",
            "message": f"成功对列 '{column1}' 与 '{column2}' 进行时间差分析（共{total}行）",
            "statistics": stats,
            "top_overtime_samples": top_overtime
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"处理CSV列时间差时出错: {str(e)}",
            "statistics": None,
            "top_overtime_samples": None
        }


# ------------------------------
# 获取当前内存CSV的列名（字段头）
# ------------------------------
@tool
def get_csv_columns(state: Annotated[CustomState, InjectedState]) -> Dict[str, Any]:
    """
    获取当前内存中CSV的列名，无需连接数据库。
    适用于 query_data_test、filter_data_by_date_range 或 insert_csv_row 后的CSV结构探查。
    
    返回:
        包含列名列表的字典
    """
    csv_buffer = state.get("csv_buffer")  # 获取短期记忆中的csv文件
    if csv_buffer is None:
        return {
            "status": "error",
            "message": "无CSV数据，请先执行 query_data_test 或 filter_data_by_date_range",
            "columns": []
        }

    try:
        csv_buffer.seek(0)
        reader = csv.DictReader(csv_buffer)
        fieldnames = reader.fieldnames  # 可能为 None 如果 CSV 为空

        if fieldnames is None:
            return {
                "status": "success",
                "message": "CSV存在但无字段头",
                "columns": []
            }

        return {
            "status": "success",
            "message": f"成功获取 {len(fieldnames)} 个列名",
            "columns": list(fieldnames)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"读取CSV列名失败: {str(e)}",
            "columns": []
        }


# ------------------------------
# 统计CSV中指定列的空值情况(column_name指定)
# ------------------------------
@tool
def count_missing_values_in_column(state: Annotated[CustomState, InjectedState], column_name: str) -> Dict[str, Any]:
    """
    统计当前内存CSV中指定列的空值（缺失值）数量和比例。
    空值定义为：None、空字符串 ""、或仅包含空白字符（如 "   "）。
    
    参数:
        column_name: 要检查的列名（字符串）
    
    返回:
        包含空值统计信息的字典
    """
    csv_buffer = state.get("csv_buffer")  # 获取短期记忆中的csv文件
    if csv_buffer is None:
        return {
            "status": "error",
            "message": "无CSV数据，请先执行 query_data_test 或 filter_data_by_date_range",
            "column": column_name,
            "total_rows": 0,
            "missing_count": 0,
            "missing_ratio": 0.0,
            "non_missing_count": 0,
            "sample_missing_indices": []
        }

    try:
        csv_buffer.seek(0)
        reader = csv.DictReader(csv_buffer)
        rows = list(reader)
        fieldnames = reader.fieldnames

        if not fieldnames:
            return {
                "status": "error",
                "message": "CSV无字段头",
                "column": column_name,
                "total_rows": 0,
                "missing_count": 0,
                "missing_ratio": 0.0,
                "non_missing_count": 0,
                "sample_missing_indices": []
            }

        if column_name not in fieldnames:
            return {
                "status": "error",
                "message": f"列 '{column_name}' 不存在。可用列: {list(fieldnames)}",
                "column": column_name,
                "total_rows": 0,
                "missing_count": 0,
                "missing_ratio": 0.0,
                "non_missing_count": 0,
                "sample_missing_indices": []
            }

        total = len(rows)
        missing_indices = []

        for idx, row in enumerate(rows):
            value = row.get(column_name, "")
            # 判断是否为空：None、空字符串、或纯空白
            if value is None or str(value).strip() == "":
                missing_indices.append(idx)

        missing_count = len(missing_indices)
        non_missing_count = total - missing_count
        missing_ratio = round(missing_count / total * 100, 2) if total > 0 else 0.0

        # 返回前5个空值行索引作为样本（避免返回太多）
        sample_missing = missing_indices[:5]

        return {
            "status": "success",
            "message": f"列 '{column_name}' 空值分析完成",
            "column": column_name,
            "total_rows": total,
            "missing_count": missing_count,
            "missing_ratio_percent": missing_ratio,
            "non_missing_count": non_missing_count,
            "sample_missing_row_indices": sample_missing  # 便于用户定位问题行
        }

    except Exception as e:
        return {
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
        count_missing_values_in_column
    ]