"""SchemaValidationHook — JSON schema check on LLM output (Harness Module 6)."""

import json


class SchemaValidationHook:
    def __init__(self, required_fields: list[str]):
        self.required_fields = required_fields

    async def __call__(self, ctx):
        content = ctx.task.get("raw_response", "")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError("LLM output is not valid JSON")
        for field in self.required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        ctx.task["parsed_response"] = data
