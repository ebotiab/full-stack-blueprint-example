"""POST /api/agent: one question for the agent, its answer back."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pydantic_ai.exceptions import (
    ModelAPIError,
    OutputTokenLimitExceeded,
    RunTimedOut,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
)
from pydantic_ai.models import Model

from ..auth.deps import CurrentUser
from ..settings import get_settings
from . import assistant
from .model import resolve_model

router = APIRouter(tags=["agent"])


class AgentQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def get_model() -> Model:
    """The model AI_MODEL names; 503 while it cannot be created.

    That is: no key, a name Pydantic AI does not know, or a provider whose package is not
    installed (only Anthropic and OpenAI are: add `pydantic-ai-slim[<provider>]` for others).
    """
    try:
        return resolve_model(get_settings())
    except (UserError, ImportError) as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"The agent's model is not configured: {error}"
        ) from None


ModelDep = Annotated[Model, Depends(get_model)]


@router.post("/agent")
async def ask(question: AgentQuestion, user: CurrentUser, model: ModelDep) -> assistant.AgentAnswer:
    """The agent's answer to one question from a signed-in user, within the limits of one run."""
    try:
        result = await assistant.agent.run(
            question.question,
            model=model,
            usage_limits=assistant.LIMITS,
            timeout=assistant.TIMEOUT,
        )
    except UsageLimitExceeded, OutputTokenLimitExceeded:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The question needs more model work than one request allows.",
        ) from None
    except RunTimedOut:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, "The agent took too long to answer."
        ) from None
    except (ModelAPIError, UnexpectedModelBehavior) as error:
        # The provider's own message can quote the request or the key: only its kind goes out.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"The model provider failed ({type(error).__name__})."
        ) from None
    return result.output
