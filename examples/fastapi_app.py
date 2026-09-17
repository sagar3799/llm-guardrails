"""One-endpoint demo: POST /chat runs check_input() before a fake LLM call and
check_output() before the response goes back. FastAPI never becomes the project — this
is the one file that exists so someone can `curl` a real request path and watch
guardrails intercept it, instead of reading a CLI script. See docs/buildplan.md, Phase 4.

Run with: uvicorn examples.fastapi_app:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from guardrails.middleware import check_input, check_output
from guardrails.schemas import GuardResult

app = FastAPI(title="LLM Guardrails Demo")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str | None
    input_guard: GuardResult
    output_guard: GuardResult | None = None


def _fake_llm_call(message: str) -> str:
    """Stands in for a real LLM call — the point of this demo is the guardrails around
    it, not the model behind it."""
    return f"You said: {message}"


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    input_result = check_input(request.message)

    if not input_result.allowed:
        return ChatResponse(reply=None, input_guard=input_result)

    llm_input = input_result.sanitized_text or request.message
    raw_reply = _fake_llm_call(llm_input)

    output_result = check_output(raw_reply)
    if not output_result.allowed:
        return ChatResponse(reply=None, input_guard=input_result, output_guard=output_result)

    final_reply = output_result.sanitized_text or raw_reply
    return ChatResponse(reply=final_reply, input_guard=input_result, output_guard=output_result)
