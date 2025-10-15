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
python test.py
```