# 工作节点 Agent 的实现
需要实现工作节点：
- Text2SQL Agent
- 数据操作 Agent
- 分析 Agent

## Text2SQL Agent

目的：根据用户输入的自然语言，生成对应的 SQL 查询语句，并将对应sql查询结果以csv样式保存。

实现参考：[sql-agent](https://langchain-ai.github.io/langgraph/tutorials/sql/sql-agent/)

测试代码：
```python
text2sql_agent = Text2SQLAgent()
agent = text2sql_agent.get_agent()
question = "你数据库存储了什么数据，能解答我什么问题？？？"

# 流式输出 Agent 执行过程（包含工具调用、查询结果、最终回答）
for step in agent.stream(
    {"messages": [{"role": "user", "content": question}]},
    stream_mode="values",  # 按步骤输出关键信息
):
    # 打印每一步的最后一条消息（人类问题、AI 工具调用、工具返回结果、最终回答）
    step["messages"][-1].pretty_print()
```