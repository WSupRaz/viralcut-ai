import json
from typing import Any

from openai import OpenAI

from edit_plan_schema.schema import EditPlan
from workers.config import settings
from workers.providers.llm.base import EditPlanProvider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
TOOL_NAME = "submit_edit_plan"


class OpenRouterEditPlanProvider(EditPlanProvider):
    """Fallback for the edit-plan step, used only if the primary (Claude)
    call fails and OPENROUTER_API_KEY is configured. OpenRouter exposes an
    OpenAI-compatible chat-completions API across many backend models
    (including free-tier ones), which also happens to cover the original
    spec's "Gemini fallback" line item through the same integration point
    rather than a separate direct-to-Google client."""

    name = f"openrouter:{OPENROUTER_MODEL}"

    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openrouter_api_key, base_url=OPENROUTER_BASE_URL)

    def generate(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": TOOL_NAME,
                        "description": "Submit the finished edit plan for this video project.",
                        "parameters": EditPlan.model_json_schema(),
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        )

        message = response.choices[0].message
        if not message.tool_calls:
            raise ValueError(
                f"OpenRouter response did not include a {TOOL_NAME} tool call: {message.content!r}"
            )
        return json.loads(message.tool_calls[0].function.arguments)
