# AnalysisAgent
## 简介
AnalysisAgent是一个基于LangGraph的智能分析代理，用于分析用户的自然语言查询，并根据查询内容从数据库中提取相关数据进行分析。

目前已实现：
- 从数据库中提取数据进行分析（目前sql写死了）
- 长期记忆的初步实现，存储用户的查询历史和分析结果到内存中

待实现：
- 报告生成节点模型的训练（生成更有建设性、更规范的报告）
- Text2SQL直接生成查询语句
- 增加外挂知识库，用于辅助情况的判断以及报告的生成（类似于：如何提高管理效率、优化管理措施等信息）
- 长期记忆的优化，借助外挂数据库实现持久化存储

涉及的技术栈：LangGraph、LangMem


## 使用方法
创建环境
```
pip install -r requirements.txt
```

下载embedding模型到本地cache目录下，并且在.env文件下配置对应信息
```
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); model.save('cache/all-MiniLM-L6-v2')"
```

新建.env文件，设置对应变量
```
# MySQL数据库配置
MYSQL_HOST=xxxx
MYSQL_PORT=xxxx
MYSQL_USER=xxxx
MYSQL_PASSWORD=xxxx
MYSQL_DATABASE=xxxx

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

生成测试数据，会在指定数据库内创建一个名为`data_test`的表
```
python create_data.py
```

测试agent
```
python main.py
```