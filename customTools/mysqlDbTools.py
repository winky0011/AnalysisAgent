from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

import os, csv
from typing import Dict, List, Optional, Any, Annotated
from io import StringIO
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

from customState import CustomState

load_dotenv()


def _connect() -> Optional[mysql.connector.MySQLConnection]:
    try:
        conn = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('MYSQL_DATABASE'),
            port=int(os.getenv('MYSQL_PORT', '3306')),
            autocommit=True
        )
        return conn
    except Error as e:
        print(f"数据库连接失败: {e}")
        return None

def _disconnect(conn):
    if conn and conn.is_connected():
        conn.close()

# ------------------------------
# 查询data_test表并返回内存CSV
# ------------------------------
@tool
def query_data_test(state: Annotated[CustomState, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId]) -> Dict[str, Any]:
    """
    查询MySQL中的data_test表，返回所有字段的数据，结果以CSV格式返回。
    此工具不接受用户输入SQL，防止注入和误操作。
    
    返回:
        包含查询状态、CSV数据、记录数的字典
    """
    query = """
        SELECT *
        FROM data_test
    """
    
    try:
        conn = _connect()
        if not conn:
            return {"status": "error", "message": "数据库连接失败", "csv_data": "", "row_count": 0}

        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        records = cursor.fetchall()
        columns = cursor.column_names if records else []

        # 内存中生成CSV
        csv_buffer = StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
        csv_buffer.seek(0)

        return Command(update={
            'csv_buffer': csv_buffer,
            'messages': [
                ToolMessage(
                    content=f"查询成功，获取{len(records)}条记录",
                    status="success",  # 额外元数据：工具调用状态
                    columns=list(columns),
                    row_count=len(records),
                    tool_call_id=tool_call_id
                )
            ]
        })
    except Error as e:
        return {"status": "error", "message": f"SQL执行错误: {str(e)}", "csv_data": "", "row_count": 0}
    finally:
        if cursor:
            cursor.close()
        if conn:
            _disconnect(conn)  # 传入 conn


# ------------------------------
# 获取MySQL中data_test表的所有字段名
# ------------------------------
@tool
def get_data_test_columns() -> Dict[str, List[str]]:
    """
    获取MySQL中data_test表的所有字段名
    返回:
        包含字段名列表的字典
    """
    query = "SHOW COLUMNS FROM data_test"
    conn = _connect()
    if not conn:
        return {"status": "error", "message": "数据库连接失败", "columns": []}
    
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [row[0] for row in cursor.fetchall()]
        return {"status": "success", "message": "获取字段成功", "columns": columns}
    except Error as e:
        return {"status": "error", "message": f"SQL执行错误: {str(e)}", "columns": []}
    finally:
        if cursor:
            cursor.close()
        if conn:
            _disconnect(conn)  # 传入 conn


# ------------------------------
# 按日期范围条件取data_test数据
# ------------------------------
@tool
def filter_data_by_date_range(state: Annotated[CustomState, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId], start_date: str, end_date: str, stage: str = "t1") -> Dict[str, str]:
    """
    查询MySQL中的data_test表，按日期范围快速过滤t1/t2阶段的计划时间数据（无需手动写SQL）
    参数:
        start_date: 开始日期（格式YYYY-MM-DD，如"2024-01-01"）
        end_date: 结束日期（格式YYYY-MM-DD，如"2024-01-31"）
        stage: 阶段（可选"t1"或"t2"，对应t1_start_schedule/t2_start_schedule字段）
    返回:
        包含CSV结果的字典
    """
    if stage not in ["t1", "t2"]:
        return {"status": "error", "message": "stage必须为't1'或't2'", "csv_data": "", "row_count": 0}
    
    # 构建安全的日期过滤SQL（避免注入风险）
    query = f"""
        SELECT * FROM data_test
        WHERE {stage}_start_schedule BETWEEN %s AND %s
        OR {stage}_end_schedule BETWEEN %s AND %s
    """
    # 调用查询工具
    conn = _connect()
    if not conn:
        return {"status": "error", "message": "数据库连接失败", "csv_data": "", "row_count": 0}
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, [f"{start_date} 00:00:00", f"{end_date} 23:59:59", 
                                f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
        records = cursor.fetchall()
        columns = cursor.column_names if records else []

        # 内存CSV生成
        csv_buffer = StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
        csv_buffer.seek(0)

        return Command(update={
            'csv_buffer': csv_buffer,
            'messages': [
                ToolMessage(
                    content=f"筛选{stage}阶段{start_date}至{end_date}的数据，共{len(records)}条",
                    status="success",  # 额外元数据：工具调用状态
                    csv_data=csv_buffer.getvalue(),
                    row_count=len(records),
                    tool_call_id=tool_call_id
                )
            ]
        })
    except Error as e:
        return {"status": "error", "message": f"筛选错误: {str(e)}", "csv_data": "", "row_count": 0}
    finally:
        if cursor:
            cursor.close()
        if conn:
            _disconnect(conn)  # 传入 conn


def get_mysql_tools() -> List[BaseTool]:
    return [
        query_data_test, 
        get_data_test_columns, 
        filter_data_by_date_range
    ]