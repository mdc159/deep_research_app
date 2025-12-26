"""
Research Agent - Main agent creation and configuration.

This module creates a deep research agent with custom tools, middleware,
and subagents for conducting evidence-backed research.
"""

import logging
from typing import Any
from uuid import UUID

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from schemas.config import ModelConfig, RunConfig
from research_agent.middleware import (
    CitationMiddleware,
    CritiqueMiddleware,
    IngestionMiddleware,
    RetrievalMiddleware,
    create_citation_middleware,
    create_critique_middleware,
    create_ingestion_middleware,
    create_retrieval_middleware,
)
from research_agent.prompts import (
    get_critic_prompt,
    get_drafter_prompt,
    get_full_orchestrator_prompt,
    get_researcher_prompt,
)
from research_agent.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Research agent with middleware and subagent management.

    This class wraps the deep agent with:
    - Tool management for ingestion, retrieval, citation
    - Middleware for tracking state across the pipeline
    - Subagent configuration for researcher, drafter, critic
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        run_config: RunConfig | None = None,
    ):
        """
        Initialize the research agent.

        Args:
            model_config: Configuration for LLM models
            run_config: Configuration for the research run
        """
        self.model_config = model_config or ModelConfig()
        self.run_config = run_config

        # Initialize middleware
        self.ingestion_middleware = create_ingestion_middleware(
            run_config.ingestion if run_config else None
        )
        self.retrieval_middleware = create_retrieval_middleware(
            run_config.retrieval if run_config else None
        )
        self.citation_middleware = create_citation_middleware(run_config)
        self.critique_middleware = create_critique_middleware()

        # Initialize models
        self._planner_model: BaseChatModel | None = None
        self._drafter_model: BaseChatModel | None = None
        self._critic_model: BaseChatModel | None = None

        # Agent instance (created lazily)
        self._agent = None
        self._run_id: UUID | None = None

    def _get_model(self, model_spec: str) -> BaseChatModel:
        """
        Get a chat model from a model specification.

        Args:
            model_spec: Model specification (e.g., "anthropic:claude-sonnet-4-5-20250929")

        Returns:
            Initialized chat model
        """
        return init_chat_model(model=model_spec, temperature=0.0)

    @property
    def planner_model(self) -> BaseChatModel:
        """Get or create the planner/orchestrator model."""
        if self._planner_model is None:
            self._planner_model = self._get_model(self.model_config.planner)
        return self._planner_model

    @property
    def drafter_model(self) -> BaseChatModel:
        """Get or create the drafter model."""
        if self._drafter_model is None:
            self._drafter_model = self._get_model(self.model_config.drafter)
        return self._drafter_model

    @property
    def critic_model(self) -> BaseChatModel:
        """Get or create the critic model."""
        if self._critic_model is None:
            self._critic_model = self._get_model(self.model_config.critic)
        return self._critic_model

    def get_tools(self) -> list[BaseTool]:
        """
        Get all tools for the agent.

        Returns:
            List of LangChain tools
        """
        # Combine tools from all middleware
        tools = []
        tools.extend(self.ingestion_middleware.get_tools())
        tools.extend(self.retrieval_middleware.get_tools())
        tools.extend(self.citation_middleware.get_tools())

        # Add think tool for internal reasoning
        tools.append(create_think_tool())

        return tools

    def get_subagents(self) -> list[dict[str, Any]]:
        """
        Get subagent configurations.

        Returns:
            List of subagent configuration dicts
        """
        # Researcher subagent
        researcher = {
            "name": "researcher",
            "description": (
                "Research subagent for gathering evidence on a specific topic. "
                "Delegate when you need to search and synthesize evidence. "
                "Give one focused research topic at a time."
            ),
            "system_prompt": get_researcher_prompt(),
            "tools": self.retrieval_middleware.get_tools() + [create_think_tool()],
        }

        # Drafter subagent
        drafter = {
            "name": "drafter",
            "description": (
                "Drafting subagent for writing research sections. "
                "Delegate when you need to write a section with proper citations. "
                "Provide the section topic and relevant evidence."
            ),
            "system_prompt": get_drafter_prompt(),
            "tools": self.retrieval_middleware.get_tools() + [create_think_tool()],
        }

        # Critic subagent
        critic = {
            "name": "critic",
            "description": (
                "Critique subagent for reviewing document quality. "
                "Delegate when you need to review a draft for issues. "
                "Provide the content to review."
            ),
            "system_prompt": get_critic_prompt(),
            "tools": self.retrieval_middleware.get_tools() + [create_think_tool()],
        }

        return [researcher, drafter, critic]

    def set_run(self, run_id: UUID) -> None:
        """
        Set the current run ID for all middleware.

        Args:
            run_id: UUID of the current run
        """
        self._run_id = run_id
        self.ingestion_middleware.set_run(run_id)
        self.retrieval_middleware.set_run(run_id)
        self.citation_middleware.set_run(run_id)
        self.critique_middleware.set_run(run_id)

    def reset(self) -> None:
        """Reset all middleware for a new run."""
        self.ingestion_middleware.reset()
        self.retrieval_middleware.reset()
        self.citation_middleware.reset()
        self.critique_middleware.reset()
        self._run_id = None

    def get_stats(self) -> dict[str, Any]:
        """
        Get combined statistics from all middleware.

        Returns:
            Dictionary with all stats
        """
        return {
            "ingestion": self.ingestion_middleware.get_stats(),
            "retrieval": self.retrieval_middleware.get_stats(),
            "citation": self.citation_middleware.get_stats(),
            "critique": self.critique_middleware.get_stats(),
        }

    def create_agent(self):
        """
        Create the deep agent with all configuration.

        Returns:
            Configured deep agent
        """
        try:
            from deepagents import create_deep_agent

            # Get the full orchestrator prompt
            system_prompt = get_full_orchestrator_prompt(
                max_concurrent=3,
                max_iterations=3,
            )

            # Create the agent
            self._agent = create_deep_agent(
                model=self.planner_model,
                tools=self.get_tools(),
                system_prompt=system_prompt,
                subagents=self.get_subagents(),
            )

            logger.info("Research agent created successfully")
            return self._agent

        except ImportError as e:
            logger.error(f"Failed to import deepagents: {e}")
            raise RuntimeError(
                "deepagents package not installed. "
                "Install with: uv add deepagents"
            ) from e

    @property
    def agent(self):
        """Get or create the agent."""
        if self._agent is None:
            self.create_agent()
        return self._agent

    async def run(
        self,
        research_request: str,
        run_id: UUID,
        config: dict | None = None,
    ) -> dict[str, Any]:
        """
        Run a research task.

        Args:
            research_request: The research question/request
            run_id: UUID for this run
            config: Optional runtime configuration

        Returns:
            Research results with document and metadata
        """
        self.set_run(run_id)

        try:
            # Invoke the agent
            result = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": research_request}]},
                config=config,
            )

            # Get final stats
            stats = self.get_stats()

            return {
                "result": result,
                "stats": stats,
                "run_id": str(run_id),
            }

        except Exception as e:
            logger.exception(f"Research run failed: {e}")
            raise

        finally:
            # Don't reset - let caller decide when to reset
            pass

    async def stream(
        self,
        research_request: str,
        run_id: UUID,
        config: dict | None = None,
    ):
        """
        Stream a research task with real-time updates.

        Args:
            research_request: The research question/request
            run_id: UUID for this run
            config: Optional runtime configuration

        Yields:
            Event updates from the agent
        """
        self.set_run(run_id)

        try:
            async for event in self.agent.astream_events(
                {"messages": [{"role": "user", "content": research_request}]},
                config=config,
                version="v2",
            ):
                yield event

        except Exception as e:
            logger.exception(f"Research stream failed: {e}")
            raise


def create_think_tool() -> BaseTool:
    """
    Create the think tool for internal reasoning.

    Returns:
        Think tool
    """
    from langchain_core.tools import tool

    @tool
    def think(thought: str) -> str:
        """
        Internal reasoning tool for complex analysis and planning.

        Use this to work through complex problems, evaluate evidence,
        plan next steps, or make decisions. The output is for internal
        use and helps structure your thinking.

        Args:
            thought: Your reasoning or analysis

        Returns:
            Acknowledgment (the thinking itself is the value)
        """
        # This is a no-op tool - the value is in the agent's reasoning
        return "Thought recorded."

    return think


def create_research_agent(
    model_config: ModelConfig | None = None,
    run_config: RunConfig | None = None,
) -> ResearchAgent:
    """
    Factory function to create a research agent.

    Args:
        model_config: Configuration for LLM models
        run_config: Configuration for the research run

    Returns:
        Configured ResearchAgent instance
    """
    return ResearchAgent(model_config, run_config)


# Convenience function to get a pre-configured agent
def get_default_agent() -> ResearchAgent:
    """
    Get a research agent with default configuration.

    Returns:
        ResearchAgent with default settings
    """
    return create_research_agent()


# For direct use as a LangGraph graph (e.g., in deployments)
def create_graph(model_config: ModelConfig | None = None):
    """
    Create the agent graph for LangGraph deployment.

    Args:
        model_config: Optional model configuration

    Returns:
        LangGraph compiled graph
    """
    agent = create_research_agent(model_config)
    return agent.agent
