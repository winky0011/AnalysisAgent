# 通用工具
from langchain_core.tools import tool, InjectedToolCallId, BaseTool
from common.skills import *

@tool
def get_path(intent: str) -> str:
    """
    依据用户意图获取对应数据库取数路径，预定义的意图为：
    - 1. MRP
    - 2. MDP
    - 3. 其他
    """
    if intent == "MRP":
        return MRP
    elif intent == "MDP":
        return MDP
    else:
        return "其他"
    
def get_toos():
    return [
        get_path,
    ]