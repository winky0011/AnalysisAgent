
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings
from langmem import create_manage_memory_tool, create_search_memory_tool

from dotenv import load_dotenv
import os

from customState import CustomState
from customTools import get_all_tools
from prompt import *

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
        agent = create_react_agent(
                    self.llm, 
                    tools=self.tools, 
                    prompt=system_prompt, 
                    store=self.store,   # 长期记忆
                    state_schema=CustomState,   # 短期记忆
                )
        return agent