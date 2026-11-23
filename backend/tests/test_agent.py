"""The agent, its model and its route, offline: Pydantic AI's test models stand in for a real one."""

import asyncio
import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import httpx
import logfire
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic_ai.exceptions import ModelHTTPError, OutputTokenLimitExceeded, UserError
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings

from my_project.agent import (
    assistant,
    model,
    routes,
)
from my_project.api.main import create_app
from my_project.auth.deps import current_user
from my_project.auth.users import User
from my_project.observability import (
    instrument_agent,
)
from my_project.settings import (
    PREFIX,
    Settings,
    get_settings,
)

#: The provider variables a test removes, so a key on the developer's machine never leaks in.
PROVIDER_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "PYDANTIC_AI_GATEWAY_API_KEY")
MODEL = "anthropic:claude-opus-5-5"


@pytest.fixture
def no_model_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """No provider key (nor a model choice) in the environment or a .env file, restored after."""
    monkeypatch.chdir(tmp_path)
    for name in (*PROVIDER_KEYS, f"{PREFIX}AI_MODEL"):
        # setenv first records the variable, so whatever the test sets (load_dotenv) is undone.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def agent_app(fake: Model | None = None, *, signed_in: bool = True) -> FastAPI:
    """The app, with `fake` in place of the model AI_MODEL names (None: the real one)."""
    app = create_app()
    if fake is not None:
        app.dependency_overrides[routes.get_model] = lambda: fake
    if signed_in:
        app.dependency_overrides[current_user] = fake_user
    return app


def fake_user() -> User:
    """A stand-in for the signed-in user: tests/test_auth.py covers signing in."""
    return User(id=1, email="a@b.example", is_admin=False)


async def ask(app: FastAPI, question: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        return await http.post("/api/agent", json={"question": question})


def call_the_tool_forever(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("current_time", {})])


def reject_the_key(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise ModelHTTPError(401, "test", body={"error": "invalid x-api-key: test-key"})


def cut_off(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise OutputTokenLimitExceeded("The answer reached max_tokens.")


async def answer_late(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    await asyncio.sleep(1)
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"answer": "late"})])


async def test_the_agent_calls_its_tool() -> None:
    result = await assistant.agent.run(
        "What time is it?", model=TestModel(), usage_limits=assistant.LIMITS
    )
    returned = [
        part.tool_name
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    assert "current_time" in returned
    assert isinstance(result.output, assistant.AgentAnswer)


async def test_each_model_response_is_capped() -> None:
    caps: list[int] = []

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        caps.append((info.model_settings or ModelSettings()).get("max_tokens") or 0)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"answer": "ok"})])

    await assistant.agent.run("Hi", model=FunctionModel(answer), usage_limits=assistant.LIMITS)
    assert 0 < caps[0] < (assistant.LIMITS.total_tokens_limit or 0)


def test_current_time_is_utc() -> None:
    assert dt.datetime.fromisoformat(assistant.current_time()).utcoffset() == dt.timedelta(0)


def test_resolve_model_without_a_key_raises(no_model_key: Path) -> None:
    with pytest.raises(UserError, match="ANTHROPIC_API_KEY"):
        model.resolve_model(Settings(ai_model=MODEL))


def test_resolve_model_reads_the_key_from_dotenv(no_model_key: Path) -> None:
    (no_model_key / ".env").write_text("ANTHROPIC_API_KEY=test-key\n", encoding="utf-8")
    assert model.resolve_model(Settings(ai_model=MODEL)).model_name == "claude-opus-5-5"


async def test_agent_answers() -> None:
    response = await ask(agent_app(TestModel()), "What time is it?")
    assert response.status_code == 200
    assert isinstance(response.json()["answer"], str)


async def test_agent_without_a_model_key_answers_503(no_model_key: Path) -> None:
    response = await ask(agent_app(), "What time is it?")
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


@pytest.mark.parametrize("question", ["", "x" * 2001])
async def test_agent_rejects_an_empty_or_overlong_question(question: str) -> None:
    response = await ask(agent_app(TestModel()), question)
    assert response.status_code == 422


async def test_agent_answers_422_when_it_hits_the_usage_limits() -> None:
    response = await ask(agent_app(FunctionModel(call_the_tool_forever)), "Loop.")
    assert response.status_code == 422


async def test_agent_answers_422_when_an_answer_is_cut_off() -> None:
    response = await ask(agent_app(FunctionModel(cut_off)), "Write a book.")
    assert response.status_code == 422


async def test_agent_answers_504_when_the_run_takes_too_long(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assistant, "TIMEOUT", 0.05)
    response = await ask(agent_app(FunctionModel(answer_late)), "Take your time.")
    assert response.status_code == 504


async def test_agent_answers_503_for_a_provider_that_is_not_installed(
    no_model_key: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(f"{PREFIX}AI_MODEL", "groq:llama-3.3-70b-versatile")
    get_settings.cache_clear()
    response = await ask(agent_app(), "Hello?")
    assert response.status_code == 503
    assert "pydantic-ai-slim[groq]" in response.json()["detail"]


async def test_agent_answers_502_when_the_provider_fails() -> None:
    response = await ask(agent_app(FunctionModel(reject_the_key)), "Hello?")
    assert response.status_code == 502
    assert "test-key" not in response.text


@pytest.mark.usefixtures("app_settings")
async def test_agent_requires_sign_in() -> None:
    app = agent_app(TestModel(), signed_in=False)
    async with LifespanManager(app):
        response = await ask(app, "Who am I?")
    assert response.status_code == 401


def test_instrument_agent_follows_the_trace_content_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(logfire, "instrument_pydantic_ai", lambda **kwargs: calls.append(kwargs))
    instrument_agent(Settings(agent_trace_content=False))
    assert calls == [{"include_content": False}]
