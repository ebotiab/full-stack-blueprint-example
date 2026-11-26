"""A bounded trace allowance, reserved persistently before entering this context.

Unadmitted requests, health probes, auth attempts and metrics emit no demo telemetry.
Each admitted chat exports at most 48 application spans; each budgeted startup one.
Gateway telemetry is separate and must also be capped in its project settings.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from opentelemetry import context
from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult

_allowance: ContextVar[list[int] | None] = ContextVar("demo_trace_allowance", default=None)


@contextmanager
def trace_allowance(spans: int = 48) -> Iterator[None]:
    # A new root: never correlate a visitor-supplied trace ID or baggage.
    parent = context.attach(context.Context())
    token = _allowance.set([spans])
    try:
        yield
    finally:
        _allowance.reset(token)
        context.detach(parent)


class DemoSampler(Sampler):
    def should_sample(
        self,
        parent_context: Any,
        trace_id: int,
        name: str,
        kind: Any = None,
        attributes: Any = None,
        links: Any = None,
        trace_state: Any = None,
    ) -> SamplingResult:
        remaining = _allowance.get()
        if remaining is not None and remaining[0] > 0:
            remaining[0] -= 1
            return SamplingResult(Decision.RECORD_AND_SAMPLE, attributes, trace_state)
        return SamplingResult(Decision.DROP)

    def get_description(self) -> str:
        return "Persistently admitted demo traces only"
