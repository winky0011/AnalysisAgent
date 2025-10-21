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
        # tools.extend(get_neo4j_tools())
        tools.extend(get_report_tools())

        assign_agent = self._init_agents()
        tools.extend(assign_agent)

        return tools
    
    def _init_agents(self):
        """初始化智能体集"""
        assign_to_mapreduce_workflow = self._create_handoff_tool(
            agent_name="map_reduce_workflow",
            description="将任务转交给MapReduce workflow，处理需分治计算的检索需求",
        )

        return [assign_to_mapreduce_workflow]

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.3,
        )
    
    def _create_handoff_tool(self, *, agent_name: str, description: str | None = None):
        name = f"transfer_to_{agent_name}"
        description = description or f"将任务转交给MapReduce workflow，处理需分治计算的检索需求"

        @tool(name, description=description)
        def handoff_tool(
            custom_state: Annotated[CustomState, InjectedState],  # 输入CustomState
            tool_call_id: Annotated[str, InjectedToolCallId],
        ) -> Command:
            # 1. 生成工具调用成功消息（用于追踪转交记录）
            tool_message = {
                "role": "tool",
                "content": (
                    f"已成功转交任务至{agent_name}，携带信息："
                    f"用户名：{custom_state.user_name or '未提供'}，"
                    f"CSV路径：{custom_state.csv_local_path or '无'}"
                ),
                "name": name,
                "tool_call_id": tool_call_id,
            }

            mapreduce_state = MapReduceState(
                query=next(
                    msg["content"] for msg in custom_state["messages"] 
                    if msg["role"] == "user"  # 确保只取用户输入作为query
                ),
                level=1,  # 若需动态调整，可从custom_state提取（如custom_state.get("level", 1)）
                remaining_steps=24,
                communities=[],
                intermediate_results=[],
                final_answer="",
            )

            return Command(
                goto=agent_name,
                update=mapreduce_state,  # 更新 MapReduceState
                graph=Command.PARENT,
            )

        return handoff_tool

    def _init_supervisor(self) -> Any:
        """构建分析智能体"""
        analysis_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=neo4j_analysis_prompt,
            name="analysis_agent",
        )

        map_reduce_workflow = MapReduceSearchAgent().get_agent()

        supervisor = (
            StateGraph(MessagesState)
            .add_node(analysis_agent, destinations=("map_reduce_workflow", END))
            .add_node(map_reduce_workflow)
            .add_edge(START, "analysis_agent")
            .add_edge("map_reduce_workflow", "analysis_agent")
            .add_edge("analysis_agent", END)
            .compile()
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