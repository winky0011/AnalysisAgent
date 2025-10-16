from .csv_tools import get_csv_tools
from .math_tools import get_math_tools
from .mysql_tools import get_mysql_tools
from .chart_tools import get_mcp_tools

__all__ = [
    "get_csv_tools",
    "get_math_tools",
    "get_mysql_tools",
    "get_mcp_tools"
]

def get_all_tools():
    """聚合所有工具模块的工具函数，返回工具列表"""
    all_tools = []
    all_tools.extend(get_csv_tools())
    all_tools.extend(get_math_tools())
    all_tools.extend(get_mysql_tools())

    return all_tools