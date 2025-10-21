from langchain_core.tools import tool
import time
from pathlib import Path

# 固定存储目录（建议用绝对路径）
LOCAL_REPORT_DIR = Path("./cache/local_report_cache")
# 确保目录存在，不存在则创建
LOCAL_REPORT_DIR.mkdir(exist_ok=True, parents=True)

@tool
def save_report(report: str) -> str:
    """
    保存分析报告到文件
    
    参数:
        report: 待保存的报告内容
    
    返回:
        保存成功的提示信息
    """
    timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
    with open(LOCAL_REPORT_DIR / f"analysis_report_{timestamp}.md", "w", encoding="utf-8") as f:
        f.write(report)
    return f"报告已成功保存到 {LOCAL_REPORT_DIR / f'analysis_report_{timestamp}.md'}"

def get_report_tools():
    return [
        save_report
    ]