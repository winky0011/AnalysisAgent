from langgraph.prebuilt.chat_agent_executor import AgentState
from langchain_core.messages import BaseMessage 
from typing import NotRequired, List
from io import StringIO

# ------------------------------
# 短期记忆
# ------------------------------
class CustomState(AgentState):
    user_name: NotRequired[str]
    user_id: NotRequired[str]
    csv_buffer: NotRequired[StringIO]  # csv文件内存