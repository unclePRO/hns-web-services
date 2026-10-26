# Internal Systems A&D Services

## Overview
This repository contains a suite of three intentionally vulnerable web services designed for the **Hack & Shield 2026 Attack & Defense (A&D) CTF**. The services are themed around a corporate "Internal Systems" network, featuring shared Apple/macOS-inspired styling for a cohesive competition environment.

As an Attack & Defense CTF, each service is designed to be fully exploitable by the Red Team and cleanly patchable by the Blue Team without breaking standard Service Level Agreement (SLA) functionality.

## The Challenge Services

This repository contains three independent modules, each running on its own designated port. 

### 1. Internal Auth API (JWT)
* **Directory:** `/jwt_auth/`
* **Port:** `5001`
* **Vulnerability:** JWT Unverified Signature
* **Description:** A corporate Single Sign-On (SSO) dashboard that issues employee session tokens. The critical administrator endpoint disables cryptographic signature verification during the decoding process, allowing attackers to forge tokens with elevated claims without knowing the server's secret key.

### 2. Internal Access Portal (CSRF)
* **Directory:** `/csrf_auth/`
* **Port:** `5000` (or `5002` depending on configuration)
* **Vulnerability:** Cross-Site Request Forgery (Account Takeover)
* **Description:** An account management portal where employees update their contact addresses. The state-changing endpoint properly checks for active session cookies but fails to validate the HTTP `Referer` or implement CSRF tokens. Attackers can hijack an admin's browser session to silently overwrite the admin's recovery email.

### 3. Support Desk AI (LLM)
* **Directory:** `/llm_service/`
* **Port:** `5003`
* **Vulnerability:** Prompt Injection (Excessive Agency / Tool Calling Hijack)
* **Description:** An automated customer support triage system powered by an agentic LLM. The AI parses its own output for JSON blocks (`<tool_call>`) to execute internal workflows. Because incoming emails are fed to the AI without sanitization, attackers can inject malicious tool-call tags into support tickets to execute unauthorized system commands.

---

## Important Note on Documentation

**Detailed documentation is provided inside each service's directory.** 
Please navigate to the specific service folder and read its dedicated `README.md` file. Each individual README contains:
* Complete local setup and deployment commands.
* Step-by-step **Attack Phase** (Red Team) execution workflows.
* Step-by-step **Defense Phase** (Blue Team) source code patching instructions.
* Methods to verify that the applied patch satisfies the SLA checker.

---

## How Flags Work in This Repository

In this competition, every service guards a flag formatted as `HNS{...}`. The goal of the attacker is to exfiltrate this flag, while the defender must secure it. 

Flags are retrieved differently depending on the vulnerability's mechanics:

* **JWT:** The flag is returned directly in the HTTP response body when a successfully forged admin token is submitted to the `/api/admin/flag` endpoint.
* **CSRF:** Because the attack executes blindly in the victim's browser, the attacker cannot see the immediate response. After successfully forcing the admin to change their email via CSRF, the attacker must call a public `/retrieve_flag` endpoint using the newly injected email to prove the account takeover was successful and receive the flag.
* **LLM:** The flag is exposed in the AI's standard output console. The attacker must inject a payload requesting the `read_system_flag` internal tool; when the admin later clicks "Summarize Inbox", the AI executes the tool and prints the flag to the dashboard.