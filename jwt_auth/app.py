from pathlib import Path
import jwt
from flask import Flask, jsonify, request, render_template

# --------------------------------------------------
# Paths and application setup
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CHALLENGE_ROOT = (BASE_DIR / "challenge_fs").resolve()
CONFIG_FILE = CHALLENGE_ROOT / ".env"

app = Flask(__name__)


# --------------------------------------------------
# Load simulated challenge configuration
# --------------------------------------------------

def load_config():
    config = {}

    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()

    return config


CONFIG = load_config()
JWT_SECRET = CONFIG.get("JWT_SECRET", "default-fallback-secret")
FLAG = "HNS{jwt_unverified_signature_demo}"


# --------------------------------------------------
# JWT Helper Functions
# --------------------------------------------------

def issue_employee_token(username="employee_01"):
    payload = {
        "sub": username,
        "role": "employee",
        "iss": "Internal Auth API"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token_strict(token):
    """Secure decoder used by the public token inspector."""
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def decode_admin_token(token):
    # Decode token for admin portal access
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_signature": False}
    )

# --------------------------------------------------
# Main portal
# --------------------------------------------------

@app.get("/")
def home():
    sample_token = issue_employee_token()
    return render_template("index.html", sample_token=sample_token)


# --------------------------------------------------
# Public API endpoints
# --------------------------------------------------

@app.get("/api/status")
def status():
    return jsonify({
        "service": "Internal Auth API",
        "version": "1.4.0",
        "status": "online"
    })


@app.get("/api/help")
def help_api():
    return jsonify({
        "available_endpoints": {
            "status": "/api/status",
            "help": "/api/help",
            "issue_token": "/api/token",
            "verify_token": "/api/verify?token=<jwt_token>",
            "admin_portal": "/api/admin/",
            "admin_flag_api": "/api/admin/flag"
        },
        "auth_description":
            "Generate an employee JWT via /api/token and use /api/admin/ for elevated access."
    })


@app.route("/api/token", methods=["GET", "POST"])
def get_token():
    username = request.args.get("user", "employee_01")
    token = issue_employee_token(username)
    return jsonify({
        "token": token,
        "role": "employee",
        "message": "Standard employee token issued."
    })


# --------------------------------------------------
# Secure token verification endpoint
# --------------------------------------------------

@app.get("/api/verify")
def verify_token():
    token = request.args.get("token", "").strip()

    if not token:
        return jsonify({"error": "Missing token parameter"}), 400

    try:
        claims = decode_token_strict(token)
        return jsonify({
            "valid": True,
            "claims": claims
        })
    except jwt.InvalidTokenError as exc:
        return jsonify({
            "valid": False,
            "error": f"Signature verification failed: {str(exc)}"
        }), 401


# --------------------------------------------------
# Vulnerable Admin Portal & API
# --------------------------------------------------

@app.route("/api/admin/", methods=["GET", "POST"])
def admin_portal():
    message = ""
    flag = None
    claims = None

    if request.method == "POST":
        token = request.form.get("token", "").strip()

        if not token:
            message = "Please provide a JWT session token."
        else:
            try:
                claims = decode_admin_token(token)
                if claims.get("role") == "admin":
                    message = f"Welcome, Administrator ({claims.get('sub', 'unknown')})."
                    flag = FLAG
                else:
                    message = (
                        f"Access denied. Token role is '{claims.get('role')}', "
                        "but 'admin' is required."
                    )
            except jwt.InvalidTokenError:
                message = "Malformed JWT token."

    return render_template(
        "admin.html",
        message=message,
        flag=flag,
        claims=claims
    )


@app.get("/api/admin/flag")
def admin_flag_api():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing Bearer token"}), 401

    token = auth_header.split(" ", 1)[1].strip()

    try:
        claims = decode_admin_token(token)
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    if claims.get("role") != "admin":
        return jsonify({
            "error": "Insufficient privileges",
            "current_role": claims.get("role")
        }), 403

    return jsonify({
        "message": "Administrator authenticated",
        "flag": FLAG
    })


# --------------------------------------------------
# Error handling
# --------------------------------------------------

@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Endpoint not found"}), 404


# --------------------------------------------------
# Run locally
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5001,
        debug=False
    )