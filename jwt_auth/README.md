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

## Vulnerability Analysis & Flag Conditions

### Why Simple Token Tampering Fails
Unlike basic JWT challenges where signature verification is globally disabled, modifying the payload of a standard employee token directly will fail with `401 Invalid token`. Both `/api/verify` and `/api/admin/flag` enforce `verify_signature: True` whenever the JWT header has `"typ": "JWT"`.

### Conditions Required to Retrieve the Flag
Through source code review of `app.py`, two components govern administrative access:

1. **Header Compatibility Bypass (`build_decode_options`):**
   When `decode_portal_token()` inspects the unverified JWT header via `jwt.get_unverified_header(token)`, it passes `mode="portal"` to `build_decode_options()`. If the header's `typ` field is set to `"JWT-LEGACY"`, the function overrides `options["verify_signature"] = False`.
2. **Multi-Claim Validation (`validate_admin_claims`):**
   Even when a token is decoded, the server enforces strict claim requirements before returning `FLAG`:
   * `iss` must equal `"Internal Auth API"`.
   * `exp` must be a valid future Unix timestamp.
   * `role` must be set to `"admin"`.
   * `aud` must be scoped to `"internal-admin"` (instead of `"employee-portal"`).
   * `clearance` must be an integer `>= 5` (instead of `1`).

When a token satisfying both the header condition and all required claims is submitted to `/api/admin/` or `/api/admin/flag`, the application returns the flag: `HNS{jwt_legacy_header_claim_escalation}`.

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
Restart the Flask server and run the test suite from the project root to confirm all service checks pass:

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