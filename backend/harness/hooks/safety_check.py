"""SafetyCheckHook — hard constraint on reply drafts (Harness Module 7)."""

import re

FORBIDDEN_WORDS = ["保证", "一定", "最低价", "绝对"]
MAX_LENGTH = 500


class SafetyCheckHook:
    async def __call__(self, ctx):
        for draft in ctx.task.get("drafts", []):
            warnings = []
            for word in FORBIDDEN_WORDS:
                if word in draft["content"]:
                    warnings.append(f"contains_forbidden_word: {word}")
            if len(draft["content"]) > MAX_LENGTH:
                warnings.append("exceeds_max_length")
            if warnings:
                ctx.warnings.append({"draft_style": draft["style"], "warnings": warnings})
