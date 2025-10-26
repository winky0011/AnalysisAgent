# AnalysisAgent

## 1. 简介
> 项目启动时间：2025年10月14日
> 
> 启动目的：快速掌握Agent开发，串联已有能力（SFT、PE）

AnalysisAgent是一个基于LangGraph的智能分析代理，用于分析用户的自然语言查询，并根据查询内容从数据库中提取相关数据进行分析。


目前已实现：
- 采用 [`Multi-agent supervisor`](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/#2-create-supervisor-with-langgraph-supervisor) 架构：
  - [SQL Agent](https://langchain-ai.github.io/langgraph/tutorials/sql/sql-agent/)、Statistics Agent 以及 Analysis Agent 的初步实现，对应功能见 [readme](agents/readme.md) ，emmm，目前需求过于简单，sql agent即可实现，不需要调用Statistics Agent。
  - Supervisor Agent的实现，基于官网提供的教程：[multi_agent](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/#research-agent)
  - agent之间的转换是基于handoff机制，信息的传递基于send原语
- Neo4j 知识图谱的构建，向量检索的实现


待实现：
- <u>外部 MCP 工具的接入（初步设想是引入[Echart工具](https://github.com/antvis/mcp-server-chart)）+ 报告生成</u>
- 记忆的实现，借助外挂数据库实现持久化存储，以及[mem路由](https://arxiv.org/abs/2508.04903)
- Text2SQL 直接生成查询语句，目前有两种待实现的思路：
  - ~~Text2SQL Agent~~
  - 基于SFT训练的Text2SQL模型
- 报告生成节点模型的训练（生成更有建设性、更规范的报告）


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
- https://github.com/anthropics/skills
- https://github.com/infiniflow/ragflow/tree/main
- https://docs.ragas.io/en/latest/getstarted/index.html


## 2. 使用方法

> 如果使用 uv 管理环境，请在每条 python 执行命令前添加 `uv run` 前缀。

### 2.1 环境准备

#### 2.1.1 配置

创建环境，安装对应的依赖
```
conda create -n analysisagent python=3.12
conda activate analysisagent
pip install -r requirements.txt
```

下载embedding模型到本地cache目录下
```
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); model.save('cache/all-MiniLM-L6-v2')"
```

新建.env文件，设置对应变量，参考 `.env.example` 文件。
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


#### 2.1.2 数据库准备

> 注意：在执行任何数据库脚本之前，请确保目标数据库服务正在运行。

生成 MySQL 测试数据，具体表格设计可以查看[readme.md](database/mysql_setup/readme.md)。在测试数据生成结束后，**十分建议**将mysql数据库配置中的账号设置为只读模式，避免 Agent 执行危险操作。
```
python database\mysql_setup\gen_data.py
```

生成 Neo4j 测试数据，将需要解析的文档存在 `database/neo4j_setup/files` 文件下，修改 Neo4j 的设置文件 `database/settings.py`，主要修改以下参数，其他参数设置按需修改：
- theme
- entity_types
- relationship_types

执行以下命令，生成对应知识图谱（**此过程可能会消耗大量token！！！**）：
```
python -m database.neo4j_setup.build_database --build         # 完整构建知识图谱
python -m database.neo4j_setup.build_database --incremental   # 增量插入
```

已插入的文件会记录在`cache\file_registry.json`文件中，用于增量插入时判断文件是否已存在。

#### 2.1.3 启动 MCP 服务端以及配置

MCP 服务端的配置，这里使用到的是 [antvis/mcp-server-chart](https://github.com/antvis/mcp-server-chart)，可以根据 [readme.md](https://github.com/antvis/mcp-server-chart/blob/main/README.md) 进行配置。
启动成功后，修改 `custom_tools\chart_tools.py` 中的 `SERVER_CONFIGS` 变量：
```
SERVER_CONFIGS = {
    "mcp-server-chart": {  
        "command": "xxx", 
        "args": [
            "xxxx"
        ],
        "transport": xxx,
    }
}
```


### 2.2 运行agent

测试agent
```
python main.py
```