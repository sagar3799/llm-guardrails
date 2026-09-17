"""One-endpoint demo: POST /chat runs check_input() before a fake LLM call and
check_output() before the response goes back. FastAPI never becomes the project — this
is the one file that exists so someone can `curl` a real request path and watch
guardrails intercept it, instead of reading a CLI script. See docs/buildplan.md, Phase 4.

An optional `policy` field selects a named policy pack (e.g. "strict", "healthcare") via
GuardrailsEngine instead of the zero-config default — see README: "Versioned policy
packs". Omit it to use the plain check_input()/check_output() functions, unchanged.

Run with: uvicorn examples.fastapi_app:app --reload
"""

from __future__ import annotations

from functools import cache

from fastapi import FastAPI
from pydantic import BaseModel

from guardrails.engine import GuardrailsEngine
from guardrails.middleware import check_input, check_output
from guardrails.schemas import GuardResult

app = FastAPI(title="LLM Guardrails Demo")


class ChatRequest(BaseModel):
    message: str
    policy: str | None = None


class ChatResponse(BaseModel):
    reply: str | None
    input_guard: GuardResult
    output_guard: GuardResult | None = None


@cache
def _engine_for(policy: str) -> GuardrailsEngine:
    return GuardrailsEngine(policy_name=policy)


def _fake_llm_call(message: str) -> str:
    """Stands in for a real LLM call — the point of this demo is the guardrails around
    it, not the model behind it."""
    return f"You said: {message}"


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if request.policy:
        engine = _engine_for(request.policy)
        do_check_input, do_check_output = engine.check_input, engine.check_output
    else:
        do_check_input, do_check_output = check_input, check_output

    input_result = do_check_input(request.message)

    if not input_result.allowed:
        return ChatResponse(reply=None, input_guard=input_result)

    llm_input = input_result.sanitized_text or request.message
    raw_reply = _fake_llm_call(llm_input)

    output_result = do_check_output(raw_reply)
    if not output_result.allowed:
        return ChatResponse(reply=None, input_guard=input_result, output_guard=output_result)

    final_reply = output_result.sanitized_text or raw_reply
    return ChatResponse(reply=final_reply, input_guard=input_result, output_guard=output_result)
