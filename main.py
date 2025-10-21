from common.utils import pretty_print_messages
from agents.supervisor import SupervisorAgent
from agents.analysis_agent import AnalysisAgent

if __name__ == "__main__":
    supervisor = SupervisorAgent().get_agent()
    for chunk in supervisor.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "我想知道申请奖学金需要提供什么材料，结果帮我保存下来（markdown格式）",
                }
            ]
        },
        subgraphs=True,
    ):
        pretty_print_messages(chunk, last_message=True)
