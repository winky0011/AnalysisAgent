from common.utils import pretty_print_messages
from agents.supervisor import SupervisorAgent

if __name__ == "__main__":
    supervisor = SupervisorAgent().get_agent()

    for chunk in supervisor.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "你数据库里都具备什么知识？能回答我什么问题？",
                }
            ]
        },
        subgraphs=True,
    ):
        pretty_print_messages(chunk, last_message=True)
