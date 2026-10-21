"""Bridge between shared config and LangGraph.

Reads the agent config JSON written by config-api, builds a LangGraph agent,
and exports ``graph`` for ``langgraph dev``.

Falls back to a minimal stub agent when no config exists yet (first startup
before the user builds) or when the build fails.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

from .configuration import Configuration, load
from .mcp_errors import configure_mcp_tool_error_handling, recover_mcp_exceptions
from .middleware import (
    build_current_date_middleware,
    build_session_header_middleware,
    build_system_prompt_addition_middleware,
    get_system_prompt_additions,
)

_CONFIG = os.environ.get("AGENT_CONFIG_PATH", "./agent_config.yaml")


async def _build():
    """Build a LangGraph agent from a resolved Configuration."""
    # initialize config
    config: Configuration = load(_CONFIG)

    # initialize model — the proxy picks per turn when configured, otherwise the first model serves everything.
    # Sampling params come from models[0] either way so behavior matches across both paths.
    selected = config.models[0]
    model = ChatOpenAI(
        model=config.proxy.model if config.proxy else selected.name,
        base_url=config.proxy.url if config.proxy else selected.url,
        api_key="dummy" if config.proxy else (selected.api_key or "dummy"),
        temperature=selected.temperature,
        max_tokens=selected.max_tokens,
        use_responses_api=False,
        include_response_headers=bool(config.proxy),
        **({"top_p": selected.top_p} if selected.top_p is not None else {}),
    )

    # initialize tools
    tools: list[Any] = []
    if config.mcp_servers:
        # "tools" isn't a connection param the MCP client understands
        mcp_servers = {
            name: server.model_dump(exclude_none=True, exclude={"tools"}) for name, server in config.mcp_servers.items()
        }
        # Transient tool sessions clean up while the lifespan lease preserves browser state.
        if playwright := mcp_servers.get("playwright"):
            playwright["terminate_on_close"] = True
        client = MultiServerMCPClient(
            mcp_servers,
            tool_interceptors=[recover_mcp_exceptions],
        )
        for name, server in config.mcp_servers.items():
            available_tools = await client.get_tools(server_name=name)
            if server.tools:
                # filter tools to only include the ones in the server config
                available_tools = [t for t in available_tools if t.name in server.tools]
            tools.extend(configure_mcp_tool_error_handling(available_tools))

    # initialize middleware
    middleware = [build_current_date_middleware()]
    addition = get_system_prompt_additions(config)
    if addition:
        middleware.append(build_system_prompt_addition_middleware(addition))
    if config.proxy:
        middleware.append(build_session_header_middleware(config.proxy.session_header))

    # initialize backend
    backend = LocalShellBackend(root_dir=os.getcwd(), virtual_mode=True, inherit_env=True)

    # initialize agent
    return create_deep_agent(
        model=model,
        tools=tools or None,
        system_prompt=config.system_prompt,
        middleware=tuple(middleware),
        backend=backend,
    )


graph = asyncio.run(_build())
