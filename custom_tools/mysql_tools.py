from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

import os, csv, time
from typing import Dict, List, Optional, Any, Annotated
from io import StringIO
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

from common.memory_state import CustomState
from .tool_utils import *

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
# 获取当前数据库中有什么表
# ------------------------------
@tool
def get_mysql_tables() -> Dict[str, List[str]]:
    """
    获取当前MySQL数据库中的所有表名
    返回:
        包含表名列表的字典
    """
    query = "SHOW TABLES"
    conn = _connect()
    if not conn:
        return {"status": "error", "message": "数据库连接失败", "tables": []}
    
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        tables = [row[0] for row in cursor.fetchall()]
        return {"status": "success", "message": "获取表成功", "tables": tables}
    except Error as e:
        return {"status": "error", "message": f"SQL执行错误: {str(e)}", "tables": []}
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if conn:
            _disconnect(conn)

# ------------------------------
# 获取指定表的字段
# ------------------------------
@tool
def get_table_columns(table_name: str) -> Dict[str, List[str]]:
    """
    获取MySQL中指定表的所有字段名
    参数:
        table_name: 表名
    返回:
        包含字段名列表的字典
    """
    query = f"SHOW COLUMNS FROM {table_name}"
    conn = _connect()
    if not conn:
        return {"status": "error", "message": "数据库连接失败", "columns": []}
    
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [row[0] for row in cursor.fetchall()]
        return {"status": "success", "message": f"获取{table_name}表字段成功", "columns": columns}
    except Error as e:
        return {"status": "error", "message": f"SQL执行错误: {str(e)}", "columns": []}
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if conn:
            _disconnect(conn)


# ------------------------------
# 查询指定表并写入本地CSV，state存路径
# ------------------------------
@tool
def query_data(table_name: str, state: Annotated[CustomState, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId]) -> Dict[str, Any]:
    """
    查询MySQL中指定表的所有数据，并将结果写入本地CSV文件
    参数:
        table_name: 表名
    返回:
        包含CSV文件路径、记录数和字段名的字典
    """
    query = f"SELECT * FROM {table_name}"
    
    try:
        conn = _connect()
        if not conn:
            return {"status": "error", "message": "数据库连接失败", "csv_path": "", "row_count": 0}

        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        records = cursor.fetchall()
        columns = cursor.column_names if records else []
        row_count = len(records)

        # 1. 生成本地CSV文件
        if row_count > 0:
            # 生成时间命名的文件名
            csv_filename = generate_csv_filename(table_name)
            # 获取绝对路径
            csv_abs_path = get_absolute_csv_path(csv_filename)
            # 写入本地文件
            with open(csv_abs_path, "w", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(records)
        else:
            csv_abs_path = ""

        # 2. state中存储文件路径和元数据
        return Command(update={
            'csv_local_path': csv_abs_path,  # 核心：存储本地绝对路径
            'csv_meta': {  # 存储元数据，方便Agent快速了解文件信息
                'table_name': table_name,
                'row_count': row_count,
                'columns': list(columns),
                'create_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            },
            'messages': [
                ToolMessage(
                    content=f"查询成功：{table_name}表{row_count}条记录，已保存至本地：{csv_abs_path}",
                    status="success",
                    csv_path=csv_abs_path,
                    csv_meta=state["csv_meta"],
                    tool_call_id=tool_call_id
                )
            ]
        })
    except Error as e:
        return {"status": "error", "message": f"SQL执行错误: {str(e)}", "csv_path": "", "row_count": 0}
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if conn:
            _disconnect(conn)


# ------------------------------
# 执行SQL查询语句，结果写入本地CSV文件，state存路径
# ------------------------------
@tool
def execute_sql_query(state: Annotated[CustomState, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId], query: str) -> Dict[str, Any]:
    """
    执行MySQL查询语句，将结果写入本地CSV文件，state中存储文件路径
    参数:
        query: 要执行的SQL查询语句（仅支持SELECT操作）
    返回:
        包含执行状态、文件路径、记录数和元数据的字典
    """
    # 危险操作防护
    if any(keyword in query.lower() for keyword in ["delete", "drop", "truncate", "update", "insert"]):
        return {
            "status": "error", 
            "message": "查询语句包含危险操作（仅允许SELECT），已拒绝执行", 
            "csv_path": "", 
            "row_count": 0, 
            "csv_meta": {}
        }

    # SQL注入风险防护
    if any(char in query for char in [";", "--", "#", "/*", "*/"]):
        return {
            "status": "error", 
            "message": "查询语句包含潜在的SQL注入风险，已拒绝执行", 
            "csv_path": "", 
            "row_count": 0, 
            "csv_meta": {}
        }
    
    # 仅允许SELECT查询
    if not query.strip().lower().startswith("select"):
        return {
            "status": "error", 
            "message": "查询语句必须以SELECT开头", 
            "csv_path": "", 
            "row_count": 0, 
            "csv_meta": {}
        }

    conn = _connect()
    if not conn:
        return {
            "status": "error", 
            "message": "数据库连接失败", 
            "csv_path": "", 
            "row_count": 0, 
            "csv_meta": {}
        }
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        records = cursor.fetchall()
        columns = cursor.column_names if records else []
        row_count = len(records)

        # 生成基于查询哈希的文件名（避免重复，同时区分不同查询）
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]  # 取哈希前8位
        csv_filename = f"sql_query_{query_hash}_{time.strftime('%Y%m%d%H%M%S')}.csv"
        csv_abs_path = get_absolute_csv_path(csv_filename)

        # 写入本地CSV文件（即使记录数为0，也生成空文件方便追踪）
        with open(csv_abs_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)

        # 构建元数据（包含查询语句摘要，方便追溯）
        csv_meta = {
            "query": query[:200] + "..." if len(query) > 200 else query,  # 截断长查询
            "row_count": row_count,
            "columns": list(columns),
            "create_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "version": state.get("csv_meta", {}).get("version", 0) + 1  # 版本号自增
        }

        # 更新state：存储文件路径和元数据
        return Command(update={
            'csv_local_path': csv_abs_path,
            'csv_meta': csv_meta,
            'messages': [
                ToolMessage(
                    content=f"SQL查询成功，{row_count}条记录已保存至本地：{csv_abs_path}",
                    status="success",
                    csv_path=csv_abs_path,
                    csv_meta=csv_meta,
                    tool_call_id=tool_call_id
                )
            ]
        })
    except Error as e:
        return {
            "status": "error", 
            "message": f"SQL执行错误: {str(e)}", 
            "csv_path": "", 
            "row_count": 0, 
            "csv_meta": {}
        }
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if conn:
            _disconnect(conn)

def get_mysql_tools() -> List[BaseTool]:
    return [
        query_data,
        get_mysql_tables,
        get_table_columns,
        execute_sql_query
    ]