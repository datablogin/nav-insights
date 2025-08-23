from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional, Sequence, Type, TypeVar

import requests
from requests import Session
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LlamaCppClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "local",
        timeout: int = 120,
        session: Optional[Session] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = session or requests.Session()

    def _chat(
        self,
        messages: Sequence[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.2,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        r = self.session.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

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
        messages = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]
        if hasattr(schema_model, "model_json_schema"):
            json_schema = schema_model.model_json_schema()
        else:
            json_schema = schema_model.schema()  # type: ignore

        if try_json_schema_mode:
            try:
                content = self._chat(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object", "json_schema": json_schema},
                )
                return self._validate(schema_model, content)
            except Exception:
                pass

        fallback = [
            {
                "role": "system",
                "content": (
                    "Return ONLY MINIFIED JSON that validates the provided schema. No prose.\n"
                    + json.dumps(json_schema)
                ),
            },
            {"role": "user", "content": user_prompt.strip()},
        ]
        last_err = None
        for _ in range(retries + 1):
            content = self._chat(fallback, max_tokens=max_tokens, temperature=temperature)
            try:
                return self._validate(schema_model, content)
            except ValidationError as ve:
                last_err = ve
                fallback.append(
                    {
                        "role": "system",
                        "content": (
                            "Previous JSON failed validation: "
                            f"{ve}. Return corrected JSON only."
                        ),
                    }
                )
                time.sleep(0.1)
        raise last_err or RuntimeError("Failed to produce valid JSON.")

    @staticmethod
    def _validate(schema_model: Type[T], content: str) -> T:
        data = json.loads(content)
        if hasattr(schema_model, "model_validate"):
            return schema_model.model_validate(data)  # pydantic v2
        return schema_model.parse_obj(data)  # pydantic v1


def compose_insight_json(
    ir: Any,
    actions: List[Any],
    schema_model: Type[T],
    base_url: str = "http://localhost:8000/v1",
    model: str = "local",
    timeout: Optional[int] = None,
) -> T:
    client = LlamaCppClient(base_url=base_url, model=model, timeout=timeout or 120)
    system = "You produce ONLY MINIFIED JSON that validates the provided schema."
    user = (
        "Given these facts and actions, produce the final Insight JSON.\nFacts:\n"
        + json.dumps(ir, default=str)
        + "\nActions:\n"
        + json.dumps([a.model_dump() for a in actions], default=str)
    )
    return client.generate_structured(schema_model, system, user)
