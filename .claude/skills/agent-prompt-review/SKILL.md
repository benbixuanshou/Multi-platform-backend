---
name: agent-prompt-review
description: Reviews and validates Agent System Prompts for this project. Use when the user asks to "review a prompt", "check prompt quality", "validate agent prompt", "add a new agent prompt", "change the classify prompt", "update the reply prompt", or mentions prompt completeness, required fields, or output format.
---

# Agent Prompt Review

## Purpose

Validate that an Agent System Prompt meets this project's conventions before committing.

## When to Activate

- User asks to create, modify, or review an Agent System Prompt
- User mentions a specific agent's prompt file
- User asks "is this prompt complete?"

## Review Checklist

Run through each item. Report violations with file path and line reference.

### 1. YAML Frontmatter (for modular prompts)

For prompts under `backend/agents/prompts/` using the Skills-like modular format:

> See [references/required-fields.md](references/required-fields.md) for the complete per-agent field specification.

### 2. Prompt Structure (all agents)

- [ ] **Role definition**: Present. Declares agent identity, not generic ("classification engine" not "AI assistant").
- [ ] **Input specification**: Clearly defines what variables are injected (`{platform}`, `{content}`, `{username}`, etc.).
- [ ] **Output format**: Strict JSON, no markdown wrapping. Every field enumerated with allowed values.
- [ ] **Safety rules**: Contains at minimum: never promise, never price, never pretend to be creator.
- [ ] **Edge cases**: Addresses emoji-only, dialect/slang, very short comments, very long comments.
- [ ] **No model recommendation**: Must not mention specific models (Claude, DeepSeek, etc.). That belongs in ModelProvider config.

### 3. Classification Agents (ClassifyRouter)

- [ ] All 7 `category` values enumerated
- [ ] All `intent` sub-values enumerated per category
- [ ] `urgency` rules defined (HIGH/MEDIUM/LOW triggers)
- [ ] `needs_reply` decision logic clear
- [ ] Output includes `confidence` field

### 4. Generation Agents (ReplyGenerate)

- [ ] Exactly 3 styles: warm, casual, professional
- [ ] Each style has distinct, concrete guidance (not "be warm" — "use 姐妹/宝子, talk like a friend")
- [ ] `recommended` field in output
- [ ] `risk_warning` field (nullable string)

### 5. Review Agents (ReplyCritic)

- [ ] Four scoring dimensions: style_match, completeness, safety, naturalness
- [ ] Three recommendation levels defined: all_good, review_recommended, needs_regeneration
- [ ] `regeneration_hint` field when needs_regeneration

## Post-Review Workflow

After changes pass review, remind the user:

1. Run eval set: `python tests/phase3_classify_eval.py` (for classify) or `python tests/phase4_reply_eval.py` (for reply)
2. Compare old vs new scores. Do not merge if accuracy drops.
3. Record prompt version in commit message.

## Common Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Prompt says "use Haiku for this" | Remove. Model selection is ModelProvider config. |
| Missing confidence field | Add `confidence: 0.0-1.0` to output. |
| "回复要有温度" (too vague) | Replace with concrete: "use 姐妹/宝子 naturally, 1-2 emoji max". |
| Only 6 categories listed | Must have all 7: question, complaint, praise, spam, neutral, ugc_gold, collab_inquiry. |
| Style description repeated across styles | Each style must have unique, distinguishable guidance. |
