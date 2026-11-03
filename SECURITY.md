# Security

## Reporting a vulnerability
Please report it privately through GitHub: this repository's **Security** tab, **Report a vulnerability**. Do not open a public issue. Say what you found, how to reproduce it, and what it lets someone do.

## How Godling is protected
- **Decisions**: ADR-014 (the security review and its fixes), ADR-015 (the stream relay), ADR-017 (the public edge: limits, Cloudflare, monitoring, audits, the review before real money).
- **Outside review**: real money waits for one ([`deploy/security-review.md`](deploy/security-review.md)).
- **Dependencies**: audited every week and on every change (`.github/workflows/audit.yml`); Dependabot proposes updates.
- **Checking a deployment from outside**: `deploy/check.sh`.
