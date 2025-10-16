import os
from typing import Any, List
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

from custom_tools import get_mysql_tools
from memory_state import CustomState

load_dotenv()

class Text2SQLAgent:
    """
    负责根据用户输入的自然语言，生成对应的 SQL 查询语句，并将对应sql查询结果以csv样式保存。
    """

    def __init__(self) -> None:
        self.db = self._init_db()
        self.llm = self._init_llm()
        self.tools = self._init_tools()
        self.agent = self._init_agent()

    def _init_db(self):
        """初始化数据库连接"""
        mysql_host = os.getenv('MYSQL_HOST', 'localhost')
        mysql_user = os.getenv('MYSQL_USER')
        mysql_password = os.getenv('MYSQL_PASSWORD')
        mysql_database = os.getenv('MYSQL_DATABASE')
        mysql_port = os.getenv('MYSQL_PORT', '3306')  # 默认 3306，用字符串避免类型问题

        engine_url = f"mysql+mysqlconnector://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}"

        return SQLDatabase.from_uri(engine_url)

    def _init_tools(self):
        """初始化工具集"""
        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        tools = toolkit.get_tools()   # langgraph中提供的工具
        tools.extend(get_mysql_tools())  # 自定义工具
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
        """
        构建并返回 ReAct 智能体图（Agent Graph）。
        
        每次调用都会创建一个新的智能体实例，确保状态隔离。
        """
        system_prompt = """
你是一个用于与 MySQL 数据库交互的 Agent，需严格遵循以下规则：
1. 给定用户问题后，先获取数据库表列表，再查询相关表的结构，最后生成 SQL。
2. 生成 **MySQL 语法** 的查询语句。
3. 如果后续涉及对查询结果的操作，请以csv样式将查询结果暂存在内存中，否则返回 {top_k} 条查询结果，优先按相关字段排序展示关键信息。
4. 仅查询所需列，禁止使用 SELECT * 获取所有列；禁止执行 DML 语句（INSERT/UPDATE/DELETE/DROP 等）。
5. 执行查询前必须用 sql_db_query_checker 工具检查语法正确性，若报错需重新修改查询。
""".format(
    dialect=self.db.dialect,  # 自动填充数据库类型
    top_k=5  # 默认返回前 5 条结果
)
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
            state_schema=CustomState,
        )
    
    def get_agent(self):
        return self.agent