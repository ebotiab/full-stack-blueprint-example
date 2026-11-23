"""An LLM agent the API calls, built with Pydantic AI.

- `assistant.py`: the agent, its tools and the limits of one run. Grow it there.
- `model.py`: the model named by the `AI_MODEL` setting, with its provider's key.
- `routes.py`: `POST /api/agent`, which answers 503 while the model has no key.

Invariants (tests/test_agent.py checks them): the agent is built without a model, so the API
starts without a provider key; every run has usage limits; no test calls a real model
(tests/conftest.py blocks it).
"""
