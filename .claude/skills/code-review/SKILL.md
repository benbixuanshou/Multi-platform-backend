---
name: code-review
description: Review newly written or modified code before commit. Check security (OWASP top 10, injection, auth bypass), correctness (edge cases, error handling), and project conventions (Harness component patterns, naming, structure). Use after completing a Phase step, before committing code. Trigger: user says "review", "code review", "check code", "审查", or after Phase completion.
---

# Code Review

## Purpose

Review code changes before commit. Focus on issues automated tools miss — security logic flaws, project convention violations, business logic errors, and API design inconsistencies.

## When to Use

- After completing any Phase step
- Before `git commit`
- When user explicitly asks for a review
- When reviewing PRs or code diffs

## Review Checklist (5 dimensions, ordered by priority)

### 1. Security (non-negotiable)

- **Input validation**: All user input has allow-list validation or Pydantic schema constraints. No raw strings accepted without length/format checks.
- **Injection**: SQL uses ORM parameterized queries (NO string concatenation). Command execution uses `shlex.quote` or subprocess with list args.
- **Auth bypass**: Every protected endpoint has `Depends(get_current_user)`. No auth check that can be skipped by omitting headers.
- **Secrets**: No API keys, passwords, tokens hardcoded in source. All secrets from `os.getenv()` or `Settings` class.
- **Information leakage**: Error messages don't reveal user existence (login says "Invalid email or password" not "User not found"). Stack traces never returned in production.
- **IDOR**: Resource access checks ownership (`comment.user_id == current_user.id`), not just existence.
- **Rate limiting**: Login/register endpoints have rate limiting (via RateLimitHook). If not yet implemented, flag as known debt.

### 2. Correctness

- **Edge cases**: Empty input, null/None values, zero-length arrays, very large inputs.
- **Error handling**: All external calls (DB, API, Redis) wrapped in try/except. Exceptions return appropriate HTTP status codes, not 500.
- **Transactions**: Multi-table writes use transactions. No partial writes on failure.
- **Idempotency**: Operations that shouldn't repeat (send reply, create user) have duplicate detection.
- **Async**: All I/O uses `await`. No blocking calls in async context.

### 3. Project Conventions

- **Harness components**: New Hook/Provider/Tool follows existing interface patterns. Hook has failure strategy (blocking vs non-blocking). Tool has timeout and readonly flag.
- **Models**: CHAR(36) UUID PK, TIMESTAMP with default, InnoDB engine, FOR UPDATE SKIP LOCKED for queues.
- **API routes**: Route files use APIRouter, Pydantic schemas for request/response, Depends for DI. Stubs return valid JSON, not Ellipsis.
- **Naming**: Python files snake_case, classes PascalCase, functions snake_case. API paths kebab-case.
- **Imports**: Standard library first, then third-party, then project modules. No circular imports.

### 4. API Design

- **Response consistency**: All endpoints return JSON. Error responses have `{"detail": "..."}` format (FastAPI default).
- **Status codes**: 201 for creation, 204 for no-content, 401 for auth failure, 403 for forbidden, 404 for not found, 409 for conflict, 422 for validation.
- **Pagination**: List endpoints accept `page` and `page_size` params. Response includes `total` count.
- **Breaking changes**: No renaming or removing existing fields without deprecation notice.

### 5. Testing

- **Smoke test**: Is the new/updated endpoint covered in `tests/phase{N}_smoke.py` or equivalent?
- **Edge case test**: Are there tests for empty results, invalid input, auth failure?
- **Regression**: Does the change break any existing test? Run the phase test script.

## Output Format

After review, output a summary:

```
## Review: [files reviewed]

### Security
- [issue or "no issues found"]

### Correctness
- [issue or "no issues found"]

### Project Conventions
- [issue or "no issues found"]

### API Design
- [issue or "no issues found"]

### Testing
- [issue or "no issues found"]

### Known Debt (not blocking, should fix later)
- [item or "none"]

### Verdict
[APPROVED / CHANGES NEEDED]
```

## Common Anti-Patterns to Flag

```
❌ password = request.body["password"]         → ✅ password: str (Pydantic schema)
❌ query = f"SELECT * FROM users WHERE id={id}" → ✅ select(User).where(User.id == id)
❌ except: pass                                → ✅ except SpecificError: logger.error(...)
❌ return {"error": "something"}               → ✅ raise HTTPException(status_code=400, detail="...")
❌ if user == None: ...                        → ✅ if user is None: ...
❌ datetime.utcnow()                            → ✅ datetime.now(timezone.utc)
```
