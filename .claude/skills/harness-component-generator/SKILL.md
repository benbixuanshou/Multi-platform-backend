---
name: harness-component-generator
description: Generates new Harness components (Hooks, Tools, Providers) following this project's conventions. Use when the user asks to "add a hook", "create a new hook", "add a harness component", "implement a new Check", "add a Provider", or mentions extending the harness framework.
---

# Harness Component Generator

## Purpose

Generate new Harness components that integrate correctly with the existing framework.

## When to Activate

- User asks to create a new Hook, Tool, or Provider
- User mentions `HookPipeline`, `ToolRegistry`, `ModelProvider`, `EmbeddingProvider`
- User says "we need a new check" or "add a RateLimitHook"

## Component Types

### Hook

Hook responsibilities: pre-model, post-model, pre-tool, post-tool, or on_error.

Template: `assets/hook.py.tmpl`

Two failure modes:
- **Blocking** (pre_model, pre_tool): hook failure stops the pipeline. Use for RateLimit, ContextBudget.
- **Non-blocking** (post_model, post_tool): hook failure adds warning, pipeline continues. Use for SafetyCheck, Logging.

### Provider

Provider responsibilities: abstract an external API behind a swappable interface.

See existing: `ModelProvider` (LLM), `EmbeddingProvider` (embeddings).

### Tool

Tool responsibilities: a readonly or write operation the Agent can invoke.

Registered in: `ToolRegistry`.

## Hook Implementation Checklist

Generate a Hook by following these steps in order:

1. Determine which pipeline phase the hook belongs to:
   - `pre_model`: Runs before LLM call. Blocking.
   - `post_model`: Runs after LLM response. Non-blocking (add warnings, don't crash).
   - `on_error`: Runs on exception. Manages retry logic.

2. Class signature:
   ```python
   class XxxHook:
       async def __call__(self, ctx: HookContext) -> None:
   ```

3. `HookContext` fields available:
   - `ctx.task`: dict, the agent task
   - `ctx.compressed`: bool, set by ContextBudgetHook
   - `ctx.warnings`: list[str], append warnings here
   - `ctx.budget_remaining`: int

4. Register in `AGENT_HOOKS` config (see [references/hook-config.md](references/hook-config.md)).

5. Add tests to `tests/phase2_harness/test_xxx_hook.py`.

## Provider Implementation Checklist

1. Inherit from the abstract base class (see existing `ModelProvider` or `EmbeddingProvider`).
2. Implement all abstract methods.
3. Add config key to `.env.example` and `.env`.
4. Register in the agent config.

## Reference

See existing implementations:
- `backend/harness/hooks/safety_check.py` — Non-blocking post_model hook
- `backend/harness/hooks/schema_validation.py` — Blocking post_model hook
- `backend/harness/model_provider.py` — Provider pattern
- `backend/harness/embedding_provider.py` — Provider pattern
