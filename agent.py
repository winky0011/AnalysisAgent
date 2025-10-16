
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langmem import create_manage_memory_tool, create_search_memory_tool

from dotenv import load_dotenv
import os

from customState import CustomState
from customTools import get_all_tools

load_dotenv()

class AnalysisWorkflow:
    def __init__(self):
        self.tools = get_all_tools()
        self.llm = init_chat_model(
            model=os.getenv("OPENAI_LLM_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.5,
        )

        # 长期记忆存储
        embeddings = init_embeddings(
            model=os.getenv("EMBEDDING_MODEL"),
            provider=os.getenv("EMBEDDING_PROVIDER"),
            model_kwargs={
                    "device": "cpu",
                    "local_files_only": True
                }
        )
        self.store = InMemoryStore(
            index={
                'embed': embeddings,
                'dims': int(os.getenv("EMBEDDING_DIM")),
            }
        )  # 长期记忆
    
    def graph_builder(self):
        system_prompt = """你是专业的数据分析助手，负责处理MySQL数据库查询、时间差计算和数据统计任务。
请根据用户需求，判断是否需要调用以下工具：
1. query_data_test：执行SQL查询data_test表，返回CSV结果；
2. filter_data_by_date_range：按日期范围过滤t1/t2阶段数据，无需手动写SQL；
3. get_last_csv_results：获取上一次查询的CSV结果，避免重复查库；
4. calculate_single_time_difference：计算两个时间点的差值；
5. batch_calculate_time_differences：批量计算时间列表差值并统计；
6. calculate_math：基础数学运算（如加减乘除）。

决策规则：
- 若需要数据库数据或时间计算或基础数学运算，必须调用对应工具；
- 若已调用过工具且有历史CSV结果，优先调用get_last_csv_results；
- 工具返回结果后，需检查status是否为"success"，若为"error"需告知用户错误原因；
- 无需调用工具时（如用户问"如何使用工具"），直接回答。
    """
        agent = create_react_agent(
                    self.llm, 
                    tools=self.tools, 
                    prompt=system_prompt, 
                    store=self.store,   # 长期记忆
                    state_schema=CustomState,   # 短期记忆
                )
        return agent