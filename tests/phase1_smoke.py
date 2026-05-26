"""Phase 1 verification: FastAPI skeleton + JWT auth.

Run: python tests/phase1_smoke.py
Requires: backend running on localhost:8000, MYSQL_HOST=localhost
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0


def test(name: str, method: str, path: str, body=None, token=None, want_status: int = 200):
    global PASS, FAIL
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body else None
    try:
        resp = urllib.request.urlopen(req, data=data, timeout=5)
        status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        FAIL += 1
        return None

    if status == want_status:
        print(f"  PASS {name} ({status})")
        PASS += 1
    else:
        print(f"  FAIL {name}: expected {want_status}, got {status}")
        FAIL += 1

    if status == 200 or status == 201:
        return json.loads(resp.read())
    return None


# ---- Auth ----
print("\n=== Auth ===")
import uuid
email = f"smoke-{uuid.uuid4().hex[:8]}@test.com"

result = test("register", "POST", "/api/auth/register",
              body={"email": email, "password": "smoke123", "display_name": "Smoke"},
              want_status=201)

result = test("login", "POST", "/api/auth/login",
              body={"email": email, "password": "smoke123"})

test("login bad pw", "POST", "/api/auth/login",
     body={"email": email, "password": "wrong"}, want_status=401)

test("duplicate register", "POST", "/api/auth/register",
     body={"email": email, "password": "x", "display_name": "Dup"},
     want_status=409)

token = result["access_token"] if result else None
refresh_token = result["refresh_token"] if result else None

test("refresh token", "POST", "/api/auth/refresh",
     body={"refresh_token": refresh_token})

test("logout", "POST", "/api/auth/logout", token=token, want_status=204)

# ---- Unauthenticated ----
print("\n=== Public access (no auth required in Phase 1) ===")
test("public endpoint ok", "GET", "/api/comments", want_status=200)

# ---- All stubs alive ----
print("\n=== Route stubs ===")
routes = [
    ("GET", "/api/comments"),
    ("GET", "/api/comments/uuid-test"),
    ("GET", "/api/posts"),
    ("GET", "/api/posts/uuid-test"),
    ("GET", "/api/analytics/overview"),
    ("GET", "/api/analytics/insights"),
    ("GET", "/api/agents/status"),
    ("GET", "/api/settings/profile"),
    ("GET", "/api/settings/platforms"),
    ("GET", "/api/comments/uuid-test/drafts"),
]
for method, path in routes:
    test(f"stub {method} {path}", method, path, token=token)

# ---- Summary ----
print(f"\n{'='*40}")
print(f"Results: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
if FAIL == 0:
    print("Phase 1 PASSED")
else:
    print("Phase 1 FAILED")
    sys.exit(1)
