from langgraph.prebuilt.chat_agent_executor import AgentState

from pydantic import BaseModel
from typing import NotRequired, List, Dict, Any, Optional, Callable
from pydantic import Field

# ------------------------------
# 短期记忆
# ------------------------------
class CustomState(AgentState):
    user_name: NotRequired[str]
    user_id: NotRequired[str]
    csv_local_path: NotRequired[str]  # csv文件
    csv_meta: NotRequired[Dict[str, Any]]  # csv文件元数据


class MapReduceState(BaseModel):
    query: str = Field(description="用户查询语句")
    level: int = Field(description="社区层级")
    data_items: List[dict] = Field(default_factory=list, description="从数据库获取的原始数据")
    intermediate_results: List[str] = Field(default_factory=list, description="Map阶段的中间结果")
    final_result: str = Field(default="", description="Reduce阶段的最终结果")
    llm: Any = Field(description="大语言模型实例")
    map_system_prompt: str = Field(description="Map阶段系统提示词")
    reduce_system_prompt: str = Field(description="Reduce阶段系统提示词")
    response_type: str = Field(default="多个段落", description="最终响应格式")
    data_query: str = Field(description="获取数据的Cypher查询")
    map_process_func: Optional[Callable] = Field(default=None, description="自定义Map处理函数")
    reduce_process_func: Optional[Callable] = Field(default=None, description="自定义Reduce处理函数")

# ------------------------------
# 长期记忆的存储结构
# ------------------------------
class AnalysisMemory(BaseModel):
    """记录一次数据分析任务的输入与结论"""
    query: str          # 用户原始问题
    final_answer: str   # agent 最终输出的分析结论
    context: str        # 提取自对话的上下文说明