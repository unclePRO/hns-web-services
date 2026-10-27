from datetime import datetime, timedelta, timezone
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
# Configuration loader
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
ISSUER = "Internal Auth API"
FLAG = "HNS{jwt_legacy_header_claim_escalation}"

DEFAULT_DECODE_OPTIONS = {
    "verify_signature": True,
    "verify_exp": True,
    "require": ["sub", "role", "iss", "aud", "clearance", "exp"]
}


# --------------------------------------------------
# Token lifecycle and validation helpers
# --------------------------------------------------

def issue_employee_token(username="employee_01"):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": "employee",
        "clearance": 1,
        "iss": ISSUER,
        "aud": "employee-portal",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp())
    }
    headers = {
        "typ": "JWT",
        "alg": "HS256"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256", headers=headers)


def build_decode_options(token_header, mode="strict"):
    options = dict(DEFAULT_DECODE_OPTIONS)

    # Legacy SSO migration compatibility support for v1 internal tokens
    if mode == "portal" and token_header.get("typ") == "JWT-LEGACY":
        options["verify_signature"] = False

    return options


def decode_token_strict(token):
    header = jwt.get_unverified_header(token)
    options = build_decode_options(header, mode="strict")
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=["HS256"],
        issuer=ISSUER,
        audience=["employee-portal", "internal-admin"],
        options=options
    )


def decode_portal_token(token):
    header = jwt.get_unverified_header(token)
    options = build_decode_options(header, mode="portal")
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=["HS256"],
        issuer=ISSUER,
        audience=["employee-portal", "internal-admin"],
        options=options
    )


def validate_admin_claims(claims):
    if claims.get("role") != "admin":
        return False, f"Role '{claims.get('role')}' does not have administrative access."

    if claims.get("aud") != "internal-admin":
        return False, "Token audience must be scoped to 'internal-admin'."

    clearance = claims.get("clearance", 0)
    if not isinstance(clearance, int) or clearance < 5:
        return False, "Insufficient security clearance level (Level 5 required)."

    return True, "Authorized"


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
        "version": "1.5.0",
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
            "Generate an employee JWT via /api/token and authenticate with internal services."
    })


@app.route("/api/token", methods=["GET", "POST"])
def get_token():
    username = request.args.get("user", "employee_01")
    token = issue_employee_token(username)
    return jsonify({
        "token": token,
        "role": "employee",
        "clearance": 1,
        "audience": "employee-portal",
        "message": "Standard employee token issued."
    })


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
            "error": f"Token validation failed: {str(exc)}"
        }), 401


# --------------------------------------------------
# Administration Portal & API
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
                claims = decode_portal_token(token)
                authorized, reason = validate_admin_claims(claims)
                if authorized:
                    message = f"Welcome, Administrator ({claims.get('sub', 'unknown')})."
                    flag = FLAG
                else:
                    message = f"Access denied: {reason}"
            except jwt.InvalidTokenError as exc:
                message = f"Token rejected: {str(exc)}"

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
        claims = decode_portal_token(token)
    except jwt.InvalidTokenError as exc:
        return jsonify({"error": f"Invalid token: {str(exc)}"}), 401

    authorized, reason = validate_admin_claims(claims)
    if not authorized:
        return jsonify({
            "error": "Insufficient privileges",
            "detail": reason
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


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5001,
        debug=False
    )