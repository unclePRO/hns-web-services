# JWT Identity Portal - Hack & Shield A&D Challenge

## Service Description
The **Internal Auth API** (`v1.5.0`) is a simulated corporate Single Sign-On (SSO) dashboard that issues and validates JSON Web Tokens (JWT) for internal microservices.

**The Vulnerability:** The service contains a **Header-Triggered Signature Verification Bypass** combined with **Multi-Claim Privilege Escalation**. By default, all tokens with a standard `"typ": "JWT"` header undergo strict `HS256` cryptographic verification. However, a legacy SSO compatibility branch inside `build_decode_options()` disables signature verification when `mode="portal"` and the token header specifies `"typ": "JWT-LEGACY"`.

## What to Expect (Service Flow)
When the service is running, it exposes the following endpoints:
* `GET /api/token` - Issues a signed employee JWT (`role: "employee"`, `clearance: 1`, `aud: "employee-portal"`).
* `GET /api/verify` - Strictly validates a token's signature and returns its decoded payload.
* `GET /api/admin/flag` - Protected administrative endpoint requiring a Bearer token that passes both `decode_portal_token()` and `validate_admin_claims()`.
* `GET /api/admin/` - Web UI portal equivalent for submitting administrative tokens.

## Local Setup & Deployment
Run these commands from the project root to start the service:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
*The service listens on `http://127.0.0.1:5001`.*

---

## Attack Phase (Red Team) — Conceptual Walkthrough
The goal of the Red Team is to analyze the authentication logic, identify how legacy tokens are processed, and satisfy the administrative claim checks to retrieve the flag.

### Step 1: Endpoint & Token Reconnaissance
Inspect the service endpoints via `/api/help` and request a baseline token from `/api/token`. Decoding a standard employee token reveals the baseline structure:

**Standard Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Standard Payload:**
```json
{
  "sub": "employee_01",
  "role": "employee",
  "clearance": 1,
  "iss": "Internal Auth API",
  "aud": "employee-portal",
  "iat": 1730000000,
  "exp": 1730007200
}
```

Attempting to modify `"role": "admin"` on a standard token and submitting it to `/api/admin/` or `/api/admin/flag` fails with a `401` error because `DEFAULT_DECODE_OPTIONS` enforces `"verify_signature": True`.

### Step 2: Source Code Audit (Identifying the Header Bypass)
Reviewing `app.py` reveals a difference between how `/api/verify` and the admin endpoints decode tokens:
* `/api/verify` calls `decode_token_strict()`, which passes `mode="strict"` to `build_decode_options()`.
* `/api/admin/` and `/api/admin/flag` call `decode_portal_token()`, which inspects the unverified JWT header (`jwt.get_unverified_header(token)`) and passes `mode="portal"` to `build_decode_options()`.

Inside `build_decode_options()`, if `mode == "portal"` and the header's `typ` field is set to `"JWT-LEGACY"`, the decoder overrides `options["verify_signature"] = False`.

### Step 3: Satisfying Multi-Claim Validation
Bypassing signature verification via the header alone is not sufficient. Both admin endpoints pass the decoded claims into `validate_admin_claims(claims)` and verify required fields defined in `DEFAULT_DECODE_OPTIONS`. To pass all checks, a token must contain:

**Required Header Structure:**
```json
{
  "alg": "HS256",
  "typ": "JWT-LEGACY"
}
```

**Required Payload Claims:**
```json
{
  "sub": "admin_user",
  "role": "admin",
  "clearance": 5,
  "iss": "Internal Auth API",
  "aud": "internal-admin",
  "exp": 1999999999
}
```
* `role` must equal `"admin"`.
* `aud` must be changed from `"employee-portal"` to `"internal-admin"`.
* `clearance` must be an integer greater than or equal to `5`.
* `iss` must remain `"Internal Auth API"`, and `exp` must be a valid future Unix timestamp.

### Step 4: Retrieving the Flag
When a JWT encoded with the `"typ": "JWT-LEGACY"` header and the escalated administrative claims is submitted to the service:
1. **Via the Web Portal:** Paste the token into the form at `http://127.0.0.1:5001/api/admin/` and click **Verify JWT & Authenticate**.
2. **Via the API:** Send the token in the `Authorization: Bearer <token>` HTTP header to `GET /api/admin/flag`.

Once both `decode_portal_token()` and `validate_admin_claims()` succeed, the service responds with:
`{"flag": "HNS{jwt_legacy_header_claim_escalation}", "message": "Administrator authenticated"}`

---

## Defense Phase (Blue Team)
Your goal as a defender is to patch the legacy compatibility bypass in `app.py` so unverified tokens are never accepted, while keeping legitimate employee token generation and verification intact.

### Step 1: Locate the Flaw
Open `app.py` and inspect `build_decode_options(token_header, mode="strict")`. Notice how the `JWT-LEGACY` condition mutates the `options` dictionary to disable signature verification for portal endpoints.

### Step 2: Apply the Patch
Remove the legacy override inside `build_decode_options()` so that `DEFAULT_DECODE_OPTIONS` (which enforces `"verify_signature": True`) is always used regardless of the `typ` header.

**Vulnerable Code:**
```python
def build_decode_options(token_header, mode="strict"):
    options = dict(DEFAULT_DECODE_OPTIONS)

    # Legacy SSO migration compatibility support for v1 internal tokens
    if mode == "portal" and token_header.get("typ") == "JWT-LEGACY":
        options["verify_signature"] = False

    return options
```

**Patched Code:**
```python
def build_decode_options(token_header, mode="strict"):
    options = dict(DEFAULT_DECODE_OPTIONS)
    return options
```

*(Alternatively, update `decode_portal_token()` to call `decode_token_strict(token)` directly).*

### Step 3: Verify the Fix (SLA Check)
Restart the Flask server and run the automated test suite from the project root to confirm all service checks pass:

```bash
source .venv/bin/activate
python -m pytest -v
```

You can also verify manually that normal employee tokens still validate properly:
```bash
NORMAL_TOKEN=$(curl -s [http://127.0.0.1:5001/api/token](http://127.0.0.1:5001/api/token) | jq -r .token)
curl -s "[http://127.0.0.1:5001/api/verify?token=$NORMAL_TOKEN](http://127.0.0.1:5001/api/verify?token=$NORMAL_TOKEN)"
```
**Expected Output:** `{"claims":{...},"valid":true}`