from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import InjectedState, create_react_agent
from langgraph.types import Command, Send

from dotenv import load_dotenv
import json
import os
import re
from typing import Annotated, Any, Dict, List, Optional

from agents import AnalysisAgent, StatisticsAgent, Text2SQLAgent
from common.memory_backend import init_memory_backend
from common.memory_state import CustomState
from common.prompt import supervisor_prompt
from custom_tools.memory_tools import create_supervisor_memory_tools

load_dotenv()

class SupervisorAgent:
    """
    协调多个智能体的智能体。
    """
    def __init__(self) -> None:
        self.memory_namespace_prefix = "supervisor_memories"
        self.memory_backend = init_memory_backend()
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

        assign_to_analysis_agent = self._create_handoff_tool(
            agent_name="analysis_agent",
            description="Assign task to a analysis agent.",
        )

        memory_tools = create_supervisor_memory_tools(
            default_namespace_prefix=self.memory_namespace_prefix,
            backend=self.memory_backend,
        )

        return [assign_to_sql_agent, assign_to_statistic_agent, assign_to_analysis_agent, *memory_tools]

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.5,
        )

    def _get_state_value(self, state: CustomState, key: str, default: Optional[Any] = None) -> Optional[Any]:
        if isinstance(state, dict):
            return state.get(key, default)
        return getattr(state, key, default)

    def _normalize_message_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts)
        return ""

    def _extract_last_user_message_text(self, state: CustomState) -> str:
        messages = self._get_state_value(state, "messages", [])
        if not messages:
            return ""
        for message in reversed(messages):
            if isinstance(message, BaseMessage) and getattr(message, "type", "") == "human":
                return self._normalize_message_content(message.content)
            if isinstance(message, dict) and message.get("role") == "user":
                return self._normalize_message_content(message.get("content"))
        return ""

    def _extract_last_ai_message_info(self, state: CustomState) -> Optional[Dict[str, Any]]:
        messages = self._get_state_value(state, "messages", [])
        if not messages:
            return None
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return {
                    "name": getattr(message, "name", None),
                    "content": self._normalize_message_content(message.content),
                }
            if isinstance(message, BaseMessage) and getattr(message, "type", "") == "ai":
                return {
                    "name": getattr(message, "name", None),
                    "content": self._normalize_message_content(message.content),
                }
            if isinstance(message, dict) and message.get("role") == "assistant":
                return {
                    "name": message.get("name"),
                    "content": self._normalize_message_content(message.get("content")),
                }
        return None

    def _namespace_from_state(self, state: CustomState) -> str:
        user_id = (
            self._get_state_value(state, "user_id")
            or self._get_state_value(state, "langgraph_user_id")
            or "anonymous"
        )
        return f"{self.memory_namespace_prefix}/{user_id}"

    def _parse_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        cleaned = text.strip()
        if not cleaned:
            return None
        # Handle fenced code blocks like ```json {...}```
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned, count=1, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                return None
        return None

    def _decide_memory_write(
        self,
        user_message: str,
        retrieved_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        context_lines = "\n".join(
            f"- {item.get('content', '')}" for item in retrieved_items[:5]
        ) or "（无相关记忆）"
        prompt = (
            "你是一个长期记忆管理助手，需要判断用户最新的输入是否包含值得长期保存的偏好、"
            "背景信息或其他对未来对话有帮助的事实。\n"
            "请以 JSON 格式回答，包含字段：\n"
            '  - "should_write": 布尔值，是否应写入记忆。\n'
            '  - "memory_summary": 如果需要写入，请给出一到两句中文描述，概括核心要点；否则为空字符串。\n'
            '  - "reason": 简要说明判断依据。\n'
            "只保存会在未来多次使用、对用户画像重要或能指导后续行为的信息；临时性问题或一次性的请求不要写入。"
        )

        llm_messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content=(
                    "用户最新消息：\n"
                    f"{user_message.strip()}\n\n"
                    "已存在的相关记忆：\n"
                    f"{context_lines}\n"
                )
            ),
        ]

        try:
            response = self.llm.invoke(llm_messages)
        except Exception:
            return {"should_write": False, "memory_summary": "", "reason": "llm_failure"}

        decision_text = self._normalize_message_content(getattr(response, "content", ""))
        parsed = self._parse_json_from_text(decision_text)
        if not parsed:
            return {"should_write": False, "memory_summary": "", "reason": "parse_failure"}

        should_write = bool(parsed.get("should_write", False))
        memory_summary = str(parsed.get("memory_summary", "") or "").strip()
        reason = str(parsed.get("reason", "") or "").strip()
        return {
            "should_write": should_write,
            "memory_summary": memory_summary,
            "reason": reason,
        }

    def _memory_router_node(self, state: CustomState) -> Dict[str, Any]:
        user_message = self._extract_last_user_message_text(state)
        if not user_message:
            return {}

        last_routed = self._get_state_value(state, "last_memory_routed_message")
        if last_routed == user_message:
            return {}

        namespace = self._namespace_from_state(state)

        updates: Dict[str, Any] = {"last_memory_routed_message": user_message}
        injected_messages: List[SystemMessage] = []

        results = self.memory_backend.search(namespace, user_message, top_k=5, min_score=0.3)
        if results:
            lines = "\n".join(f"- {item['content']}" for item in results)
            injected_messages.append(
                SystemMessage(content=f"相关长期记忆（命名空间：{namespace}）：\n{lines}")
            )
        else:
            injected_messages.append(
                SystemMessage(content="未在长期记忆中检索到相关内容，如有需要可以调用 memory_search。")
            )

        injected_messages.append(
            SystemMessage(
                content=(
                    "请评估当前对话是否包含值得写入长期记忆的偏好或事实。"
                    "如需保存，请在最终回答前调用 memory_write 工具写入简洁要点。"
                )
            )
        )

        decision = self._decide_memory_write(user_message, results or [])

        if decision.get("should_write"):
            summary = decision.get("memory_summary", "")
            reason = decision.get("reason", "")
            updates["pending_memory_write"] = {
                "namespace": namespace,
                "query": user_message,
                "summary": summary,
                "reason": reason,
            }
            injected_messages.append(
                SystemMessage(
                    content=(
                        "记忆助手建议写入长期记忆。\n"
                        f"摘要：{summary or '（助手未提供摘要，请自行概括）'}\n"
                        f"理由：{reason or '（无）'}\n"
                        "请在最终答案前使用 memory_write 工具保存关键要点，或在回答中说明无需写入。"
                    )
                )
            )

        if injected_messages:
            updates["messages"] = injected_messages

        return updates

    def _memory_persist_node(self, state: CustomState) -> Dict[str, Any]:
        pending = self._get_state_value(state, "pending_memory_write")
        if not pending:
            return {}

        ai_info = self._extract_last_ai_message_info(state)
        if not ai_info:
            return {}

        name = ai_info.get("name")
        if name and name != "supervisor":
            # 仅在主管智能体输出最终答案时写入记忆
            return {}

        content = (ai_info.get("content") or "").strip()
        if not content:
            return {}

        namespace = pending.get("namespace") or self._namespace_from_state(state)
        query = pending.get("query", "")
        summary = (pending.get("summary") or "").strip()
        reason = (pending.get("reason") or "").strip()

        sections: List[str] = []
        if summary:
            sections.append(f"【记忆要点】\n{summary}")
        if reason:
            sections.append(f"【判断依据】\n{reason}")
        sections.append(f"【用户问题】\n{query}")
        sections.append(f"【最终回答】\n{content}")
        memory_entry = "\n\n".join(sections)

        try:
            self.memory_backend.write(namespace, memory_entry, metadata={"source": "supervisor"})
        except Exception:
            # 写入失败不应阻断流程，记录失败后清理状态以避免无限重试
            return {"pending_memory_write": None}

        return {"pending_memory_write": None}

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
        analysis_agent = AnalysisAgent().get_agent()

        supervisor = (
            StateGraph(CustomState)
            # NOTE: `destinations` is only needed for visualization and doesn't affect runtime behavior
            .add_node("memory_router", self._memory_router_node)
            .add_node(supervisor_agent, destinations=("text2sql_agent", "statistic_agent", "analysis_agent", END))
            .add_node(sql_agent)
            .add_node(statistic_agent)
            .add_node(analysis_agent)
            .add_node("memory_persist", self._memory_persist_node)
            .add_edge(START, "memory_router")
            .add_edge("memory_router", "supervisor")
            # always return back to the supervisor
            .add_edge("text2sql_agent", "memory_router")
            .add_edge("statistic_agent", "memory_router")
            .add_edge("analysis_agent", "memory_router")
            .add_edge("supervisor", "memory_persist")
            .add_edge("memory_persist", END)
            .compile()
        )
        
        return supervisor
    
    def get_agent(self):
        return self.agent

# 测试
if __name__ == "__main__":
    from common.utils import pretty_print_messages
    supervisor = SupervisorAgent().get_agent()
    for chunk in supervisor.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "我想知道在数据库的data_test表中有多少订单是超期的，各个超期类别分别有多少，我需要具体数据？超期的定义是：没有实际开始/实际时间比预期时间晚",
                }
            ]
        },
        subgraphs=True,
    ):
        pretty_print_messages(chunk, last_message=True)