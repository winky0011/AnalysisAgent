import os
from typing import Any
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from langchain_community.graphs import Neo4jGraph
from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langmem import create_manage_memory_tool, create_search_memory_tool

# 替换原 MySQL 自定义工具为 Neo4j 和报告生成相关工具
from custom_tools import get_neo4j_tools, get_report_generation_tools
from memory_state import CustomState
from prompt import neo4j_analysis_prompt  # 新增的 Neo4j 分析提示词

load_dotenv()

class Neo4jAnalysisAgent:
    """
    负责根据用户输入的需求，检索 Neo4j 图数据库并生成结构化分析报告。
    """

    def __init__(self) -> None:
        self.graph = self._init_neo4j()  # 初始化 Neo4j 连接
        self.llm = self._init_llm()
        self.store = self._init_memory_store()
        self.tools = self._init_tools()
        self.agent = self._init_agent()

    def _init_neo4j(self):
        """初始化 Neo4j 图数据库连接"""
        return Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USER"),
            password=os.getenv("NEO4J_PASSWORD"),
            database=os.getenv("NEO4J_DATABASE", "neo4j")  # 默认为 neo4j 数据库
        )

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
        """初始化工具集（替换为 Neo4j 工具和报告生成工具）"""
        tools = []

        # 2. 自定义 Neo4j 工具（例如复杂关系查询、图数据统计等）
        tools.extend(get_neo4j_tools(self.graph))

        # 3. 报告生成工具（例如格式化输出、图表生成、PDF 导出等）
        # tools.extend(get_report_generation_tools())

        # 4. 记忆管理工具（复用，用于上下文关联）
        tools.extend([
            create_manage_memory_tool(namespace=("neo4j_analysis_memories", "{langgraph_user_id}")),
            create_search_memory_tool(namespace=("neo4j_analysis_memories", "{langgraph_user_id}")),
        ])

        return tools

    def _init_llm(self):
        """初始化大语言模型（保持原有配置，可根据需要调整）"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.3,  # 降低随机性，确保报告严谨性
        )

    def _init_agent(self) -> Any:
        """构建 Neo4j 分析智能体（核心逻辑调整）"""
        # 格式化分析提示词，注入 Neo4j 特性（如节点、关系、Cypher 语法）
        system_prompt = neo4j_analysis_prompt.format(
            node_types=self.graph.get_node_types(),  # 动态获取数据库中的节点类型
            relationship_types=self.graph.get_relationship_types(),  # 动态获取关系类型
            report_format="markdown"  # 指定报告输出格式（可改为 html、text 等）
        )

        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
            state_schema=CustomState,  # 启用自定义状态管理（用于跟踪报告生成进度）
            name="neo4j_analysis_agent",
            store=self.store,
        )
    
    def get_agent(self):
        return self.agent