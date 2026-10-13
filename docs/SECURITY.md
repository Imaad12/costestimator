# Security: what is provided and what is not

The application is designed for **one workstation or a small trusted team on a private network**. Iteration 4 added hardening for that use (below); it is **not** an internet-facing product and has had **no third-party security review**.

## Provided (each has an automated test in `tests/integration/test_security_hardening.py` unless noted)
| Control | Behaviour |
|---|---|
| Authentication | PBKDF2 password hashes, HMAC-signed session tokens with expiry (`KSA_TOKEN_TTL_HOURS`), AI principals can never sign in (`tests/integration/test_api_ui.py`) |
| Authorisation | Enforced in services (`approvals.engine.authorize`), never only in the UI; the REST API and UI share one action registry (`tests/approvals`, `test_api_ui.py`) |
| CSRF | State-changing requests that carry the session **cookie** must come from the same origin (`Origin`, else `Referer`, must match `Host`); otherwise `403 CSRF_BLOCKED`. Bearer-token API clients are not subject to it (a token is not an ambient credential). Cookies are `HttpOnly; SameSite=Strict` and `Secure` over HTTPS. Disable only for diagnosis: `KSA_CSRF_ORIGIN_CHECK=false` |
| Sign-in lockout | After `KSA_LOGIN_MAX_FAILURES` (default 5) consecutive failures a name is locked for `KSA_LOGIN_LOCK_MINUTES` (default 15) - **also for unknown names**, so existence is not revealed; a correct password is refused during the lock; the lock is audit-logged; an administrator can clear it (`python -m app.cli unlock-user NAME --user admin`). The failure counter resets after a success |
| Security headers | `Content-Security-Policy` (scripts only from the app itself, no inline scripts, no framing), `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store` for dynamic pages, `Strict-Transport-Security` when served over TLS or behind a proxy that sets `X-Forwarded-Proto: https` (`KSA_SECURITY_HEADERS=false` turns them off) |
| TLS | `python -m app.cli run --ssl-certfile cert.pem --ssl-keyfile key.pem` serves HTTPS. The server **refuses to listen on a non-loopback address without TLS** unless `--allow-insecure-network` confirms TLS is terminated elsewhere (reverse proxy) |
| Audit | Hash-chained `audit_log` (tamper-evident, not tamper-proof): `python -m app.cli audit-verify` |
| Uploads / templates | Uploads never overwrite; client-form templates must be inside the project's workspace (`FORM_PATH`) |
| Secrets | `.env`, `var/`, `projects/` are git-ignored; the signing key is read from `KSA_SECRET_KEY` or a generated key file |

## Not provided (do not rely on these)
* **MFA / SSO / password policy / password-reset flow.** Passwords are set by an administrator (`create-user --reset`).
* Per-folder or per-document **access control** inside a project workspace; every signed-in user with a project role sees its files.
* **Encrypted backups**; rotation of the signing key; per-IP rate limiting; a web-application firewall.
* **Concurrent multi-user operation:** requests are serialised through one SQLite connection (correct, not fast). Long reports block other users for their duration.
* A penetration test or external review. Anything beyond a trusted LAN needs one, plus a reverse proxy, a managed database and real identity management.
* Protection against a malicious *administrator* or someone with filesystem access to `var/ksa_estimator.db`.

## Operating guidance
1. Bind to `127.0.0.1` (default) unless TLS is configured. 2. Set `KSA_SECRET_KEY` explicitly in shared use. 3. Replace the demo users (`init --demo-users` is for local demos only). 4. Back up with `python -m app.cli backup` and keep backups on encrypted storage yourself. 5. Treat the `AI` features as optional and off by default (`KSA_AI_ENABLED`); they can only propose.
