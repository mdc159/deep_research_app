"""
Research agent implementation using the deepagents framework.

This package contains the main agent configuration, prompts, tools,
and middleware for the research pipeline.
"""

from research_agent.agent import (
    ResearchAgent,
    create_graph,
    create_research_agent,
    create_think_tool,
    get_default_agent,
)

__version__ = "0.1.0"

__all__ = [
    "ResearchAgent",
    "create_research_agent",
    "create_graph",
    "create_think_tool",
    "get_default_agent",
]
