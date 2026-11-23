"""The agent's model, from the `AI_MODEL` setting."""

from dotenv import load_dotenv
from pydantic_ai.models import Model, infer_model

from ..settings import Settings


def resolve_model(settings: Settings) -> Model:
    """The model `AI_MODEL` names, with its provider's key from the environment.

    The providers read their key (ANTHROPIC_API_KEY…) from the environment, while backend/.env is
    read by pydantic-settings only: load that file into the environment first, never over a
    variable already set. Raises `pydantic_ai.exceptions.UserError` when the key is missing or the
    model name is not one Pydantic AI knows.
    """
    load_dotenv(".env", override=False)
    return infer_model(settings.ai_model)
