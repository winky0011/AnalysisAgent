# AnalysisAgent

## 简介
> 项目启动时间：2025年10月14日
> 
> 启动目的：快速掌握Agent开发，串联已有能力（SFT、PE）

AnalysisAgent是一个基于LangGraph的智能分析代理，用于分析用户的自然语言查询，并根据查询内容从数据库中提取相关数据进行分析。


目前已实现：
- ~~从数据库中提取数据进行分析（目前只支持mysql数据库，且sql写死了）；~~
- ~~长期记忆的初步实现，存储用户的查询历史和分析结果到内存中；~~
- 采用 [`Multi-agent supervisor`](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/#2-create-supervisor-with-langgraph-supervisor) 架构：
  - [SQLAgenty](https://langchain-ai.github.io/langgraph/tutorials/sql/sql-agent/) 以及 StatisticsAgent 的初步实现，emmms，目前需求过于简单，sql agent即可实现，不需要调用StatisticsAgent。
  - Supervisor Agent的实现，基于官网提供的教程：[multi_agent](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/#research-agent)
  - agent之间的转化是基于handoff机制，信息的传递基于send原语


待实现：
- <u>外部 MCP 工具的接入（初步设想是引入echart工具）+ 报告生成</u>
- 增加外挂知识库，用于辅助情况的判断以及报告的生成（类似于：如何提高管理效率、优化管理措施等信息）
- Text2SQL 直接生成查询语句，目前有两种待实现的思路：
  - ~~Text2SQL Agent~~
  - 基于SFT训练的Text2SQL模型
- 报告生成节点模型的训练（生成更有建设性、更规范的报告）
- 记忆的实现，借助外挂数据库实现持久化存储，以及[mem路由](https://arxiv.org/abs/2508.04903)


涉及的技术栈/框架：LangGraph、LangMem、LangSmith、text2sql、SFT、neo4j、RAG、MCP


参考资料：
- https://langchain-ai.github.io/langgraph/
- https://langchain-ai.github.io/langmem/
- https://github.com/DMIRLAB-Group/Track-SQL
- https://arxiv.org/abs/2503.16252
- https://arxiv.org/abs/2402.03578
- https://github.com/1517005260/graph-rag-agent
- https://github.com/antvis/mcp-server-chart
- https://github.com/24mlight/a-share-mcp-is-just-i-need
- https://github.com/a2aproject/a2a-python
- https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills


## 使用方法
创建环境，安装对应的依赖
```
conda create -n analysisagent python=3.12
conda activate analysisagent
pip install -r requirements.txt
```

下载embedding模型到本地cache目录下，并且在.env文件下配置对应信息
```
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); model.save('cache/all-MiniLM-L6-v2')"
```

新建.env文件，设置对应变量
```
# MySQL数据库配置，建议用户权限不要太高！！！
MYSQL_HOST=xxxx
MYSQL_PORT=xxxx
MYSQL_USER=xxxx
MYSQL_PASSWORD=xxxx
MYSQL_DATABASE=xxxx

# Neo4j数据库配置
NEO4J_URI='bolt://xxxxx:xxx'
NEO4J_USERNAME='xxxx'
NEO4J_PASSWORD='xxxx'

# LLM模型配置
OPENAI_BASE_URL=xxxx
OPENAI_LLM_MODEL=xxxx
OPENAI_API_KEY=xxxx

# 嵌入模型配置
EMBEDDING_MODEL='cache/all-MiniLM-L6-v2'
EMBEDDING_PROVIDER='huggingface'
EMBEDDING_DIM=384

# LangSmith配置，用于监控agent运行
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=xxxx
LANGSMITH_API_KEY=xxxx
LANGSMITH_PROJECT=xxxx
```

生成测试数据，会在指定数据库内创建一个名为`data_test`的表。在测试数据生成结束后，**十分建议**将mysql数据库配置中的账号设置为只读模式，避免 Agent 执行危险操作。
```
python database\mysql_setup\data_test.py
```

测试agent
```
python main.py
```