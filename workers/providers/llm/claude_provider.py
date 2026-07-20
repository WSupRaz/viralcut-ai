from typing import Any

import anthropic

from edit_plan_schema.schema import EditPlan
from workers.config import settings
from workers.providers.llm.base import EditPlanProvider

CLAUDE_MODEL = "claude-sonnet-5"
MAX_TOKENS = 8192
TOOL_NAME = "submit_edit_plan"


def _build_tool_schema() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Submit the finished edit plan for this video project.",
        "input_schema": EditPlan.model_json_schema(),
    }


class ClaudeEditPlanProvider(EditPlanProvider):
    """Claude is the brain only -- it never touches video frames, it only
    produces this structured plan (see ARCHITECTURE section of the product
    spec). Forces a tool call rather than asking for free-text JSON, so a
    malformed response is a schema-validation failure, not a JSON parse
    error somewhere in a wall of prose."""

    name = "claude-sonnet-5"

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        tool = _build_tool_schema()
        response = self._client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=[tool],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": user_prompt}],
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == TOOL_NAME:
                return block.input
        raise ValueError("Claude response did not include a submit_edit_plan tool call")
