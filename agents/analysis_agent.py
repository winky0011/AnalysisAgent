import os
from typing import Any
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from langchain_community.graphs import Neo4jGraph
from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langmem import create_manage_memory_tool, create_search_memory_tool

from custom_tools import get_neo4j_tools, get_report_tools
from common.prompt import neo4j_analysis_prompt

load_dotenv()

class AnalysisAgent:
    """
    负责根据用户输入的需求，检索 Neo4j 图数据库并生成结构化分析报告。
    """

    def __init__(self) -> None:
        self.llm = self._init_llm()
        self.store = self._init_memory_store()
        self.tools = self._init_tools()
        self.agent = self._init_agent()

    def _init_memory_store(self):
        """初始化长期记忆存储（复用原有逻辑，用于存储历史分析记录）"""
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
        tools.extend([
            create_manage_memory_tool(namespace=("neo4j_analysis_memories", "{langgraph_user_id}")),
            create_search_memory_tool(namespace=("neo4j_analysis_memories", "{langgraph_user_id}")),
        ])

        return tools

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.3,  # 降低随机性，确保报告严谨性
        )

    def _init_agent(self) -> Any:
        """构建分析智能体"""

        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=neo4j_analysis_prompt,
            name="analysis_agent",
            store=self.store,
        )
    
    def get_agent(self):
        return self.agent
    
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