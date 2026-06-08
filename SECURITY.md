# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| `main` | ✅ |
| Older releases | ❌ |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please send a report to **yr0556772363@gmail.com** with the subject line `[CVOps Security] <short description>`.

Include:

- A clear description of the vulnerability and its potential impact
- Step-by-step reproduction instructions (proof-of-concept if possible)
- Any suggested mitigations or patches

**Response timeline:**
- Acknowledgement within **48 hours**
- Full response or fix timeline within **7 days**

We follow coordinated disclosure: we ask that you keep the vulnerability confidential until a fix is released, or 90 days have elapsed since the report, whichever comes first.

## Scope

**In scope:**
- Authentication or authorisation bypass (JWT, org boundaries)
- Token leakage or replay attacks
- SQL injection or arbitrary data exfiltration
- Server-side request forgery (SSRF)
- Privilege escalation across organisations or roles

**Out of scope:**
- Vulnerabilities in third-party dependencies that are not directly exploitable in CVOps
- Theoretical issues without a reproducible proof-of-concept
- Issues that require physical access to the host machine
- Denial-of-service attacks (rate limiting is out of scope for the current phase)

## Security design notes

- All JWTs carry a `jti` (JWT ID) claim; revoked tokens are blacklisted in Redis for the remainder of their lifetime
- Refresh token rotation: the consumed refresh token is blacklisted before a new pair is issued
- Blob storage: clients receive presigned S3 URLs (15-min TTL for GET, 60-min for PUT); raw bytes never pass through the API
- All resources are scoped to `org_id`; cross-org access is blocked at the DB query level
- Passwords are hashed with bcrypt (passlib, cost factor 12)

## Preferred language

English or Hebrew.
