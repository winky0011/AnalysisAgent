from langgraph.prebuilt.chat_agent_executor import AgentState

from pydantic import BaseModel
from typing import NotRequired
from io import StringIO

# ------------------------------
# 短期记忆
# ------------------------------
class CustomState(AgentState):
    user_name: NotRequired[str]
    user_id: NotRequired[str]
    csv_buffer: NotRequired[StringIO]  # csv文件内存

# ------------------------------
# 长期记忆的存储结构
# ------------------------------
class AnalysisMemory(BaseModel):
    """记录一次数据分析任务的输入与结论"""
    query: str          # 用户原始问题
    final_answer: str   # agent 最终输出的分析结论
    context: str        # 提取自对话的上下文说明