import os
from typing import Any, Annotated
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt import InjectedState
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool, InjectedToolCallId
from langchain_community.graphs import Neo4jGraph
from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langgraph.types import Command, Send
from langmem import create_manage_memory_tool, create_search_memory_tool
from langgraph.graph import StateGraph, START, MessagesState, END

from custom_tools import get_neo4j_tools, get_report_tools
from common.prompt import neo4j_analysis_prompt
from .search.mapReduce import MapReduceSearchAgent
from common.memory_state import MapReduceState, CustomState
from langgraph.graph import END

load_dotenv()

@tool
def map_reduce_search_tool(
    state: Annotated[CustomState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    level: int
):
    """
    调用 MapReduceSearchAgent 进行检索。
    args：
        query: 检索查询语句
        level: 0、1、2....，数值越小表示社区越 “顶层”（抽象、范围大），数值越大表示社区越 “底层”（具体、范围小）。
    """
    map_reduce_agent = MapReduceSearchAgent()
    result = map_reduce_agent.search(query, level)
    return {
        "tool_call_id": tool_call_id,
        "status": "success", 
        "message": result,
    }

class AnalysisAgent:
    """
    负责根据用户输入的需求，检索 Neo4j 图数据库并生成结构化分析报告。
    """

    def __init__(self) -> None:
        self.llm = self._init_llm()
        self.store = self._init_memory_store()
        self.tools = self._init_tools()
        self.supervisor = self._init_supervisor()

    def _init_memory_store(self):
        """初始化长期记忆存储"""
        embedding_model = os.getenv("EMBEDDING_MODEL")
        embedding_provider = os.getenv("EMBEDDING_PROVIDER")
        embedding_dim = int(os.getenv("EMBEDDING_DIM", "768"))

        embeddings = init_embeddings(
            model=embedding_model,
            provider=embedding_provider,
            model_kwargs={
                "device": "cpu",
                "local_files_only": True,
            }
        )

        return InMemoryStore(
            index={
                'embed': embeddings,
                'dims': embedding_dim,
            }
        )

    def _init_tools(self):
        """初始化工具集"""
        tools = []
        tools.extend(get_neo4j_tools())
        tools.extend(get_report_tools())
        tools.append(map_reduce_search_tool)

        return tools
    

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.3,
        )

    def _init_supervisor(self) -> Any:
        """构建分析智能体"""
        supervisor = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=neo4j_analysis_prompt,
            name="analysis_agent",
        )

        return supervisor
    
    def get_agent(self):
        return self.supervisor
    
if __name__ == "__main__":
    from common.utils import pretty_print_messages
    analysis = AnalysisAgent().get_agent()
    for chunk in analysis.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "我想知道申请奖学金需要提供什么材料",
                }
            ]
        },
        subgraphs=True,
    ):
        pretty_print_messages(chunk, last_message=True)