from langgraph.prebuilt.chat_agent_executor import AgentState

from pydantic import BaseModel
from typing import NotRequired, List, Dict, Any

# ------------------------------
# 短期记忆
# ------------------------------
class CustomState(AgentState):
    user_name: NotRequired[str]
    user_id: NotRequired[str]
    csv_local_path: NotRequired[str]  # csv文件
    csv_meta: NotRequired[Dict[str, Any]]  # csv文件元数据

# ------------------------------
# 长期记忆的存储结构
# ------------------------------
class AnalysisMemory(BaseModel):
    """记录一次数据分析任务的输入与结论"""
    query: str          # 用户原始问题
    final_answer: str   # agent 最终输出的分析结论
    context: str        # 提取自对话的上下文说明