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

Caveats of the provided controls: (1) the lockout can be used to lock out a *known* user name on purpose (there is no per-IP separation) - an administrator unlocks it; (2) behind a reverse proxy the `Host` header must be passed through unchanged, otherwise the same-origin check refuses browser writes (`KSA_CSRF_ORIGIN_CHECK=false` is the diagnostic escape, not a fix); (3) sign-in history older than 30 days is pruned on the next successful sign-in.

## Actor identity, test principals and submission readiness (iteration 5)
Approval identity is a **durable, structured record**, never a display name: `users.actor_type` is `human` (a real, accountable person), `test` (a software-validation principal) or `ai`. When an approval or a reconciliation exception is recorded, `approvals.actor_type` / `recon_exceptions.accepted_actor_type` are **resolved from the users table at that moment** (`human | test | ai | unregistered | inactive | role_mismatch`) together with `environment` (`KSA_ENVIRONMENT`, default `production`; the synthetic pilot runs as `test`). A name that is not a registered user is `unregistered` (a forged display name or a hand-built `Actor` cannot become `human`); a claimed role that differs from the registered role is `role_mismatch`. Pre-existing approvals are `unregistered` (provenance unprovable) and never count.
`services/readiness.evaluate` decides whether an export is **SUBMISSION READY**: the project is not a demonstration project, no synthetic data is used, the estimate, offer and tender-export approvals (and the approvals behind the rates, commercial policy, tax category and indirects that price the estimate) are for exactly this project/version, were recorded for a registered active **human** holding an allowed role **in a production environment**, have a matching entry in the verifying audit chain (a copied or hand-written approval row has none), every accepted reconciliation exception was accepted by a registered human Commercial Approver/Administrator in production, the gate is clear, the state is Complete, and any linked client profile has no unmet mandatory requirement. Otherwise a *demonstration* project receives a clearly labelled **DEMONSTRATION EXPORT - NOT SUBMISSION READY - NOT APPROVED FOR ANY REAL TENDER** (the banner names the actor types and environment); any other project is refused (`NOT_PRODUCTION_READY`). On a real project in a production environment only a registered human may approve an estimate or tender export or produce the export package (`NON_HUMAN_ACTOR`). The same checks run in the services, so UI, REST API and CLI behave identically (`tests/approvals/test_actor_isolation.py`, `tests/integration/test_actor_isolation_api.py`, pilot stage 19). `init --demo-users` creates `test` principals (their passwords are published); `create-user --actor-type test` creates others.
Limits: a person with administrator rights or database access can register a `human` user or edit rows; the audit chain is tamper-evident only; this is not identity assurance (no MFA/SSO).

## Not provided (do not rely on these)
* **MFA / SSO / password policy / password-reset flow.** Passwords are set by an administrator (`create-user --reset`).
* Per-folder or per-document **access control** inside a project workspace; every signed-in user with a project role sees its files.
* **Encrypted backups**; rotation of the signing key; per-IP rate limiting; a web-application firewall.
* **Concurrent multi-user operation:** requests are serialised through one SQLite connection (correct, not fast). Long reports block other users for their duration.
* A penetration test or external review. Anything beyond a trusted LAN needs one, plus a reverse proxy, a managed database and real identity management.
* Protection against a malicious *administrator* or someone with filesystem access to `var/ksa_estimator.db`.

## Operating guidance
1. Bind to `127.0.0.1` (default) unless TLS is configured. 2. Set `KSA_SECRET_KEY` explicitly in shared use. 3. Replace the demo users (`init --demo-users` is for local demos only). 4. Back up with `python -m app.cli backup` and keep backups on encrypted storage yourself. 5. Treat the `AI` features as optional and off by default (`KSA_AI_ENABLED`); they can only propose.

## End-to-end closure (iteration 6, 2026-10-14)
Full audit and threat model: `docs/ASSUMPTIONS_GOVERNANCE_AND_SECURITY_AUDIT.md`. In short:

* **Four-eyes is now the default** (`allow_self_approval = false` in code and in `config/settings.toml`). An Administrator is **not** exempt for assumptions, project overrides, productivity norms, workforce profiles, programme baselines,
  tender queries, tender documents and rates (`policy.SEPARATION_ENTITIES`). The demo seeder relaxes it only inside its own loader and restores it.
* **Database guards**: triggers refuse any change or delete of an *Approved/Superseded* assumption, project override, productivity norm or workforce profile (`IMMUTABLE_RECORD`). They protect against bugs and casual SQL; anyone with write access to the
  database file can drop them. The hash-chained audit log is tamper-**evident**, not tamper-proof.
* **Identity**: REST/UI identity comes from the signed token, never from a request field (tested: body fields `reviewer`/`actor` are ignored); the CLI `action` command authenticates a real user; `create-user` and password resets from the shell are now audited as `cli:<os user>`.
* **Submission readiness (Stage J)** also requires: no unresolved material query, no missing required document, no synthetic assumption feeding the estimate, an approved non-provisional programme baseline whose norms, workforce profile and baseline approvals are registered-human production approvals, and document approvals for the technical and commercial proposals; a pack with BLOCKED documents or placeholders is never labelled submission-ready even when the approval chain verifies.
* **Not provided**: MFA/SSO, immutable or off-box audit storage, encryption at rest, separation of administrator duties, API rate limiting beyond sign-in lockout, penetration testing. Hardening backlog: audit document section 6. **Deployment restriction:** local-only or trusted-LAN behind TLS; not for internet exposure and not for wider multi-user production until the backlog items 1-3 are done.
