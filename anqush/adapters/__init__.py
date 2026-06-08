"""Anqush adapters — framework-specific integrations."""

from .openai import OpenAIAdapter, wrap_openai
from .langgraph import LangGraphAdapter, wrap_tool_node
from .mcp import MCPAdapter, create_mcp_proxy

__all__ = [
    "OpenAIAdapter",
    "wrap_openai",
    "LangGraphAdapter",
    "wrap_tool_node",
    "MCPAdapter",
    "create_mcp_proxy",
]
