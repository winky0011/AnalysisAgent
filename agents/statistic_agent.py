import os
from typing import Any, List
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langmem import create_memory_store_manager, ReflectionExecutor
from langmem import create_manage_memory_tool, create_search_memory_tool

from custom_tools import get_csv_tools, get_math_tools
from common.prompt import statistic_prompt
from common.memory_state import CustomState, AnalysisMemory

load_dotenv()

class StatisticsAgent:
    """
    拆解问题，依据问题链路对csv进行操作，生成统计结果
    """

    def __init__(self) -> None:
        self.llm = self._init_llm()
        self.store = self._init_memory_store()
        self.tools = self._init_tools()
        self.agent = self._init_agent()

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

    def _init_memory_manager(self):
        """初始化记忆管理器"""
        return create_memory_store_manager(
            self.llm,
            schemas=[AnalysisMemory],
            namespace=("analysis_memories", "{langgraph_user_id}"),
            store=self.store,
            # instructions=memory_prompt,
        )

    def _init_reflection_executor(self):
        """初始化后台反射执行器"""
        return ReflectionExecutor(
            self.memory_manager,
            store=self.store
        )

    def _init_tools(self):
        """初始化工具集"""
        tools = get_math_tools()
        tools.extend(get_csv_tools())  # 自定义工具
        tools.extend([
            create_manage_memory_tool(namespace=("statistic_memories", "{langgraph_user_id}")),
            create_search_memory_tool(namespace=("statistic_memories", "{langgraph_user_id}")),
        ])
        return tools

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.5,
        )

    def _init_agent(self) -> Any:
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=statistic_prompt,
            name="statistic_agent",
            store=self.store,
        )
    
    def get_agent(self):
        return self.agent