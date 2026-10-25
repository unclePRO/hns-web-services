# JWT Unverified Signature CTF --- Setup & Exploit Notes

## Overview

A web-exploitation CTF service demonstrating **JWT Authentication Bypass via Unverified Signature** (PortSwigger JWT category).

**Intended solve:** Request a standard token from `/api/token` → inspect its structure via `/api/verify` → modify the payload claim from `"role": "employee"` to `"role": "admin"` (without knowing `JWT_SECRET`) → submit the forged token to `/api/admin/` or `/api/admin/flag` → obtain the flag.

## Run Flask locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py