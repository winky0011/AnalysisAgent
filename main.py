# main.py
import asyncio
from agent import *

async def main():
    config = {"configurable": {"langgraph_user_id": "test_user_001"}}
    
    # 第一轮：执行分析
    response1 = await analysis_chat.ainvoke(
        [{"role": "user", "content": "我想知道在data_test表中有多少订单是超期的？超期的定义是：没有实际开始/实际时间比预期时间晚"}],
        config=config
    )
    print("✅ Round 1:", response1["messages"][-1].content)

    await asyncio.sleep(30)  # 等待记忆写入完成

    # 第二轮：查询历史
    response2 = await analysis_chat.ainvoke(
        [{"role": "user", "content": "上一个问题的结果是什么？？"}],
        config=config
    )
    print("\n✅ Round 2 Response (should recall):")
    print(response2["messages"][-1].content)

    # 手动查看记忆
    # memories = await analysis_workflow.memory_manager.asearch(
    #     query="我想知道在data_test表中有多少订单是超期的？超期的定义是：没有实际开始/实际时间比预期时间晚", config=config
    # )
    # print("\n🔍 Stored Memories:")
    # for m in memories:
    #     print(f"- Query: {m['value'].query}\n  Answer: {m['value'].final_answer}\n")

if __name__ == "__main__":
    asyncio.run(main())
