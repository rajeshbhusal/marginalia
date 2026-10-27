from typing import Any

from pydantic import BaseModel, ConfigDict


def _const_to_enum(schema: dict[str, Any]) -> None:
    # Single-value Literals render as "const"; a one-item enum means the same thing and is
    # accepted by every provider's structured-output schema subset.
    for prop in schema.get("properties", {}).values():
        if "const" in prop:
            prop["enum"] = [prop.pop("const")]


class DraftModel(BaseModel):
    """Base for schemas the model fills in through structured outputs.

    Keep these flat and explicit: every field required (use `| None` for optional values), no
    numeric or length constraints, and descriptions that tell the model what to write.
    """

    model_config = ConfigDict(json_schema_extra=_const_to_enum)
