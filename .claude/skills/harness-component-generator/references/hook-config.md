# Hook Configuration Reference

## Hook phases (5 total)

```
pre_model → post_model → pre_tool → post_tool → on_error
```

## Current hook assignments

```json
{
  "agent_hooks": {
    "classify_router": {
      "pre_model":  ["rate_limit", "context_budget"],
      "post_model": ["schema_validation", "logging"],
      "on_error":   ["retry"]
    },
    "reply_generate": {
      "pre_model":  ["rate_limit", "context_budget"],
      "post_model": ["schema_validation", "safety_check", "logging"],
      "on_error":   ["retry"]
    },
    "insight_mining": {
      "pre_model":  ["rate_limit", "context_budget"],
      "post_model": ["schema_validation", "logging"],
      "on_error":   ["retry"]
    }
  }
}
```

## Adding a new hook

1. Create `backend/harness/hooks/<hook_name>.py`
2. Add to the appropriate agent's hook list in config
3. If global (applied to all agents), add to all three agent configs
4. Specify phase: pre_model (blocking) or post_model (non-blocking)
5. Add test in `tests/phase2_harness/`

## Failures by phase

| Phase | Failure behavior |
|---|---|
| pre_model | Block: stop pipeline before LLM call |
| post_model | Non-block: add warning, continue |
| on_error | Manages retry, can escalate to circuit breaker |
