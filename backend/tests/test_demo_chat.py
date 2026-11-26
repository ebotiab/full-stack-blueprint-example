"""Real PostgreSQL/session boundaries; deterministic Pydantic AI model doubles."""

import asyncio
from collections.abc import AsyncIterator

import asyncpg
import httpx
import httpx2
import pytest
from asgi_lifespan import LifespanManager
from fastapi import HTTPException
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import Decision
from pydantic_ai.exceptions import ModelHTTPError, UserError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from my_project import demo_chat, demo_gateway
from my_project.api.main import create_app
from my_project.demo import EMAIL, PASSWORD
from my_project.demo_gateway import GatewayClient
from my_project.demo_telemetry import DemoSampler, trace_allowance
from my_project.settings import PREFIX, get_settings

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    if len(messages) == 1:
        return ModelResponse(parts=[ToolCallPart("read_demo_messages", {"limit": 4})])
    prompts = [str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart)]
    return ModelResponse(parts=[TextPart("Answer: " + "; ".join(prompts))])


@pytest.fixture
async def http(
    app_settings: None, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv(f"{PREFIX}DEMO_ENABLED", "true")
    monkeypatch.setenv(f"{PREFIX}DEMO_CHAT_ENABLED", "true")
    monkeypatch.setenv(f"{PREFIX}DEMO_GATEWAY_ROUTE", "test-free")
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_API_KEY", "test-only")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[demo_chat.get_chat_model] = lambda: FunctionModel(answer)
    async with (
        LifespanManager(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as client,
    ):
        yield client


async def login(http: httpx.AsyncClient) -> None:
    response = await http.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers=SAME_ORIGIN
    )
    assert response.status_code == 200


async def ask(http: httpx.AsyncClient, message: str = "summarize") -> httpx.Response:
    return await http.post("/api/demo-chat", json={"message": message}, headers=SAME_ORIGIN)


async def test_session_auth_csrf_and_input_boundaries(http: httpx.AsyncClient) -> None:
    assert (await ask(http)).status_code == 401
    assert (await http.get("/api/demo-chat")).status_code == 401
    await login(http)
    assert (await http.post("/api/demo-chat", json={"message": "hi"})).status_code == 403
    for message in ["", "  ", "x" * 601]:
        assert (await ask(http, message)).status_code == 422
    forged = await http.post(
        "/api/demo-chat", json={"message": "hi", "session_id": "somebody-else"}, headers=SAME_ORIGIN
    )
    assert forged.status_code == 422
    assert (await http.post("/api/agent", json={}, headers=SAME_ORIGIN)).status_code == 403


async def test_tool_continuity_and_isolation(
    http: httpx.AsyncClient, db_conn: asyncpg.Connection
) -> None:
    await login(http)
    first_cookies = http.cookies
    first = await ask(http, "first-private-question")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["execution"]["tool_used"]
    assert first.json()["execution"]["rows_read"] == 4
    second = await ask(http, "follow-up")
    assert "first-private-question" in second.json()["answer"]
    history = await db_conn.fetchval("SELECT history FROM demo_chat_sessions")
    assert history is not None
    assert len(history) == 2
    assert "tool-return" not in str(history)
    http.cookies = httpx.Cookies()
    await login(http)
    other = await ask(http, "other-session")
    assert "first-private-question" not in other.text
    assert "follow-up" not in other.text
    assert other.json()["remaining"] == 4
    http.cookies = first_cookies
    assert (await http.get("/api/demo-chat")).json()["remaining"] == 3
    await http.post("/api/auth/logout", headers=SAME_ORIGIN)
    assert await db_conn.fetchval("SELECT count(*) FROM demo_chat_sessions") == 1


async def test_expired_context_is_not_used_or_quota_reset(
    http: httpx.AsyncClient, db_conn: asyncpg.Connection
) -> None:
    await login(http)
    await ask(http, "expired-question")
    await db_conn.execute("UPDATE demo_chat_sessions SET expires_at = now() - interval '1 second'")
    response = await ask(http, "new-question")
    assert "expired-question" not in response.text
    assert response.json()["remaining"] == 3


async def test_session_cap_survives_model_replacement(http: httpx.AsyncClient) -> None:
    await login(http)
    for i in range(5):
        assert (await ask(http, f"question {i}")).status_code == 200
    assert (await ask(http)).status_code == 429
    assert not (await http.get("/api/demo-chat")).json()["available"]


@pytest.mark.parametrize(("window", "cap"), [("YYYY-MM", 100), ("YYYY-MM-DD", 20)])
async def test_global_cap_survives_new_session(
    http: httpx.AsyncClient, db_conn: asyncpg.Connection, window: str, cap: int
) -> None:
    await login(http)
    await db_conn.execute(
        "INSERT INTO demo_chat_budget (period, turns) VALUES (to_char(now() AT TIME ZONE 'UTC', $1), $2) "
        "ON CONFLICT (period) DO UPDATE SET turns = $2",
        window,
        cap,
    )
    assert (await ask(http)).status_code == 429
    http.cookies.clear()
    await login(http)
    assert (await ask(http)).status_code == 429
    assert await db_conn.fetchval("SELECT sum(attempts) FROM demo_chat_sessions") in (None, 0)


async def test_global_lock_refuses_overlap_without_spending(
    http: httpx.AsyncClient, db_conn: asyncpg.Connection
) -> None:
    await login(http)
    await db_conn.execute("SELECT pg_advisory_lock($1)", demo_chat.LOCK_ID)
    try:
        assert (await ask(http)).status_code == 429
        assert await db_conn.fetchval("SELECT count(*) FROM demo_chat_sessions") == 0
    finally:
        await db_conn.execute("SELECT pg_advisory_unlock($1)", demo_chat.LOCK_ID)
    assert (await ask(http)).status_code == 200


async def test_failure_is_sanitized_and_reservation_is_never_refunded(
    http: httpx.AsyncClient, db_conn: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    await login(http)

    async def fail(*args, **kwargs):
        raise ModelHTTPError(429, "test", body="SECRET-provider-payload")

    monkeypatch.setattr(demo_chat.agent, "run", fail)
    response = await ask(http)
    assert response.status_code == 502
    assert "SECRET" not in response.text
    assert await db_conn.fetchval("SELECT attempts FROM demo_chat_sessions") == 1
    assert await db_conn.fetchval("SELECT sum(turns) FROM demo_chat_budget") == 2
    # Provider exhaustion persists across new requests; it does not spend another reservation.
    assert (await ask(http)).status_code == 503
    assert await db_conn.fetchval("SELECT attempts FROM demo_chat_sessions") == 1
    assert not (await http.get("/api/demo-chat")).json()["available"]
    assert await db_conn.fetchval("SELECT pg_try_advisory_lock($1)", demo_chat.LOCK_ID)
    await db_conn.execute("SELECT pg_advisory_unlock($1)", demo_chat.LOCK_ID)


async def test_timeout_and_tool_loop_stop(
    http: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await login(http)

    async def slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(1)
        return ModelResponse(parts=[TextPart("late")])

    monkeypatch.setattr(demo_chat, "TIMEOUT", 0.01)
    with demo_chat.agent.override(model=FunctionModel(slow)):
        assert (await ask(http)).status_code == 504

    def loop(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart("read_demo_messages", {})])

    monkeypatch.setattr(demo_chat, "TIMEOUT", 30)
    with demo_chat.agent.override(model=FunctionModel(loop)):
        assert (await ask(http)).status_code == 422


async def test_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(f"{PREFIX}DEMO_ENABLED", "true")
    monkeypatch.setenv(f"{PREFIX}DEMO_CHAT_ENABLED", "false")
    get_settings.cache_clear()
    assert "not activated" in (demo_chat.configuration_error() or "")
    monkeypatch.setenv(f"{PREFIX}DEMO_CHAT_ENABLED", "true")
    monkeypatch.delenv("PYDANTIC_AI_GATEWAY_API_KEY", raising=False)
    get_settings.cache_clear()
    assert "missing" in (demo_chat.configuration_error() or "")
    async with GatewayClient() as client:
        with pytest.raises(HTTPException) as exc:
            demo_chat.get_chat_model(client)
    assert exc.value.status_code == 503
    get_settings.cache_clear()


async def test_gateway_model_pins_us_route_and_disables_transport_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{PREFIX}DEMO_ENABLED", "true")
    monkeypatch.setenv(f"{PREFIX}DEMO_CHAT_ENABLED", "true")
    monkeypatch.setenv(f"{PREFIX}DEMO_GATEWAY_ROUTE", "example-free")
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_API_KEY", "test-only")
    # An unrelated base URL must never redirect this demo's credential.
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_BASE_URL", "https://unrelated.invalid")
    get_settings.cache_clear()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(demo_gateway, "_TRACER", provider.get_tracer("demo-test"))
    received: list[httpx2.Request] = []

    def upstream(request: httpx2.Request) -> httpx2.Response:
        received.append(request)
        return httpx2.Response(200, json={"object": "list", "data": []})

    client = GatewayClient(transport=httpx2.MockTransport(upstream))
    try:
        model = demo_chat.get_chat_model(client)
        async with model:
            assert model.model_name == "openai/gpt-oss-20b"
            assert model.settings is not None
            assert model.settings.get("extra_headers") == {"Cache-Control": "no-store"}
            assert model.provider is not None
            assert (
                str(model.provider.base_url)
                == "https://gateway-us.pydantic.dev/proxy/example-free/"
            )
            assert model.provider.client.max_retries == 0
            assert model.provider.client.timeout == 20.0
            await model.provider.client.models.list(
                extra_headers={"Cookie": "synthetic=example", "baggage": "test=example"}
            )
            headers = received[0].headers
            assert headers["traceparent"].endswith("-00")
            assert "cookie" not in headers
            assert "baggage" not in headers
            [http_span] = exporter.get_finished_spans()
            assert http_span.context is not None
            assert headers["traceparent"] == (
                f"00-{http_span.context.trace_id:032x}-{http_span.context.span_id:016x}-00"
            )
            assert http_span.attributes == {
                "gateway.route": "example-free",
                "server.address": "gateway-us.pydantic.dev",
                "http.request.method": "GET",
                "http.response.status_code": 200,
            }

        def invalid(*args, **kwargs):
            raise UserError("sensitive-config-detail")

        monkeypatch.setattr(demo_chat, "gateway_provider", invalid)
        with pytest.raises(HTTPException) as exc:
            demo_chat.get_chat_model(client)
        assert exc.value.status_code == 503
        assert "sensitive-config-detail" not in exc.value.detail
    finally:
        await client.aclose()
        get_settings.cache_clear()


def test_telemetry_requires_admission_and_has_a_hard_span_cap() -> None:
    sampler = DemoSampler()

    def sample() -> Decision:
        return sampler.should_sample(None, 1, "test").decision

    assert sample() == Decision.DROP
    with trace_allowance(2):
        assert sample() == Decision.RECORD_AND_SAMPLE
        assert sample() == Decision.RECORD_AND_SAMPLE
        assert sample() == Decision.DROP
    assert sample() == Decision.DROP
