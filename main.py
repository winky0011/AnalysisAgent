from common.utils import pretty_print_messages
from agents.supervisor import SupervisorAgent

if __name__ == "__main__":
    supervisor = SupervisorAgent().get_agent()

    for chunk in supervisor.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "你都具备什么和‘奖学金评选’相关的知识？我申请奖学金需要满足什么条件？",
                }
            ]
        },
        subgraphs=True,
    ):
        pretty_print_messages(chunk, last_message=True)
