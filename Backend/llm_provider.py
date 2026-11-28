import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Literal, Optional, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

CLAUDE_CODE_MODEL = os.getenv("CLAUDE_CODE_MODEL", "claude-sonnet-5-5")
CLAUDE_CODE_EFFORT = os.getenv("CLAUDE_CODE_EFFORT", "medium")
CLAUDE_CODE_TIMEOUT = float(os.getenv("CLAUDE_CODE_TIMEOUT", "180"))
USE_CLI_FOR_AGENT = os.getenv("USE_CLI_FOR_AGENT", "true").lower() == "true"


class LLMUnavailableError(RuntimeError):
    """The LLM could not answer: not installed, timed out, usage limit, or an error reply.

    `limit_reached` is True when the provider says the usage limit was hit,
    so the API can tell the user to wait instead of retrying right away.
    """

    def __init__(self, message: str, limit_reached: bool = False):
        super().__init__(message)
        self.limit_reached = limit_reached


def _looks_like_limit(text: str) -> bool:
    text = (text or "").lower()
    return "limit" in text and ("usage" in text or "rate" in text or "reached" in text)


# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------

class PlanStep(BaseModel):
    url: str
    goal: str

class PlanResponse(BaseModel):
    steps: list[PlanStep]

class RoutedPlan(BaseModel):
    """Classification and plan from one LLM call. steps is empty for GENERAL."""
    mode: Literal["PERSON", "COMPANY", "GENERAL"]
    steps: list[PlanStep] = []

class Lead(BaseModel):
    name: str
    title: str
    company: str
    email: Optional[str] = None
    source_url: str
    relevance: str
    domain: Optional[str] = None   # company's own website domain, e.g. "nvidia.com"; used for its logo

class SynthesisResponse(BaseModel):
    leads: list[Lead]
    suggestions: str = ""
    summary: str = ""


# ---------------------------------------------------------------------------
# Claude Code CLI helpers
# ---------------------------------------------------------------------------

def _claude_code_command() -> str:
    command = shutil.which("claude.exe") or shutil.which("claude.cmd") or shutil.which("claude")
    if command is None:
        raise LLMUnavailableError("Claude Code is not installed or not on PATH (the 'claude' command).")
    return command


def _claude_code(system: str, user: str, schema: type[T] | None = None) -> T | str:
    prompt = user
    if schema is not None:
        json_schema = schema.model_json_schema()
        prompt = f"{user}\n\nReply with only a JSON object matching this schema, and no other text:\n{json.dumps(json_schema)}"

    with tempfile.TemporaryDirectory() as work:
        system_file = Path(work) / "system.txt"
        system_file.write_text(system, encoding="utf-8")
        cmd = [
            _claude_code_command(), "-p",
            "--model", CLAUDE_CODE_MODEL,
            "--output-format", "json",
            "--system-prompt-file", str(system_file),
            "--tools", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if CLAUDE_CODE_EFFORT:
            cmd.extend(["--effort", CLAUDE_CODE_EFFORT])
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        try:
            result = subprocess.run(
                cmd, input=prompt, cwd=work, capture_output=True, text=True,
                encoding="utf-8", timeout=CLAUDE_CODE_TIMEOUT, env=env,
            )
        except subprocess.TimeoutExpired:
            raise LLMUnavailableError(
                f"Claude Code took longer than {CLAUDE_CODE_TIMEOUT:g}s; "
                "raise CLAUDE_CODE_TIMEOUT."
            ) from None

    if result.returncode != 0 and not result.stdout.strip():
        err = result.stderr.strip()
        raise LLMUnavailableError(f"Claude Code failed: {err}", limit_reached=_looks_like_limit(err))

    try:
        reply = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise LLMUnavailableError("Claude Code returned output that is not JSON.") from None
    if reply.get("is_error"):
        detail = str(reply.get("result") or reply.get("subtype"))
        raise LLMUnavailableError(f"Claude Code failed: {detail}", limit_reached=_looks_like_limit(detail))

    text = reply["result"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    if schema is None:
        return text
    return schema.model_validate_json(text)


async def claude_code_invoke(system: str, user: str, schema: type[T] | None = None) -> T | str:
    return await asyncio.to_thread(_claude_code, system, user, schema)


# ---------------------------------------------------------------------------
# ChatClaudeCode — LangChain BaseChatModel backed by the CLI
# ---------------------------------------------------------------------------

TOOL_CALL_INSTRUCTIONS = """When you want to use a tool, respond with ONLY a JSON object in this exact format:
{"content": "your brief reasoning", "tool_calls": [{"name": "tool_name", "args": {"arg1": "value1"}}]}

When you do NOT need a tool, respond with plain text (no JSON wrapper)."""


class ChatClaudeCode(BaseChatModel):
    model: str = CLAUDE_CODE_MODEL
    temperature: float = 0.4
    max_tokens: int = 4096

    @property
    def _llm_type(self) -> str:
        return "claude-code-cli"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        tools = kwargs.get("tools", [])
        tool_choice = kwargs.get("tool_choice")

        system_parts: list[str] = []
        conversation: list[BaseMessage] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_parts.append(
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
            else:
                conversation.append(msg)

        system_text = "\n\n".join(system_parts) if system_parts else ""

        if tools:
            tool_block = self._format_tools(tools, tool_choice)
            system_text = f"{system_text}\n\n{tool_block}" if system_text else tool_block

        user_text = self._format_conversation(conversation)

        raw = _claude_code(system_text, user_text)
        message = self._parse_response(raw, bool(tools))
        return ChatResult(generations=[ChatGeneration(message=message)])

    # ------------------------------------------------------------------
    # Tool formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tools(tools: list[dict], tool_choice: Any = None) -> str:
        lines = ["You have access to the following tools:\n"]
        for tool in tools:
            func = tool.get("function", tool)
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            lines.append(f"### {name}")
            if desc:
                lines.append(desc)
            lines.append(f"Parameters: {json.dumps(params, indent=2)}")
            lines.append("")

        lines.append(TOOL_CALL_INSTRUCTIONS)

        if isinstance(tool_choice, dict):
            forced = tool_choice.get("function", {}).get("name", "")
            if forced:
                lines.append(f"\nYou MUST call the '{forced}' tool in your response.")
        elif tool_choice in ("required", "any"):
            lines.append("\nYou MUST call at least one tool in your response.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Conversation serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _format_conversation(messages: list[BaseMessage]) -> str:
        parts: list[str] = []
        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if isinstance(msg, HumanMessage):
                parts.append(f"Human: {content}")
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    tc_text = json.dumps(
                        [{"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls]
                    )
                    parts.append(f"Assistant: {content}\nTool calls: {tc_text}")
                else:
                    parts.append(f"Assistant: {content}")
            elif isinstance(msg, ToolMessage):
                tool_name = getattr(msg, "name", "tool")
                parts.append(f"Tool result ({tool_name}): {content}")
            else:
                parts.append(f"{msg.type}: {content}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str, has_tools: bool) -> AIMessage:
        if has_tools:
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and "tool_calls" in data:
                    tool_calls = []
                    for tc in data["tool_calls"]:
                        tool_calls.append({
                            "name": tc["name"],
                            "args": tc.get("args", {}),
                            "id": f"call_{uuid.uuid4().hex[:12]}",
                        })
                    return AIMessage(
                        content=data.get("content", ""),
                        tool_calls=tool_calls,
                    )
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return AIMessage(content=raw)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_agent_llm(temperature: float = 0.4) -> BaseChatModel:
    if USE_CLI_FOR_AGENT:
        return ChatClaudeCode(temperature=temperature)
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=CLAUDE_CODE_MODEL,
        temperature=temperature,
        max_tokens=4096,
    )
