"""
llm_llamacpp.py
A minimal client for the llama.cpp HTTP server (OpenAI-compatible API) with
a helper for schema-validated (Pydantic) outputs.

Usage:
  1) Start llama.cpp server (example):
       llama-server -m ./models/mistral-7b-instruct.Q4_K_M.gguf --port 8000
     (Docs: https://github.com/ggml-org/llama.cpp#readme)

  2) Use LlamaCppClient.generate_structured(...) with a Pydantic model schema.
     The client will attempt JSON-schema mode if the server supports it,
     and fall back to "prompt-only + validate + retry" otherwise.

Notes:
  - Some llama.cpp builds have had intermittent issues with response_format/json_schema
    on /v1/chat/completions. We handle this by graceful fallback.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LlamaCppClient:
    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "local", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # --- Low-level ---
    def _chat(self, messages: Sequence[Dict[str, str]], max_tokens: int = 512, temperature: float = 0.2,
              response_format: Optional[Dict[str, Any]] = None) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        # OpenAI-compatible shape
        return data["choices"][0]["message"]["content"]

    # --- High-level structured generation ---
    def generate_structured(
        self,
        schema_model: Type[T],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
        retries: int = 2,
        try_json_schema_mode: bool = True,
    ) -> T:
        """
        Ask the model to return *only* JSON that validates against schema_model.
        Strategy:
          1) Attempt response_format with JSON schema (if server supports it).
          2) Fallback: prompt says "ONLY return JSON" and we validate; on failure we retry with error hints.
        """
        messages = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]

        # Prepare JSON schema (Pydantic v2 or v1)
        if hasattr(schema_model, "model_json_schema"):
            json_schema = schema_model.model_json_schema()
        else:
            json_schema = schema_model.schema()  # type: ignore

        # 1) Try JSON schema mode
        if try_json_schema_mode:
            try:
                content = self._chat(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={
                        "type": "json_object",
                        "json_schema": json_schema,
                    },
                )
                return self._validate(schema_model, content)
            except requests.HTTPError as http_err:
                # Known: some server builds reject json_schema or grammar; fall back
                # print(f"[llama.cpp] json_schema mode failed: {http_err}. Falling back to prompt-only.")
                pass
            except Exception:
                # Fall through to fallback
                pass

        # 2) Fallback loop: prompt-only + validation + repair retries
        guidance = (
            "You are a strict JSON generator. Respond with ONLY minified JSON (no code fences, no prose). "
            "The JSON MUST validate against the provided schema. Do not include any fields not in the schema."
        )
        fallback_messages = [
            {"role": "system", "content": guidance + "\nJSON Schema:\n" + json.dumps(json_schema)},
            {"role": "user", "content": user_prompt.strip()},
        ]
        last_err = None
        for attempt in range(retries + 1):
            content = self._chat(fallback_messages, max_tokens=max_tokens, temperature=temperature, response_format=None)
            try:
                return self._validate(schema_model, content)
            except ValidationError as ve:
                last_err = ve
                # Append error feedback and retry
                fallback_messages.append({
                    "role": "system",
                    "content": f"Your previous JSON failed validation. Errors:\n{ve}\n"
                               f"Output ONLY corrected JSON that matches the schema."
                })
                time.sleep(0.2)

        # If we reach here, all attempts failed
        raise last_err or RuntimeError("Failed to produce valid JSON.")

    @staticmethod
    def _validate(schema_model: Type[T], content: str) -> T:
        """
        Parse and validate model JSON. Accept only JSON objects.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValidationError.from_exception_data(schema_model.__name__, [{
                "type": "json_decode_error",
                "loc": ("__root__",),
                "msg": f"Invalid JSON: {e}",
                "input": content,
            }])
        # pydantic v2
        if hasattr(schema_model, "model_validate"):
            return schema_model.model_validate(data)  # type: ignore[attr-defined]
        # pydantic v1
        return schema_model.parse_obj(data)  # type: ignore[attr-defined]


if __name__ == "__main__":
    # Demo usage with the Insight schema
    from schemas import Insight  # make sure schemas.py is discoverable on PYTHONPATH

    client = LlamaCppClient(base_url="http://localhost:8000/v1", model="local")
    system = "You turn structured PPC audit facts into operator-ready insights as valid JSON."
    user = "Produce an Insight JSON with empty sections/actions for a placeholder test."

    insight = client.generate_structured(
        schema_model=Insight,
        system_prompt=system,
        user_prompt=user,
        max_tokens=400,
        temperature=0.1,
        retries=1,
        try_json_schema_mode=True,
    )
    print(insight.model_dump_json(indent=2))
