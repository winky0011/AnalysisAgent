from langchain_core.messages import HumanMessage

from agent import AnalysisWorkflow

def main():
    analysisWorkflow = AnalysisWorkflow()
    agent = analysisWorkflow.graph_builder()

    # Invoke
    config = {
        "configurable": {
            "user_id": "user_123",
            "user_name": "Joy",
        },
        "recursion_limit": 25
    }
    messages = [HumanMessage(content="我想知道在data_test表中有多少订单是超期的？超期的定义是：没有实际开始/实际时间比预期时间晚")]
    # messages = [HumanMessage(content="你好！")]
    messages = agent.invoke(
        {
            "messages": messages
        },
        config=config
    )
    for m in messages["messages"]:
        m.pretty_print()


if __name__ == "__main__":
    main()
