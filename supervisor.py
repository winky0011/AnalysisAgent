from langchain.chat_models import init_chat_model
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from langgraph.types import Send
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.graph import StateGraph, START, MessagesState, END
from langgraph.types import Command

from dotenv import load_dotenv
import os
from typing import Any, List, Annotated

from prompt import supervisor_prompt
from nodes import Text2SQLAgent, StatisticsAgent
from memory_state import CustomState

load_dotenv()

class SupervisorAgent:
    """
    协调多个智能体的智能体。
    """
    def __init__(self) -> None:
        # 按顺序初始化各组件
        self.tools = self._init_tools()
        self.llm = self._init_llm()
        self.agent = self._init_agent()

    def _create_handoff_tool(
        self, *, agent_name: str, description: str | None = None
    ):
        name = f"transfer_to_{agent_name}"
        description = description or f"Ask {agent_name} for help."

        @tool(name, description=description)
        def handoff_tool(
            # this is populated by the supervisor LLM
            task_description: Annotated[
                str,
                "Description of what the next agent should do, including all of the relevant context.",
            ],
            # these parameters are ignored by the LLM
            state: Annotated[MessagesState, InjectedState],
        ) -> Command:
            task_description_message = {"role": "user", "content": task_description}
            agent_input = {**state, "messages": [task_description_message]}
            return Command(
                goto=[Send(agent_name, agent_input)],
                graph=Command.PARENT,
            )

        return handoff_tool

    def _init_tools(self):
        """初始化智能体集"""
        assign_to_sql_agent = self._create_handoff_tool(
            agent_name="text2sql_agent",
            description="Assign task to a text2sql agent.",
        )

        assign_to_statistic_agent = self._create_handoff_tool(
            agent_name="statistic_agent",
            description="Assign task to a statistic agent.",
        )

        return [assign_to_sql_agent, assign_to_statistic_agent]

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
        构建并返回 ReAct 智能体图
        
        每次调用都会创建一个新的智能体实例，确保状态隔离。
        """
        supervisor_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=supervisor_prompt,
            state_schema=CustomState,
            name="supervisor",
        )

        sql_agent = Text2SQLAgent().get_agent()
        statistic_agent = StatisticsAgent().get_agent()

        supervisor = (
            StateGraph(CustomState)
            # NOTE: `destinations` is only needed for visualization and doesn't affect runtime behavior
            .add_node(supervisor_agent, destinations=("text2sql_agent", "statistic_agent", END))
            .add_node(sql_agent)
            .add_node(statistic_agent)
            .add_edge(START, "supervisor")
            # always return back to the supervisor
            .add_edge("text2sql_agent", "supervisor")
            .add_edge("statistic_agent", "supervisor")
            .add_edge("supervisor", END)
            .compile()
        )
        
        return supervisor
    
    def get_agent(self):
        return self.agent

# 测试
from utils import pretty_print_messages
supervisor = SupervisorAgent().get_agent()
for chunk in supervisor.stream(
    {
        "messages": [
            {
                "role": "user",
                "content": "1 + 2",
            }
        ]
    },
    subgraphs=True,
):
    pretty_print_messages(chunk, last_message=True)

# final_message_history = chunk["supervisor"]["messages"]
# for message in final_message_history:
#     message.pretty_print()