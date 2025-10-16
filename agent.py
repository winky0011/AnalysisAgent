from langchain_core.messages import HumanMessage, AIMessage

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langmem import create_memory_store_manager, ReflectionExecutor
from langgraph.func import entrypoint
from langchain_core.runnables import RunnableConfig

from dotenv import load_dotenv
import os
from typing import Any, List

from memoryState import CustomState, AnalysisMemory
from customTools import get_all_tools
from prompt import system_prompt, memory_prompt

load_dotenv()

class AnalysisWorkflow:
    """
    分析工作流类，用于构建具备长期记忆与工具调用能力的智能体。
    
    负责初始化语言模型、嵌入模型、工具集、记忆存储，并提供图构建接口。
    """

    def __init__(self) -> None:
        # 按顺序初始化各组件
        self.tools = self._init_tools()
        self.llm = self._init_llm()
        self.store = self._init_memory_store()
        self.memory_manager = self._init_memory_manager()
        self.reflection_executor = self._init_reflection_executor()
        self.agent = self._init_agent()

    def _init_tools(self):
        """初始化工具集"""
        return get_all_tools()

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.5,
        )

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

    def _init_agent(self) -> Any:
        """
        构建并返回 ReAct 智能体图（Agent Graph）。
        
        每次调用都会创建一个新的智能体实例，确保状态隔离。
        """
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
            store=self.store,
            state_schema=CustomState,
        )
    

analysis_workflow = AnalysisWorkflow()

@entrypoint(store=analysis_workflow.store)
async def analysis_chat(
    messages: List[Any],
    config: RunnableConfig,
) -> dict:
    """
    带长期记忆的数据分析聊天入口。
    
    - 自动从历史中检索相关分析记忆
    - 调用 ReAct Agent 执行工具链分析
    - 异步保存最终结论到长期记忆
    """
    # === 统一输入为 Message 对象（兼容 dict 和 Message）===
    normalized_messages = []
    for m in messages:
        if isinstance(m, dict):
            if m["role"] == "user":
                normalized_messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                normalized_messages.append(AIMessage(content=m["content"]))
            else:
                # 忽略 system/tool 等（或按需处理）
                continue
        else:
            normalized_messages.append(m)

    if not normalized_messages:
        raise ValueError("No valid messages provided")

    user_query = normalized_messages[0].content if normalized_messages else ""

    # === 检索相关历史记忆 ===
    memories = await analysis_workflow.memory_manager.asearch(
        query=user_query,
        config=config
    )
    memory_context = "\n".join(
        f"- Query: {m.value.query}\n  Answer: {m.value.final_answer}"
        for m in memories
    ) if memories else ""

    # === 构建带记忆的系统提示 ===
    enriched_system = f"""{system_prompt}

## Prior Analyses (if relevant):
{memory_context}"""

    # === 调用 agent ===
    input_for_agent = [{"role": "system", "content": enriched_system}] + [
        {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
        for m in normalized_messages
    ]

    response = await analysis_workflow.agent.ainvoke(
        {"messages": input_for_agent},
        config=config
    )

    # === 从 response 中提取 final answer ===
    final_answer = ""
    for msg in reversed(response["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            final_answer = msg.content
            break

    # === 异步提交记忆（后台处理）===
    try:
        analysis_workflow.reflection_executor.submit(
            {
                "messages": [
                    {"role": "user", "content": user_query},
                    {"role": "assistant", "content": final_answer},
                ]
            },
            config=config,
            after_seconds=0,
        )
    except Exception as e:
        # 可替换为日志记录
        print(f"[Memory Reflection Error] {e}")

    # === 返回响应 ===
    return {"messages": response["messages"]}