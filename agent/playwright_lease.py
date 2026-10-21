"""Keep Playwright's shared browser alive for one LangGraph process."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent

from .configuration import load

_LOGGER = logging.getLogger(__name__)
_CONFIG = os.environ.get("AGENT_CONFIG_PATH", "./agent_config.yaml")


def _error_text(result: object) -> str:
    content = getattr(result, "content", [])
    return "\n".join(item.text for item in content if isinstance(item, TextContent))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Hold one MCP session so short-lived tool sessions can cleanly terminate."""
    config = load(_CONFIG)
    playwright = config.mcp_servers.get("playwright")
    if playwright is None:
        yield
        return

    if playwright.transport not in {"streamable_http", "streamable-http", "http"} or not playwright.url:
        raise RuntimeError("Playwright browser lease requires a streamable HTTP URL")

    _LOGGER.info("Acquiring Playwright browser lease at %s", playwright.url)
    async with streamablehttp_client(
        playwright.url,
        headers=playwright.headers,
        terminate_on_close=True,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Playwright creates its browser backend lazily on the first tool call.
            result = await session.call_tool("browser_tabs", {"action": "list"})
            if result.isError:
                message = _error_text(result) or "Playwright rejected the browser lease"
                raise RuntimeError(message)

            _LOGGER.info("Playwright browser lease acquired")
            try:
                yield
            finally:
                _LOGGER.info("Releasing Playwright browser lease")


app = FastAPI(lifespan=lifespan)
