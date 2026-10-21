from __future__ import annotations

import os
import re
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, model_validator


class Model(BaseModel):
    name: str = Field(description="The name of the model")
    url: str = Field(description="The URL of the model")
    api_key: None | str = Field(None, description="The API key to use for the model")
    temperature: float = Field(0.5, ge=0.0, le=1.0, description="The temperature to use for the model")
    top_p: float | None = Field(None, ge=0.0, le=1.0, description="The top p to use for the model")
    max_tokens: int = Field(None, ge=0.0, description="The maximum number of tokens to generate")


class Proxy(BaseModel):
    """Routing proxy the agent dials instead of a provider directly.

    When set, the agent sends every call to ``url`` asking for ``model`` (a route id),
    and the proxy picks which of the configured models serves each turn.
    """

    url: str = Field(description="OpenAI-compatible base URL of the proxy")
    model: str = Field(description="Route id the proxy exposes as a model name")
    session_header: str = Field(
        "x-switchyard-session-id",
        description="Header carrying the conversation id, so the proxy's escalation hold survives across calls",
    )


class MCPServer(BaseModel):
    """Definition of a single MCP server to connect to."""

    command: str | None = Field(None, description="The command to run the MCP server (required for stdio)")
    args: list[str] | None = Field(None, description="Arguments for the command")
    transport: str = Field("stdio", description="Transport type (e.g. 'stdio', 'streamable_http')")
    url: str | None = Field(None, description="URL for HTTP transport servers (e.g. streamable_http)")
    env: dict[str, str] | None = Field(
        None,
        description="Environment variables passed to the MCP subprocess",
    )
    headers: dict[str, str] | None = Field(
        None,
        description="HTTP headers (e.g. Authorization) for HTTP transport servers",
    )
    tools: list[str] | None = Field(
        None,
        description="Allowlist of tool names to expose from this server (None = all tools)",
    )

    @model_validator(mode="after")
    def _require_command_or_url(self) -> "MCPServer":
        if not self.command and not self.url:
            raise ValueError("MCPServer requires either 'command' (stdio) or 'url' (HTTP)")
        if self.url and not self.url.startswith("$") and not (
            self.url.startswith("http://") or self.url.startswith("https://")
        ):
            raise ValueError("MCPServer 'url' must start with 'http://' or 'https://'")
        return self


class Configuration(BaseModel):
    models: Annotated[
        list[Model],
        Field(min_length=1, description="The models available to the agent; the first one is used for inference"),
    ]

    proxy: Proxy | None = Field(
        None,
        description="Routing proxy to dial instead of models[0]. When unset, models[0] serves every call.",
    )

    system_prompt: str = Field(
        "You are a helpful assistant",
        description="The system prompt for the agent",
    )

    mcp_servers: dict[str, MCPServer] = Field(
        default_factory=dict,
        description="Named MCP servers the agent can use for tools",
    )

    tool_prompt_hints: dict[str, str] = Field(
        default_factory=dict,
        description="Per-tool hint text appended to the last user message before each model call",
    )


_ENV_REF_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _resolve(value: str) -> str:
    """Replace $VAR_NAME patterns with values from os.environ. Unset vars resolve to ''."""
    return _ENV_REF_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)


def _resolve_env_vars(config: Configuration) -> Configuration:
    """Return a copy of config with all $VAR_NAME refs substituted from os.environ."""
    resolved_models = [m.model_copy(update={"api_key": _resolve(m.api_key or "")}) for m in config.models]
    resolved_servers: dict[str, MCPServer] = {}
    for name, server in config.mcp_servers.items():
        resolved_servers[name] = MCPServer(
            command=server.command,
            args=[_resolve(a) for a in server.args] if server.args else None,
            transport=server.transport,
            url=_resolve(server.url) if server.url else None,
            env={k: _resolve(v) for k, v in server.env.items()} if server.env else None,
            headers={k: _resolve(v) for k, v in server.headers.items()} if server.headers else None,
            tools=server.tools,
        )
    resolved_hints = {k: _resolve(v) for k, v in config.tool_prompt_hints.items()}
    return config.model_copy(
        update={"models": resolved_models, "mcp_servers": resolved_servers, "tool_prompt_hints": resolved_hints}
    )


def load(path: str) -> Configuration:
    """Load a YAML config file, resolve $VAR_NAME env refs, and return a validated Configuration."""
    with open(path) as f:
        data = yaml.safe_load(f.read())

    return _resolve_env_vars(Configuration.model_validate(data))
