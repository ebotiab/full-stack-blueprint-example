"""Trace the demo's real Gateway HTTP requests without exporting upstream headers."""

from collections.abc import AsyncIterator
from typing import Any

import httpx2
from opentelemetry import trace
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator

_TRACER = trace.get_tracer("my-project.demo-gateway")
_IDS = RandomIdGenerator()


class GatewayClient(httpx2.AsyncClient):
    async def send(self, request: httpx2.Request, **kwargs: Any) -> httpx2.Response:
        # Only send telemetry fields we select. HTTP exceptions can contain response bodies.
        with _TRACER.start_as_current_span(
            "Logfire AI Gateway request",
            kind=trace.SpanKind.CLIENT,
            attributes={
                "gateway.route": request.url.path.split("/")[2],
                "server.address": request.url.host,
                "http.request.method": request.method,
            },
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            response = await super().send(request, **kwargs)
            span.set_attribute("http.response.status_code", response.status_code)
            return response


async def suppress_gateway_header_capture(request: httpx2.Request) -> None:
    # Runs after Pydantic AI injects its propagation headers. The managed Gateway honors
    # the W3C sampling bit. Its native spans would otherwise store upstream Set-Cookie.
    ctx = trace.get_current_span().get_span_context()
    trace_id = ctx.trace_id if ctx.is_valid else _IDS.generate_trace_id()
    span_id = ctx.span_id if ctx.is_valid else _IDS.generate_span_id()
    request.headers["traceparent"] = f"00-{trace_id:032x}-{span_id:016x}-00"
    for name in ("baggage", "tracestate", "cookie"):
        request.headers.pop(name, None)


async def gateway_client() -> AsyncIterator[GatewayClient]:
    async with GatewayClient(follow_redirects=False) as client:
        yield client
