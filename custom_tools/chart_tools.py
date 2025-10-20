# 本代码参考于：https://github.com/24mlight/a-share-mcp-is-just-i-need
# mcp项目链接：https://github.com/antvis/mcp-server-chart
# 从mcp server中获取tools

from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
import json

SERVER_CONFIGS = {
  "mcpServers": {
    "mcp-server-chart": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@antv/mcp-server-chart"]
    }
  }
}

_mcp_client_instance = None
_mcp_tools = None


def print_tool_details(tools):
    """打印工具的详细信息，用于调试"""
    print(f"工具详细信息:")
    for i, tool in enumerate(tools, 1):
        print(f"  {i}. 工具名称: {tool.name}")
        print(f"     描述: {tool.description}")

        # 打印其他可能的属性
        for attr in ['input_schema', 'parameters', 'schema']:
            if hasattr(tool, attr):
                attr_value = getattr(tool, attr)
                if attr_value:
                    print(f"     {attr}: {attr_value}")

        print(f"     工具类型: {type(tool)}")
        # print(f"     所有属性: {dir(tool)}")
        print("     " + "-" * 50)


async def get_mcp_tools():
    """
    使用定义的服务器配置初始化MultiServerMCPClient，
    并从a-share-mcp-v2服务器获取可用工具。

    返回:
        list: 从MCP服务器加载的LangChain兼容工具列表。
              如果初始化或工具加载失败，则返回空列表。
    """
    global _mcp_client_instance, _mcp_tools

    if _mcp_tools is not None:
        print(f"Returning cached MCP tools.")
        return _mcp_tools

    print(
        f"Initializing MultiServerMCPClient with config: {SERVER_CONFIGS}")
    try:
        _mcp_client_instance = MultiServerMCPClient(SERVER_CONFIGS)

        print(
            f"Fetching tools from MCP server 'a_share_mcp_v2'...")
        # The get_tools() method is asynchronous.
        loaded_tools = await _mcp_client_instance.get_tools()

        if not loaded_tools:
            print(
                f"No tools loaded from MCP server 'a_share_mcp_v2'. Check server logs and configuration.")
            _mcp_tools = []  # Cache empty list on failure to load
            return []

        _mcp_tools = loaded_tools
        print(
            f"Successfully loaded {len(_mcp_tools)} tools from 'a_share_mcp_v2'.")

        # # 打印工具名称列表
        # tool_names = [tool.name for tool in _mcp_tools]
        # print(f"工具名称列表: {tool_names}")

        # 打印详细的工具信息
        # print_tool_details(_mcp_tools)

        return _mcp_tools

    except Exception as e:
        print(f"Failed to initialize MCP client or load tools: {e}", exc_info=True)
        _mcp_tools = []  # Cache empty list on failure
        return []


async def close_mcp_client_sessions():
    """
    关闭MultiServerMCPClient管理的任何开放会话。
    如果必要，应在应用程序关闭时调用此函数。
    """
    global _mcp_client_instance
    if _mcp_client_instance:
        print(f"Closing MCP client sessions...")
        try:
            print(
                f"MCP client sessions (if any were persistently open) assumed closed or managed by library.")
            _mcp_client_instance = None   # 允许重新初始化
            global _mcp_tools
            _mcp_tools = None
        except Exception as e:
            print(f"Error during MCP client session cleanup: {e}", exc_info=True)
    else:
        print("MCP client was not initialized, no sessions to close.")


# 测试此模块的示例（可选，用于直接执行）
async def _main_test_mcp_client():
    print("--- Testing MCP Client Tool Loading ---")
    tools = await get_mcp_tools()
    if tools:
        print(f"Successfully loaded {len(tools)} tools:")
        for tool in tools:
            print(
                f"- Name: {tool.name}")

        # 测试一个简单的工具调用（如果有合适的工具）
        if tools:
            print("--- Testing Tool Call ---")
            # 尝试调用第一个工具（需要根据实际工具调整参数）
            first_tool = tools[0]
            print(f"尝试调用工具: {first_tool.name}")

            # 这里需要根据实际的工具参数schema来构造测试参数
            # 暂时跳过实际调用，只是展示结构
            print("工具调用测试跳过（需要实际参数）")
    else:
        print("Failed to load tools or no tools found.")

    # 测试关闭（如果适用）
    await close_mcp_client_sessions()
    print("--- MCP Client Test Complete ---")

if __name__ == '__main__':
    # 这允许直接运行测试，例如：python -m src.tools.mcp_client
    # 确保您的环境已设置（例如，'uv'命令可用）。
    # E:\github\a_share_mcp的a_share_mcp服务器应该准备好运行。

    asyncio.run(_main_test_mcp_client())
