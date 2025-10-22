from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing_extensions import TypedDict, Annotated
import operator, os
from typing import List, Optional
from tqdm import tqdm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from common.prompt import MAP_SYSTEM_PROMPT, REDUCE_SYSTEM_PROMPT
from common import get_neo4j_db_manager
from common.memory_state import MapReduceState

load_dotenv()

class MapReduceSearchAgent:
    """基于LangGraph的Map-Reduce检索Agent"""
    
    def __init__(self, response_type: str = "多个段落"):
        self.llm = self._init_llm()
        self.response_type = response_type
        self.db_manager = get_neo4j_db_manager()
        self.graph = self.db_manager.get_graph()
        self.workflow = self._build_workflow()

    def _init_llm(self):
        """初始化大语言模型"""
        return init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.3,  # 降低随机性，确保报告严谨性
        )

    # ------------------------------
    # 节点函数：工作流中的各个处理步骤
    # ------------------------------
    def fetch_communities(self, state: MapReduceState) -> dict:
        """获取指定层级的社区数据"""
        communities = self.graph.query(
            """
            MATCH (c:__Community__)
            WHERE c.level = $level
            RETURN {communityId:c.id, full_content:c.full_content} AS output
            """,
            params={"level": state["level"]},
        )
        return {"communities": communities}

    def map_process(self, state: MapReduceState) -> dict:
        """Map阶段：处理单个社区数据"""
        current_community = state["communities"][0] if state["communities"] else None
        if not current_community:
            return {"intermediate_results": ["未获取到有效社区数据"]}

        # 构建Map提示
        map_prompt = ChatPromptTemplate.from_messages([
            ("system", MAP_SYSTEM_PROMPT),
            ("human", "---数据表格---\n{context_data}\n用户的问题是：{question}"),
        ])

        map_chain = map_prompt | self.llm | StrOutputParser()
        result = map_chain.invoke({
            "question": state["query"],
            "context_data": current_community["output"]  # 正确读取社区数据
        })
        return {"intermediate_results": [result]}

    def reduce_process(self, state: MapReduceState) -> dict:
        """Reduce阶段：整合所有中间结果"""
        # 构建Reduce阶段提示模板
        reduce_prompt = ChatPromptTemplate.from_messages([
            ("system", REDUCE_SYSTEM_PROMPT),
            ("human", """
                ---分析报告--- 
                {report_data}

                用户的问题是：
                {question}
                
                请按照{response_type}的形式返回最终答案。
                """),
        ])

        # 执行Reduce处理
        reduce_chain = reduce_prompt | self.llm | StrOutputParser()
        final_answer = reduce_chain.invoke({
            "report_data": "\n\n".join(state["intermediate_results"]),
            "question": state["query"],
            "response_type": self.response_type
        })
        return {"final_answer": final_answer}

    # ------------------------------
    # 条件边函数：控制工作流走向
    # ------------------------------
    def route_to_map(self, state: MapReduceState) -> List[Send]:
        """根据社区列表生成Map任务分发"""
        return [
            Send("map_process", {"communities": [community], "query": state["query"], "intermediate_results": []})
            for community in state["communities"]
        ]

    # ------------------------------
    # 工作流构建
    # ------------------------------
    def _build_workflow(self) -> StateGraph:
        """构建Map-Reduce工作流图"""
        builder = StateGraph(MapReduceState)

        # 添加节点
        builder.add_node("fetch_communities", self.fetch_communities)  # 获取社区数据
        builder.add_node("map_process", self.map_process)  # Map处理节点
        builder.add_node("reduce_process", self.reduce_process)  # Reduce处理节点

        # 定义边关系
        builder.add_edge(START, "fetch_communities")
        
        # 从fetch_communities分发任务到多个map_process（并行）
        builder.add_conditional_edges(
            "fetch_communities",
            self.route_to_map,
            ["map_process"]  # 目标节点
        )
        
        # 所有map_process完成后进入reduce_process
        builder.add_edge("map_process", "reduce_process")
        builder.add_edge("reduce_process", END)

        return builder.compile(name="map_reduce_workflow")

    # ------------------------------
    # 外部接口
    # ------------------------------
    def search(self, query: str, level: int) -> str:
        """执行Map-Reduce检索"""
        result = self.workflow.invoke(MapReduceState(
            query=query,
            level=level,
            communities=[],
            intermediate_results=[],
            final_answer=""
        ))
        return result['final_answer']

    def get_agent(self):
        return self.workflow

    def close(self):
        """关闭资源连接"""
        self.db_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()