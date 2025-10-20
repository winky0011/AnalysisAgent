from common.utils import pretty_print_messages
from agents.supervisor import SupervisorAgent

if __name__ == "__main__":
    supervisor = SupervisorAgent().get_agent()
    for chunk in supervisor.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "我想知道在数据库的data_test表中有多少订单是超期的，各个超期类别分别有多少，我需要具体数据？超期的定义是：没有实际开始/实际时间比预期时间晚",
                }
            ]
        },
        subgraphs=True,
    ):
        pretty_print_messages(chunk, last_message=True)
