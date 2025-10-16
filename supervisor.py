from langchain.chat_models import init_chat_model
from langgraph_supervisor import create_supervisor

from dotenv import load_dotenv
import os
from typing import Any, List

from prompt import supervisor_prompt
from nodes import Text2SQLAgent, StatisticsAgent

load_dotenv()

class SupervisorAgent:
    """
    协调多个智能体的智能体。
    """

    def __init__(self) -> None:
        # 按顺序初始化各组件
        self.agents = self._init_agents()
        self.llm = self._init_llm()
        self.agent = self._init_agent()

    def _init_agents(self):
        """初始化智能体集"""
        return [Text2SQLAgent().get_agent(), StatisticsAgent().get_agent()]

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.5,
        )

    def _init_agent(self) -> Any:
        """
        构建并返回 ReAct 智能体图（Agent Graph）。
        
        每次调用都会创建一个新的智能体实例，确保状态隔离。
        """
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.agents,  # 传入你已实现的两个工具 Agent
            prompt=supervisor_prompt,
            add_handoff_back_messages=True,  # 开启 Agent 完成后自动回调 Supervisor
            output_mode="full_history"  # 输出完整的消息历史（便于调试）
        ).compile()  # 编译为可运行的图结构
        
        return supervisor