"""The agent: its instructions, its tools and the limits of one run.

Grow it here: more tools (`@agent.tool_plain`, or `@agent.tool` with a `RunContext` to reach
dependencies), a richer output type, other agents next to it. The model is not set here: the caller
passes the one the `AI_MODEL` setting names (agent/model.py), so the API starts without a provider
key, and tests pass Pydantic AI's TestModel or FunctionModel instead.
"""

import datetime as dt

from pydantic import BaseModel
from pydantic_ai import Agent, UsageLimits
from pydantic_ai.settings import ModelSettings

INSTRUCTIONS = (
    "You are the assistant of this application. Answer briefly and plainly. "
    "Use your tools when they help, and say so when you do not know."
)

#: One model response at most (thinking included): without it a provider may allow 100,000+.
SETTINGS = ModelSettings(max_tokens=8_000)
#: What one run may spend, so a question cannot keep the model and its tools looping.
LIMITS = UsageLimits(request_limit=5, total_tokens_limit=40_000)
#: How long one run may take, in seconds.
TIMEOUT = 120.0


class AgentAnswer(BaseModel):
    """What the agent returns, validated by Pydantic."""

    answer: str


agent = Agent(
    None,
    name="assistant",
    instructions=INSTRUCTIONS,
    output_type=AgentAnswer,
    model_settings=SETTINGS,
)


@agent.tool_plain
def current_time() -> str:
    """The current date and time in UTC, in ISO 8601."""
    return dt.datetime.now(dt.UTC).isoformat()
