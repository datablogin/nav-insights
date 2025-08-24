from __future__ import annotations
import json
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def to_minified_json(model: BaseModel) -> str:
    return model.model_dump_json(exclude_none=True, separators=(",", ":"))


def schema_json(model_cls: Type[T]) -> str:
    if hasattr(model_cls, "model_json_schema"):
        schema = model_cls.model_json_schema()
    else:
        schema = model_cls.schema()  # pydantic v1
    return json.dumps(schema, indent=2)
