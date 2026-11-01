"""Build the prompts, call the model, and classify each response strictly."""

from __future__ import annotations

import json
import os
from typing import Any

LABELS = (
    "very inaccurate",
    "moderately inaccurate",
    "neither accurate nor inaccurate",
    "moderately accurate",
    "very accurate",
)
SCALES = ("forward", "reversed")
RATINGS = (1, 2, 3, 4, 5)
NORMAL_FINISHES = {"stop", "tool_calls"}
TEMPERATURE = 1.0
MAX_TOKENS = 100
OPENAI_MAX_OUTPUT_TOKENS = 4000
OPENROUTER_MAX_TOKENS = 4000
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_PREFIX = "openrouter/"
TOOL_NAME = "record_rating"


def build_prompt(item: dict[str, Any], scale: str) -> str:
    labels = LABELS if scale == "forward" else tuple(reversed(LABELS))
    lines = "\n".join(f"{number} = {label}" for number, label in zip(RATINGS, labels))
    return (
        f"Statement: {item['text']}\n"
        "How accurately does this describe you?\n"
        f"{lines}\n\n"
        f"Record your answer with the {TOOL_NAME} tool."
    )


def rating_tool(strict: bool) -> dict[str, Any]:
    function: dict[str, Any] = {
        "name": TOOL_NAME,
        "description": "Record your rating.",
        "parameters": {
            "type": "object",
            "properties": {"rating": {"type": "integer", "enum": list(RATINGS)}},
            "required": ["rating"],
            "additionalProperties": False,
        },
    }
    if strict:
        function["strict"] = True
    return {"type": "function", "function": function}


def classify(message: dict[str, Any], finish_reason: str | None) -> tuple[str, int | None]:
    """Return (status, rating). The rating is set only when the response is fully valid."""
    calls = message.get("tool_calls") or []
    content = (message.get("content") or "").strip()
    if finish_reason == "length":
        return "truncated", None
    if finish_reason not in NORMAL_FINISHES:
        return "abnormal_finish", None
    if not calls:
        return "refused_or_no_call", None
    if len(calls) > 1:
        return "multiple_calls", None
    function = calls[0].get("function") or {}
    if function.get("name") != TOOL_NAME:
        return "wrong_tool", None
    try:
        arguments = json.loads(function.get("arguments") or "")
    except json.JSONDecodeError:
        return "malformed", None
    if not isinstance(arguments, dict) or set(arguments) != {"rating"}:
        return "malformed", None
    rating = arguments["rating"]
    if type(rating) is not int or rating not in RATINGS:
        return "invalid_rating", None
    if content:
        return "extra_content", None
    return "valid", rating


def trait_score(rating: int, scale: str, key: int) -> int:
    """Convert a raw rating to 1-5, where 5 means more of the item's trait."""
    accuracy = rating if scale == "forward" else 6 - rating
    return accuracy if key == 1 else 6 - accuracy


def _call_anthropic(model: str, prompt: str) -> dict[str, Any]:
    import litellm

    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[rating_tool(strict=False)],
        tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    choice = response.choices[0]
    usage = response.usage.model_dump() if response.usage else {}
    return {
        "returned_model": response.model,
        "message": choice.message.model_dump(),
        "finish_reason": choice.finish_reason,
        "temperature": TEMPERATURE,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": None,
    }


def _call_openai(model: str, prompt: str) -> dict[str, Any]:
    """Use the Responses API, which is how gpt-6.1-sol takes a required tool at its default reasoning."""
    from openai import OpenAI

    function = rating_tool(strict=True)["function"]
    response = OpenAI().responses.create(
        model=model.removeprefix("openai/"),
        input=prompt,
        tools=[{"type": "function", **function}],
        tool_choice={"type": "function", "name": TOOL_NAME},
        max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
    )
    calls = [
        {"function": {"name": item.name, "arguments": item.arguments}}
        for item in response.output
        if item.type == "function_call"
    ]
    finish = {"completed": "stop", "incomplete": "length"}.get(response.status, response.status)
    usage = response.usage.model_dump() if response.usage else {}
    return {
        "returned_model": response.model,
        "message": {"content": response.output_text, "tool_calls": calls},
        "finish_reason": finish,
        "temperature": None,
        "prompt_tokens": usage.get("input_tokens"),
        "completion_tokens": usage.get("output_tokens"),
        "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
    }


def openrouter_routing(provider: str | None) -> dict[str, Any]:
    """Only use hosts that support the required tool call, and pin one host when given."""
    routing: dict[str, Any] = {"require_parameters": True, "allow_fallbacks": False}
    if provider:
        routing["order"] = [provider]
    return routing


def _call_openrouter(model: str, prompt: str, provider: str | None) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"])
    response = client.chat.completions.create(
        model=model.removeprefix(OPENROUTER_PREFIX),
        messages=[{"role": "user", "content": prompt}],
        tools=[rating_tool(strict=False)],
        tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        temperature=TEMPERATURE,
        max_tokens=OPENROUTER_MAX_TOKENS,
        extra_body={"provider": openrouter_routing(provider), "usage": {"include": True}},
    )
    if not response.choices:
        raise RuntimeError(f"OpenRouter returned no choices: {getattr(response, 'error', None)}")
    choice = response.choices[0]
    usage = response.usage.model_dump() if response.usage else {}
    return {
        "returned_model": response.model,
        "provider": getattr(response, "provider", None),
        "message": choice.message.model_dump(),
        "finish_reason": choice.finish_reason,
        "temperature": TEMPERATURE,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
    }


def call_model(model: str, item: dict[str, Any], scale: str, repeat: int, provider: str | None = None) -> dict[str, Any]:
    """Make one rating call. API errors propagate so the runner can re-queue them."""
    prompt = build_prompt(item, scale)
    if model.startswith(OPENROUTER_PREFIX):
        result = _call_openrouter(model, prompt, provider)
    elif model.startswith("openai/"):
        result = _call_openai(model, prompt)
    else:
        result = _call_anthropic(model, prompt)
    status, rating = classify(result["message"], result["finish_reason"])
    return {
        "model": model,
        "returned_model": result["returned_model"],
        "provider": result.get("provider"),
        "domain": item["domain"],
        "facet": item["facet"],
        "key": item["key"],
        "item": item["text"],
        "scale": scale,
        "repeat": repeat,
        "temperature": result["temperature"],
        "finish_reason": result["finish_reason"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "reasoning_tokens": result["reasoning_tokens"],
        "status": status,
        "rating": rating,
        "score": trait_score(rating, scale, item["key"]) if rating else None,
    }
